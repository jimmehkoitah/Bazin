"""Apify-backed adapters: Instagram, TikTok, Facebook pages and Google Maps.

Apify runs "actors" (hosted scrapers). One run = start, poll, read dataset:

    POST https://api.apify.com/v2/acts/{actor}/runs?token=...   -> {"data": {"id", "defaultDatasetId", ...}}
    GET  https://api.apify.com/v2/actor-runs/{runId}?token=...   -> poll until status is terminal
    GET  https://api.apify.com/v2/datasets/{datasetId}/items?clean=true&token=...

Actor ids are written `owner/name` everywhere in this repo and converted to the `owner~name` form the
REST path requires by `ApifyClient.actor_path`.

Fixture slug rule (shared by every adapter in this package)
-----------------------------------------------------------
    discover(query)             -> slugify(query.query)
    fetch_profile(candidate)    -> slugify(candidate.url)

so `#bazinriche` reads `tests/fixtures/apify_instagram/bazinriche.json` and the profile
`https://www.instagram.com/atelier.khadija.dakar/` reads
`tests/fixtures/apify_instagram/https-www-instagram-com-atelier-khadija-dakar.json`.
A fixture holds exactly what the vendor returns (an Apify dataset array, an API response body); the
parsing below is therefore identical in fixture and live mode. When `fixture_dir` is set and the file is
missing the adapter returns nothing instead of falling back to the network, so tests can never call out.

This module also hosts the small HTTP and parsing helpers shared by the other adapters in this package
(`request_json`, `fetch_text`, `robots_allows`, `parse_dt`, ...). They live here rather than in a new
`sources/http.py` only to keep the package flat; move them if the package grows.
"""

from __future__ import annotations

import html as html_mod
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from ..models import Candidate, MediaIn, ObservationIn, ProfileBundle
from .base import DiscoveryQuery, SourceAdapter, excerpt, hashtags_in, mentions_in, slugify
from .urls import resolve_platform

log = logging.getLogger(__name__)

TIMEOUT = 30.0
MAX_RETRIES = 2
BACKOFF_SECONDS = 1.5
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
BIO_LIMIT = 600  # ProfileBundle.bio max_length

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {"User-Agent": BROWSER_UA, "Accept-Language": "fr,en;q=0.8"}


# ---------------------------------------------------------------- shared HTTP


def _send(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None,
    params: dict[str, Any] | None,
    json_body: Any | None,
    data: Any | None,
    timeout: float,
    client: httpx.Client | None,
) -> httpx.Response:
    if client is not None:
        return client.request(method, url, headers=headers, params=params, json=json_body, data=data)
    with httpx.Client(timeout=timeout, follow_redirects=True) as c:
        return c.request(method, url, headers=headers, params=params, json=json_body, data=data)


def _backoff(attempt: int) -> None:
    time.sleep(BACKOFF_SECONDS * (2**attempt))


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    data: Any | None = None,
    timeout: float = TIMEOUT,
    retries: int = MAX_RETRIES,
    client: httpx.Client | None = None,
) -> Any:
    """One JSON call. Transient failures are retried `retries` times; 4xx raises straight away."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = _send(
                method, url, headers=headers, params=params, json_body=json_body,
                data=data, timeout=timeout, client=client,
            )
        except httpx.TransportError as exc:  # timeouts, DNS, connection refused
            last = exc
            if attempt >= retries:
                raise
            log.warning("%s %s failed (%s); retrying", method, url, exc)
            _backoff(attempt)
            continue
        if resp.status_code in RETRY_STATUS and attempt < retries:
            log.warning("%s %s -> HTTP %s; retrying", method, url, resp.status_code)
            _backoff(attempt)
            continue
        resp.raise_for_status()
        return resp.json() if resp.content else None
    raise last if last else RuntimeError(f"{method} {url} exhausted retries")


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = TIMEOUT,
    retries: int = MAX_RETRIES,
    client: httpx.Client | None = None,
) -> str | None:
    """GET a text document. Returns None when it is not there (a missing robots.txt is normal)."""
    for attempt in range(retries + 1):
        try:
            resp = _send(
                "GET", url, headers=headers, params=None, json_body=None,
                data=None, timeout=timeout, client=client,
            )
        except httpx.TransportError as exc:
            if attempt >= retries:
                raise
            log.warning("GET %s failed (%s); retrying", url, exc)
            _backoff(attempt)
            continue
        if resp.status_code in RETRY_STATUS and attempt < retries:
            _backoff(attempt)
            continue
        if resp.status_code >= 400:
            log.info("GET %s -> HTTP %s", url, resp.status_code)
            return None
        return resp.text
    return None


def robots_allows(robots_txt: str | None, url: str, agent: str = "*") -> bool:
    """True when robots.txt permits `agent` to fetch `url`. No robots.txt means allowed."""
    if not robots_txt:
        return True
    from urllib.robotparser import RobotFileParser

    parser = RobotFileParser()
    try:
        parser.parse(robots_txt.splitlines())
        return bool(parser.can_fetch(agent, url))
    except Exception as exc:  # noqa: BLE001 - an unparsable robots.txt must not stop a crawl
        log.info("could not parse robots.txt for %s: %s", url, exc)
        return True


# ---------------------------------------------------------------- shared parsing


def as_items(data: Any) -> list[dict]:
    """Normalise an actor dataset or API body into a list of dicts."""
    if data is None:
        return []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "data", "elements"):
            value = data.get(key)
            if isinstance(value, list):
                return [d for d in value if isinstance(d, dict)]
        return [data]
    return []


def pick(item: dict, *keys: str, default: Any = None) -> Any:
    """First present, non-empty value among `keys`."""
    for key in keys:
        value = item.get(key)
        if value is not None and value != "" and value != [] and value != {}:
            return value
    return default


def as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_dt(value: Any) -> datetime | None:
    """Parse ISO-8601 strings or epoch seconds/milliseconds into a timezone-aware datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        seconds = float(value)
        if seconds > 1e12:  # milliseconds
            seconds /= 1000.0
        if seconds <= 0:
            return None
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            from dateutil import parser as dateparser

            parsed = dateparser.parse(str(value))
        except Exception:  # noqa: BLE001 - unparsable dates are simply unknown
            return None
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def engagement(**values: int | float | None) -> dict:
    """Engagement dict with the unknown metrics dropped."""
    return {k: v for k, v in values.items() if v is not None}


def _tag_strings(raw: Any) -> list[str]:
    out: list[str] = []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if isinstance(entry, dict):
            entry = pick(entry, "name", "title", "hashtagName", "text")
        text = as_str(entry)
        if text:
            out.append(text)
    return out


def merge_tags(caption: str | None, raw: Any = None) -> list[str]:
    """Hashtags from the caption plus any the source listed separately, lowercased and without '#'."""
    tags = list(hashtags_in(caption))
    for text in _tag_strings(raw):
        tag = text.lstrip("#").strip().lower()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def merge_mentions(caption: str | None, raw: Any = None) -> list[str]:
    out = list(mentions_in(caption))
    for text in _tag_strings(raw):
        handle = text.lstrip("@").strip().lower().rstrip(".")
        if handle and handle not in out:
            out.append(handle)
    return out


def strip_html(raw: str | None, limit: int | None = None) -> str | None:
    """Visible text of an HTML fragment, collapsed to single spaces."""
    if not raw:
        return None
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        text = text[:limit].rstrip()
    return text or None


# XOF is written FCFA (and XAF likewise) because that is the token bazin.prices.parse_prices reads.
CURRENCY_TOKENS = {"XOF": "FCFA", "XAF": "FCFA"}


def format_money(amount: float | None, currency: str | None) -> str | None:
    """'150000 FCFA' / '45.50 EUR' — written so bazin.prices.parse_prices can read it back."""
    if amount is None:
        return None
    token = CURRENCY_TOKENS.get((currency or "").upper(), (currency or "").upper())
    number = f"{amount:.2f}".rstrip("0").rstrip(".") if amount % 1 else str(int(amount))
    return f"{number} {token}".strip()


def join_parts(parts: list[str | None], sep: str = " — ") -> str | None:
    """Join the non-empty parts of a label such as 'name — category — address'."""
    kept = [p.strip() for p in parts if p and p.strip()]
    return sep.join(kept) or None


# ---------------------------------------------------------------- adapter base


class HttpAdapter(SourceAdapter):
    """Common fixture-first plumbing for every adapter that talks to a remote service."""

    def load_or_fetch(self, slug: str, fetch: Callable[[], Any]) -> Any | None:
        """The recorded payload in fixture mode, otherwise the live one. Never both."""
        if self.fixture_dir is not None:
            payload = self.load_fixture(slug)
            if payload is None:
                log.info("%s: no fixture %s", self.name, self._fixture_path(slug))
            return payload
        return fetch()

    def store_raw(self, slug: str, payload: Any) -> str | None:
        """Hand the full payload to the raw store and return the reference for observations."""
        if payload in (None, [], {}):
            return None
        try:
            return self.raw.put(self.name, slug, payload)
        except OSError as exc:  # a broken raw store must not lose the candidates
            log.warning("%s: could not store raw payload for %s: %s", self.name, slug, exc)
            return None


class ApifyError(RuntimeError):
    """An actor run failed, was aborted, or did not finish in time."""


class ApifyClient:
    """Minimal Apify REST client: start a run, wait for it, read its dataset."""

    BASE_URL = "https://api.apify.com/v2"
    TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}

    def __init__(
        self,
        token: str | None,
        *,
        timeout: float = TIMEOUT,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ):
        self.token = token
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    @staticmethod
    def actor_path(actor: str) -> str:
        """'apify/instagram-scraper' -> 'apify~instagram-scraper' (the form the REST path takes)."""
        return actor.replace("/", "~")

    def _params(self, **extra: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"token": self.token}
        params.update({k: v for k, v in extra.items() if v is not None})
        return params

    def start_run(self, actor: str, run_input: dict) -> dict:
        if not self.token:
            raise ApifyError("no apify_token configured")
        url = f"{self.BASE_URL}/acts/{self.actor_path(actor)}/runs"
        body = request_json("POST", url, params=self._params(), json_body=run_input, timeout=self.timeout)
        run = (body or {}).get("data") or {}
        if not run.get("id"):
            raise ApifyError(f"{actor}: run did not start: {body!r}")
        log.info("apify %s run %s started", actor, run["id"])
        return run

    def run_status(self, run_id: str) -> dict:
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        body = request_json("GET", url, params=self._params(), timeout=self.timeout)
        return (body or {}).get("data") or {}

    def wait_for_run(self, run_id: str) -> dict:
        """Poll until the run reaches a terminal status; raises ApifyError past `max_wait`."""
        deadline = time.monotonic() + self.max_wait
        while True:
            run = self.run_status(run_id)
            status = run.get("status")
            if status in self.TERMINAL:
                return run
            if time.monotonic() >= deadline:
                raise ApifyError(f"run {run_id} still {status} after {self.max_wait}s")
            time.sleep(self.poll_interval)

    def dataset_items(self, dataset_id: str, limit: int | None = None) -> list[dict]:
        url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        body = request_json("GET", url, params=self._params(clean="true", limit=limit), timeout=self.timeout)
        return as_items(body)

    def run_actor(self, actor: str, run_input: dict, limit: int | None = None) -> list[dict]:
        run = self.wait_for_run(self.start_run(actor, run_input)["id"])
        if run.get("status") != "SUCCEEDED":
            raise ApifyError(f"{actor}: run {run.get('id')} finished as {run.get('status')}")
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []
        return self.dataset_items(dataset_id, limit=limit)


class ApifyAdapter(HttpAdapter):
    """Base for the four scraper adapters. Subclasses build actor inputs and map items."""

    actor: str = ""
    acquisition_method: str = "third_party_scraper"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._client: ApifyClient | None = None

    @property
    def client(self) -> ApifyClient:
        if self._client is None:
            self._client = ApifyClient(self.settings.apify_token)
        return self._client

    def is_configured(self) -> bool:
        return self.fixture_dir is not None or bool(self.settings.apify_token)

    def run(self, slug: str, run_input: dict, actor: str | None = None, limit: int | None = None) -> list[dict]:
        """Dataset items for one actor run, from the fixture when there is one."""
        payload = self.load_or_fetch(slug, lambda: self.client.run_actor(actor or self.actor, run_input, limit))
        return as_items(payload)


# ---------------------------------------------------------------- Instagram


def _instagram_post_url(post: dict) -> str | None:
    url = as_str(pick(post, "url", "postUrl"))
    if url:
        return url
    code = as_str(pick(post, "shortCode", "shortcode", "code"))
    return f"https://www.instagram.com/p/{code}/" if code else None


class ApifyInstagramAdapter(ApifyAdapter):
    """Hashtag discovery and profile detail via apify/instagram-scraper."""

    name = "apify_instagram"
    platform = "instagram"
    actor = "apify/instagram-scraper"

    # ---------------------------------------------------------- request building

    def discover_input(self, query: DiscoveryQuery, limit: int) -> dict:
        term = (query.query or "").strip()
        run_input: dict[str, Any] = {
            "resultsType": "posts",
            "resultsLimit": limit,
            "addParentData": False,
        }
        if term.startswith("#"):
            tag = term.lstrip("#").strip().lower()
            run_input["directUrls"] = [f"https://www.instagram.com/explore/tags/{tag}/"]
        else:
            run_input["search"] = term
            run_input["searchType"] = "hashtag"
            run_input["searchLimit"] = 1
        return run_input

    def profile_input(self, url: str, max_posts: int) -> dict:
        return {
            "directUrls": [url],
            "resultsType": "details",
            "resultsLimit": max_posts,
            "addParentData": False,
        }

    # ---------------------------------------------------------- mapping

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        items = self.run(slug, self.discover_input(query, limit), limit=limit)
        if not items:
            return []
        self.store_raw(slug, items)
        by_owner: dict[str, list[dict]] = {}
        for item in items:
            handle = (as_str(pick(item, "ownerUsername", "username", "owner_username")) or "").lstrip("@").lower()
            if handle:
                by_owner.setdefault(handle, []).append(item)
        out: list[Candidate] = []
        for handle, posts in by_owner.items():
            first = posts[0]
            samples = [u for u in (_instagram_post_url(p) for p in posts[:5]) if u]
            out.append(
                Candidate(
                    platform=self.platform,
                    url=f"https://www.instagram.com/{handle}/",
                    handle=handle,
                    external_id=as_str(pick(first, "ownerId", "owner_id")),
                    title=as_str(pick(first, "ownerFullName", "fullName")),
                    snippet=excerpt(as_str(pick(first, "caption", "text"))),
                    thumbnail_url=as_str(pick(first, "displayUrl", "thumbnailUrl")),
                    source_json={"post_count_in_results": len(posts), "sample_post_urls": samples},
                )
            )
        return out

    def _observation(self, post: dict, raw_ref: str | None, language: str | None = None) -> ObservationIn | None:
        url = _instagram_post_url(post)
        if not url:
            return None
        caption = as_str(pick(post, "caption", "text"))
        product = (as_str(pick(post, "productType")) or "").lower()
        media_type = (as_str(pick(post, "type", "mediaType")) or "").lower()
        kind = "reel" if product in ("clips", "reels", "igtv") or media_type == "video" else "post"
        display = as_str(pick(post, "displayUrl", "display_url", "thumbnailUrl", "imageUrl"))
        media = (
            [
                MediaIn(
                    media_url=display,
                    thumbnail_url=display,
                    width=as_int(pick(post, "dimensionsWidth")),
                    height=as_int(pick(post, "dimensionsHeight")),
                )
            ]
            if display
            else []
        )
        return ObservationIn(
            platform=self.platform,
            source_url=url,
            kind=kind,
            external_id=as_str(pick(post, "id", "shortCode")),
            published_at=parse_dt(pick(post, "timestamp", "takenAt", "taken_at_timestamp")),
            caption_excerpt=excerpt(caption),
            hashtags=merge_tags(caption, post.get("hashtags")),
            mentions=merge_mentions(caption, post.get("mentions")),
            language=language,
            engagement=engagement(
                likes=as_int(pick(post, "likesCount", "likes")),
                comments=as_int(pick(post, "commentsCount", "comments")),
                views=as_int(pick(post, "videoViewCount", "videoPlayCount", "views")),
            ),
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=media,
        )

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        slug = slugify(candidate.url)
        items = self.run(slug, self.profile_input(candidate.url, max_posts), limit=max_posts)
        if not items:
            return None
        raw_ref = self.store_raw(slug, items)
        profile = items[0]
        handle = (as_str(pick(profile, "username", "ownerUsername")) or candidate.handle or "").lstrip("@").lower()
        posts = profile.get("latestPosts") or profile.get("posts") or [i for i in items[1:]]
        observations = [
            obs
            for obs in (self._observation(p, raw_ref) for p in as_items(posts)[:max_posts])
            if obs is not None
        ]
        return ProfileBundle(
            platform=self.platform,
            url=f"https://www.instagram.com/{handle}/" if handle else candidate.url,
            handle=handle or None,
            external_id=as_str(pick(profile, "id", "ownerId")),
            display_name=as_str(pick(profile, "fullName", "ownerFullName")),
            bio=excerpt(as_str(pick(profile, "biography", "bio")), BIO_LIMIT),
            bio_link=as_str(pick(profile, "externalUrl", "external_url", "bioLink", "website")),
            followers=as_int(pick(profile, "followersCount", "followers")),
            observations=observations,
            raw_ref=raw_ref,
        )


# ---------------------------------------------------------------- TikTok


def _tiktok_handle(url: str) -> str | None:
    match = re.search(r"/@([\w.\-]+)", url or "")
    return match.group(1).lower() if match else None


def _tiktok_author(item: dict) -> dict:
    author = item.get("authorMeta")
    return author if isinstance(author, dict) else {}


def _tiktok_video_url(item: dict, handle: str | None = None) -> str | None:
    url = as_str(pick(item, "webVideoUrl", "videoUrl", "url"))
    if url:
        return url
    video_id = as_str(pick(item, "id", "videoId"))
    handle = handle or (as_str(pick(_tiktok_author(item), "name", "uniqueId")) or "").lower()
    return f"https://www.tiktok.com/@{handle}/video/{video_id}" if handle and video_id else None


class ApifyTikTokAdapter(ApifyAdapter):
    """Hashtag and free-text discovery plus profile crawls via clockworks/tiktok-scraper."""

    name = "apify_tiktok"
    platform = "tiktok"
    actor = "clockworks/tiktok-scraper"

    # ---------------------------------------------------------- request building

    def discover_input(self, query: DiscoveryQuery, limit: int) -> dict:
        term = (query.query or "").strip()
        run_input: dict[str, Any] = {
            "resultsPerPage": limit,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
            "shouldDownloadSubtitles": False,
            "shouldDownloadSlideshowImages": False,
        }
        if term.startswith("#"):
            run_input["hashtags"] = [term.lstrip("#").strip().lower()]
        else:
            run_input["searchQueries"] = [term]
            run_input["searchSection"] = ""
        return run_input

    def profile_input(self, handle: str, max_posts: int) -> dict:
        return {
            "profiles": [handle],
            "resultsPerPage": max_posts,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
            "shouldDownloadSubtitles": False,
            "profileScrapeSections": ["videos"],
            "profileSorting": "latest",
        }

    # ---------------------------------------------------------- mapping

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        items = self.run(slug, self.discover_input(query, limit), limit=limit)
        if not items:
            return []
        self.store_raw(slug, items)
        by_author: dict[str, list[dict]] = {}
        for item in items:
            handle = (as_str(pick(_tiktok_author(item), "name", "uniqueId")) or "").lstrip("@").lower()
            if handle:
                by_author.setdefault(handle, []).append(item)
        out: list[Candidate] = []
        for handle, videos in by_author.items():
            author = _tiktok_author(videos[0])
            samples = [u for u in (_tiktok_video_url(v, handle) for v in videos[:5]) if u]
            out.append(
                Candidate(
                    platform=self.platform,
                    url=f"https://www.tiktok.com/@{handle}",
                    handle=handle,
                    external_id=as_str(pick(author, "id")),
                    title=as_str(pick(author, "nickName", "nickname")),
                    snippet=excerpt(as_str(pick(videos[0], "text", "desc"))),
                    thumbnail_url=as_str(pick(videos[0].get("videoMeta") or {}, "coverUrl", "originalCoverUrl")),
                    source_json={"post_count_in_results": len(videos), "sample_post_urls": samples},
                )
            )
        return out

    def _observation(self, item: dict, handle: str | None, raw_ref: str | None) -> ObservationIn | None:
        url = _tiktok_video_url(item, handle)
        if not url:
            return None
        caption = as_str(pick(item, "text", "desc", "caption"))
        meta = item.get("videoMeta") if isinstance(item.get("videoMeta"), dict) else {}
        cover = as_str(pick(meta, "coverUrl", "originalCoverUrl", "dynamicCover"))
        media = (
            [MediaIn(media_url=cover, thumbnail_url=cover, width=as_int(meta.get("width")),
                     height=as_int(meta.get("height")))]
            if cover
            else []
        )
        return ObservationIn(
            platform=self.platform,
            source_url=url,
            kind="video",
            external_id=as_str(pick(item, "id", "videoId")),
            published_at=parse_dt(pick(item, "createTimeISO", "createTime", "created_at")),
            caption_excerpt=excerpt(caption),
            hashtags=merge_tags(caption, item.get("hashtags")),
            mentions=merge_mentions(caption, item.get("mentions")),
            language=as_str(pick(item, "textLanguage", "language")),
            engagement=engagement(
                likes=as_int(pick(item, "diggCount", "likes")),
                comments=as_int(pick(item, "commentCount", "comments")),
                views=as_int(pick(item, "playCount", "views")),
                shares=as_int(pick(item, "shareCount")),
            ),
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=media,
        )

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        handle = (candidate.handle or _tiktok_handle(candidate.url) or "").lstrip("@").lower()
        if not handle:
            return None
        slug = slugify(candidate.url)
        items = self.run(slug, self.profile_input(handle, max_posts), limit=max_posts)
        if not items:
            return None
        raw_ref = self.store_raw(slug, items)
        author = _tiktok_author(items[0])
        bio_link = pick(author, "bioLink", "bio_link")
        if isinstance(bio_link, dict):
            bio_link = pick(bio_link, "link", "url")
        observations = [
            obs for obs in (self._observation(i, handle, raw_ref) for i in items[:max_posts]) if obs is not None
        ]
        return ProfileBundle(
            platform=self.platform,
            url=f"https://www.tiktok.com/@{handle}",
            handle=handle,
            external_id=as_str(pick(author, "id")),
            display_name=as_str(pick(author, "nickName", "nickname")),
            bio=excerpt(as_str(pick(author, "signature", "bio")), BIO_LIMIT),
            bio_link=as_str(bio_link),
            followers=as_int(pick(author, "fans", "followers", "followerCount")),
            observations=observations,
            raw_ref=raw_ref,
        )


# ---------------------------------------------------------------- Facebook


class ApifyFacebookAdapter(ApifyAdapter):
    """Page search and page detail via apify/facebook-pages-scraper, posts via facebook-posts-scraper.

    ASSUMPTION to verify live: the pages actor is documented around `startUrls`; the search input used by
    `discover_input` (`searchQueries`) must be checked against the actor's input schema, and swapped for
    `apify/facebook-search-scraper` if the pages actor has no search mode.
    """

    name = "apify_facebook"
    platform = "facebook"
    actor = "apify/facebook-pages-scraper"
    posts_actor = "apify/facebook-posts-scraper"

    # ---------------------------------------------------------- request building

    def discover_input(self, query: DiscoveryQuery, limit: int) -> dict:
        return {
            "searchQueries": [(query.query or "").strip()],
            "resultsLimit": limit,
            "language": query.language or "en",
        }

    def page_input(self, url: str) -> dict:
        return {"startUrls": [{"url": url}], "resultsLimit": 1}

    def posts_input(self, url: str, max_posts: int) -> dict:
        return {"startUrls": [{"url": url}], "resultsLimit": max_posts, "onlyPostsNewerThan": None}

    # ---------------------------------------------------------- mapping

    def _page_url(self, item: dict) -> tuple[str | None, str | None]:
        raw = as_str(pick(item, "facebookUrl", "pageUrl", "url"))
        if not raw:
            page_name = as_str(pick(item, "pageName", "username"))
            raw = f"https://www.facebook.com/{page_name}/" if page_name else None
        if not raw:
            return None, None
        platform, url, handle = resolve_platform(raw)
        if platform != "facebook":
            return None, None
        return url, handle

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        items = self.run(slug, self.discover_input(query, limit), limit=limit)
        if not items:
            return []
        self.store_raw(slug, items)
        out: list[Candidate] = []
        for item in items:
            url, handle = self._page_url(item)
            if not url:
                continue
            categories = item.get("categories") if isinstance(item.get("categories"), list) else []
            out.append(
                Candidate(
                    platform=self.platform,
                    url=url,
                    handle=handle,
                    external_id=as_str(pick(item, "pageId", "id")),
                    title=as_str(pick(item, "title", "name", "pageName")),
                    snippet=excerpt(join_parts([
                        as_str(pick(item, "intro", "about", "categoryName")),
                        ", ".join(str(c) for c in categories) or None,
                        as_str(pick(item, "address")),
                    ])),
                    thumbnail_url=as_str(pick(item, "profilePictureUrl", "profilePhoto", "coverPhotoUrl")),
                    source_json={
                        k: v
                        for k, v in {
                            "likes": as_int(pick(item, "likes")),
                            "followers": as_int(pick(item, "followers")),
                            "phone": as_str(pick(item, "phone")),
                            "address": as_str(pick(item, "address")),
                            "website": as_str(pick(item, "website", "websites")),
                            "categories": [str(c) for c in categories] or None,
                        }.items()
                        if v is not None
                    },
                )
            )
        return out

    def _profile_payload(self, slug: str, url: str, max_posts: int) -> dict | None:
        def live() -> dict:
            return {
                "page": self.client.run_actor(self.actor, self.page_input(url), limit=1),
                "posts": self.client.run_actor(self.posts_actor, self.posts_input(url, max_posts), max_posts),
            }

        payload = self.load_or_fetch(slug, live)
        return payload if isinstance(payload, dict) else None

    def _observation(self, post: dict, raw_ref: str | None) -> ObservationIn | None:
        url = as_str(pick(post, "url", "postUrl", "link", "topLevelUrl"))
        if not url:
            return None
        caption = as_str(pick(post, "text", "message", "postText"))
        media_items = post.get("media") if isinstance(post.get("media"), list) else []
        thumb = None
        for entry in media_items:
            if isinstance(entry, dict):
                thumb = as_str(pick(entry, "thumbnail", "photo_image", "image", "url"))
                if isinstance(thumb, dict):
                    thumb = as_str(pick(thumb, "uri", "url"))
                if thumb:
                    break
        thumb = thumb or as_str(pick(post, "imageUrl", "thumbnailUrl"))
        return ObservationIn(
            platform=self.platform,
            source_url=url,
            kind="post",
            external_id=as_str(pick(post, "postId", "id")),
            published_at=parse_dt(pick(post, "time", "date", "timestamp", "publishedAt")),
            caption_excerpt=excerpt(caption),
            hashtags=merge_tags(caption),
            mentions=merge_mentions(caption),
            language=None,
            engagement=engagement(
                likes=as_int(pick(post, "likes", "likesCount", "reactionsCount")),
                comments=as_int(pick(post, "comments", "commentsCount")),
                shares=as_int(pick(post, "shares", "sharesCount")),
            ),
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=[MediaIn(media_url=thumb, thumbnail_url=thumb)] if thumb else [],
        )

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        slug = slugify(candidate.url)
        payload = self._profile_payload(slug, candidate.url, max_posts)
        if not payload:
            return None
        pages = as_items(payload.get("page"))
        posts = as_items(payload.get("posts"))
        if not pages and not posts:
            return None
        raw_ref = self.store_raw(slug, payload)
        page = pages[0] if pages else {}
        about = page.get("about_me") if isinstance(page.get("about_me"), dict) else {}
        phone = as_str(pick(page, "phone", "phoneNumber"))
        bio = join_parts(
            [
                as_str(pick(about, "text")) or as_str(pick(page, "intro", "about", "pageIntro")),
                as_str(pick(page, "address")),
                f"phone: {phone}" if phone else None,
                as_str(pick(page, "email")),
            ],
            sep=" · ",
        )
        website = pick(page, "website", "websites")
        if isinstance(website, list):
            website = website[0] if website else None
        observations = [obs for obs in (self._observation(p, raw_ref) for p in posts[:max_posts]) if obs]
        return ProfileBundle(
            platform=self.platform,
            url=candidate.url,
            handle=candidate.handle or as_str(pick(page, "pageName")),
            external_id=as_str(pick(page, "pageId", "id")),
            display_name=as_str(pick(page, "title", "name")),
            bio=excerpt(bio, BIO_LIMIT),
            bio_link=as_str(website),
            followers=as_int(pick(page, "followers", "likes")),
            observations=observations,
            raw_ref=raw_ref,
        )


# ---------------------------------------------------------------- Google Maps


def _place_id(item: dict) -> str | None:
    return as_str(pick(item, "placeId", "place_id", "fid", "cid"))


def _place_url(item: dict) -> str | None:
    """Canonical place URL. The actor's own `url` is a search link, so prefer the stable place_id form."""
    place_id = _place_id(item)
    if place_id:
        return f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    return as_str(pick(item, "url", "searchPageUrl"))


def _place_latlon(item: dict) -> tuple[float | None, float | None]:
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    lat = as_float(pick(location, "lat", "latitude"))
    lon = as_float(pick(location, "lng", "lon", "longitude"))
    if lat is None:
        lat = as_float(pick(item, "lat", "latitude"))
    if lon is None:
        lon = as_float(pick(item, "lng", "lon", "longitude"))
    return lat, lon


def _first_image(item: dict) -> str | None:
    image = pick(item, "imageUrl", "imageUrls", "thumbnailUrl")
    if isinstance(image, list):
        image = next((i for i in image if isinstance(i, str)), None)
    return as_str(image)


class ApifyGoogleMapsAdapter(ApifyAdapter):
    """Physical shops and ateliers via compass/crawler-google-places."""

    name = "apify_google_maps"
    platform = "google_maps"
    actor = "compass/crawler-google-places"

    # ---------------------------------------------------------- request building

    def discover_input(self, query: DiscoveryQuery, limit: int) -> dict:
        return {
            "searchStringsArray": [(query.query or "").strip()],
            "maxCrawledPlacesPerSearch": limit,
            "language": query.language or "en",
            "skipClosedPlaces": False,
            "scrapePlaceDetailPage": True,
        }

    def profile_input(self, candidate: Candidate, place_id: str | None) -> dict:
        """ASSUMPTION to verify: the actor takes bare place ids in `placeIds`; startUrls is the fallback."""
        if place_id:
            return {"placeIds": [place_id], "maxCrawledPlacesPerSearch": 1, "scrapePlaceDetailPage": True}
        return {"startUrls": [{"url": candidate.url}], "maxCrawledPlacesPerSearch": 1}

    # ---------------------------------------------------------- mapping

    def _source_json(self, item: dict) -> dict:
        lat, lon = _place_latlon(item)
        values = {
            "address": as_str(pick(item, "address", "fullAddress")),
            "phone": as_str(pick(item, "phone", "phoneUnformatted")),
            "website": as_str(pick(item, "website", "webSite")),
            "rating": as_float(pick(item, "totalScore", "rating")),
            "reviews_count": as_int(pick(item, "reviewsCount", "userRatingCount")),
            "lat": lat,
            "lon": lon,
            "category": as_str(pick(item, "categoryName", "category")),
        }
        return {k: v for k, v in values.items() if v is not None}

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        items = self.run(slug, self.discover_input(query, limit), limit=limit)
        if not items:
            return []
        self.store_raw(slug, items)
        out: list[Candidate] = []
        for item in items:
            url = _place_url(item)
            if not url:
                continue
            source_json = self._source_json(item)
            out.append(
                Candidate(
                    platform=self.platform,
                    url=url,
                    external_id=_place_id(item),
                    title=as_str(pick(item, "title", "name")),
                    snippet=excerpt(join_parts([
                        as_str(pick(item, "title", "name")),
                        source_json.get("category"),
                        source_json.get("address"),
                    ])),
                    thumbnail_url=_first_image(item),
                    source_json=source_json,
                )
            )
        return out

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        slug = slugify(candidate.url)
        place_id = candidate.external_id or self._place_id_from_url(candidate.url)
        items = self.run(slug, self.profile_input(candidate, place_id), limit=1)
        if not items:
            return None
        raw_ref = self.store_raw(slug, items)
        item = items[0]
        info = self._source_json(item)
        name = as_str(pick(item, "title", "name"))
        label = join_parts([name, info.get("category"), info.get("address")])
        image = _first_image(item)
        observation = ObservationIn(
            platform=self.platform,
            source_url=candidate.url,
            kind="map_place",
            external_id=_place_id(item),
            published_at=None,
            caption_excerpt=excerpt(label),
            hashtags=[],
            mentions=[],
            language=None,
            engagement=engagement(rating=info.get("rating"), reviews=info.get("reviews_count")),
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=[MediaIn(media_url=image, thumbnail_url=image)] if image else [],
        )
        bio = join_parts(
            [info.get("category"), info.get("address"),
             f"phone: {info['phone']}" if info.get("phone") else None],
            sep=" · ",
        )
        return ProfileBundle(
            platform=self.platform,
            url=candidate.url,
            handle=None,
            external_id=_place_id(item),
            display_name=name,
            bio=excerpt(bio, BIO_LIMIT),
            bio_link=info.get("website"),
            followers=None,
            observations=[observation],
            raw_ref=raw_ref,
        )

    @staticmethod
    def _place_id_from_url(url: str) -> str | None:
        match = re.search(r"place_id:([A-Za-z0-9_\-]+)", url or "")
        return match.group(1) if match else None
