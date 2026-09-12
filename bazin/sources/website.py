"""First-party crawl of a seller's own site: one page, parsed for identity and contact signals.

Profiles only — `discover` returns nothing, because websites arrive as candidates from web search
(`brave`/`google_cse`) and from bio links, never from a query of their own.

What one page gives us: <title>, the meta description, schema.org JSON-LD (LocalBusiness / Organization /
Store: name, telephone, address, url), visible phone numbers, wa.me and mailto links, and links to
Instagram / TikTok / Facebook. The social links are written into the bio as `links: <url1> <url2>` so S3
(identity resolution) can cross-link the site with the social identities without a new column.

Parsing uses html.parser from the standard library — no extra dependency, and a malformed page degrades
to "whatever we could read" rather than failing.

Fixture slug rule: `fetch_profile(candidate)` -> `<fixture_dir>/website/<slugify(candidate.url)>.json`
holding `{"url": "...", "robots_txt": "...", "html": "<!doctype html>..."}`.
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from ..models import Candidate, MediaIn, ObservationIn, ProfileBundle
from .apify import BROWSER_HEADERS, HttpAdapter, as_str, fetch_text, join_parts, parse_dt, robots_allows
from .base import DiscoveryQuery, excerpt, slugify
from .urls import clean_url, is_profile_url, resolve_platform

log = logging.getLogger(__name__)

SOCIAL_PLATFORMS = ("instagram", "tiktok", "facebook")
BUSINESS_TYPES = (
    "localbusiness", "organization", "store", "clothingstore", "shop", "corporation",
    "professionalservice", "homeandconstructionbusiness", "person",
)
PHONE_RE = re.compile(r"(?:\+|00)\s?\d[\d\s().\-]{6,18}\d")
WA_RE = re.compile(r"https?://(?:api\.)?wa\.me/[0-9]+|https?://api\.whatsapp\.com/send\?[^\s\"'<>]+")
MAX_LINKS = 8
MAX_PHONES = 3


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
}


class _PageParser(HTMLParser):
    """Collects the few things we need: title, meta, JSON-LD blocks, links and visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self.links: list[tuple[str, str]] = []  # (href, link text)
        self.text_parts: list[str] = []
        self._stack: list[str] = []
        self._in_json_ld = False
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k.lower(): (v or "") for k, v in attrs}
        if tag not in VOID_TAGS:
            self._stack.append(tag)
        if tag == "meta":
            key = (values.get("name") or values.get("property") or "").lower()
            if key and values.get("content"):
                self.meta.setdefault(key, values["content"].strip())
        elif tag == "a" and values.get("href"):
            self._href = values["href"].strip()
            self._link_text = []
        elif tag == "script":
            self._in_json_ld = "ld+json" in values.get("type", "").lower()

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_json_ld = False
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._link_text).strip()))
            self._href = None
            self._link_text = []
        if tag in self._stack:
            del self._stack[len(self._stack) - 1 - self._stack[::-1].index(tag) :]

    def handle_data(self, data: str) -> None:
        current = self._stack[-1] if self._stack else ""
        if self._in_json_ld:
            self.json_ld.append(data)
            return
        if current in ("script", "style"):
            return
        text = data.strip()
        if not text:
            return
        if current == "title" and not self.title:
            self.title = text
        if self._href is not None:
            self._link_text.append(text)
        self.text_parts.append(text)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()


def _walk_json_ld(node: Any) -> list[dict]:
    """Flatten @graph and arrays into the list of objects that carry an @type."""
    out: list[dict] = []
    if isinstance(node, list):
        for entry in node:
            out.extend(_walk_json_ld(entry))
    elif isinstance(node, dict):
        if node.get("@graph"):
            out.extend(_walk_json_ld(node["@graph"]))
        if node.get("@type"):
            out.append(node)
        for value in node.values():
            if isinstance(value, (list, dict)) and value is not node.get("@graph"):
                out.extend(_walk_json_ld(value))
    return out


def _types_of(node: dict) -> list[str]:
    raw = node.get("@type")
    values = raw if isinstance(raw, list) else [raw]
    return [str(v).lower() for v in values if v]


def _address_of(node: dict) -> str | None:
    address = node.get("address")
    if isinstance(address, str):
        return address.strip() or None
    if isinstance(address, dict):
        parts = [
            as_str(address.get("streetAddress")),
            as_str(address.get("addressLocality")),
            as_str(address.get("postalCode")),
            as_str(address.get("addressCountry")),
        ]
        joined = ", ".join(p for p in parts if p)
        return joined or None
    return None


def business_json_ld(blocks: list[str]) -> dict:
    """The first schema.org business-ish node: {name, telephone, address, url}."""
    nodes: list[dict] = []
    for block in blocks:
        try:
            nodes.extend(_walk_json_ld(json.loads(block)))
        except (ValueError, TypeError):
            continue
    for node in nodes:
        if any(t in BUSINESS_TYPES for t in _types_of(node)):
            return {
                "name": as_str(node.get("name")),
                "telephone": as_str(node.get("telephone")),
                "address": _address_of(node),
                "url": as_str(node.get("url")),
                "published": as_str(node.get("datePublished")),
            }
    return {}


def _normalise_phone(raw: str) -> str:
    return re.sub(r"[^\d+]", "", raw.replace("00", "+", 1) if raw.startswith("00") else raw)


def extract_contacts(text: str, links: list[tuple[str, str]], base_url: str) -> dict[str, list[str]]:
    """Phones, emails, WhatsApp links and social profile URLs found on one page."""
    phones: list[str] = []
    emails: list[str] = []
    whatsapp: list[str] = []
    socials: list[str] = []
    for match in PHONE_RE.findall(text):
        phone = _normalise_phone(match)
        if 8 <= len(phone.lstrip("+")) <= 15 and phone not in phones:
            phones.append(phone)
    for href, _label in links:
        if not href:
            continue
        lowered = href.lower()
        if lowered.startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if email and email not in emails:
                emails.append(email)
            continue
        if lowered.startswith("tel:"):
            phone = _normalise_phone(href[4:])
            if phone and phone not in phones:
                phones.append(phone)
            continue
        absolute = urljoin(base_url, href)
        if WA_RE.match(absolute):
            if absolute not in whatsapp:
                whatsapp.append(absolute)
            continue
        if not absolute.startswith("http"):
            continue
        platform, url, _handle = resolve_platform(absolute)
        if platform in SOCIAL_PLATFORMS and is_profile_url(platform, url) and url not in socials:
            socials.append(url)
    for match in WA_RE.findall(text):
        if match not in whatsapp:
            whatsapp.append(match)
    return {"phones": phones, "emails": emails, "whatsapp": whatsapp, "socials": socials}


class WebsiteAdapter(HttpAdapter):
    """Compliant first-party crawl: browser User-Agent, robots.txt honoured, one page per identity."""

    name = "website"
    platform = "website"
    acquisition_method = "first_party_crawl"

    def is_configured(self) -> bool:
        return True

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        """Websites are discovered by the SERP adapters, never by a query of their own."""
        return []

    # ---------------------------------------------------------- request building

    def headers(self) -> dict[str, str]:
        return dict(BROWSER_HEADERS)

    @staticmethod
    def robots_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme or 'https'}://{parsed.netloc}/robots.txt"

    def _fetch_page(self, url: str) -> dict:
        robots = fetch_text(self.robots_url(url), headers=self.headers())
        if not robots_allows(robots, url):
            log.info("website: robots.txt disallows %s", url)
            return {"url": url, "robots_txt": robots, "blocked": True, "html": None}
        return {"url": url, "robots_txt": robots, "html": fetch_text(url, headers=self.headers())}

    # ---------------------------------------------------------- mapping

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        slug = slugify(candidate.url)
        url = clean_url(candidate.url)
        payload = self.load_or_fetch(slug, lambda: self._fetch_page(url))
        if not isinstance(payload, dict):
            return None
        page_url = as_str(payload.get("url")) or url
        if payload.get("blocked") or not robots_allows(payload.get("robots_txt"), page_url):
            log.info("website: skipping %s (robots.txt)", page_url)
            return None
        html = payload.get("html")
        if not isinstance(html, str) or not html.strip():
            return None
        raw_ref = self.store_raw(slug, payload)

        parser = _PageParser()
        parser.feed(html)
        parser.close()
        meta = parser.meta
        description = as_str(meta.get("description")) or as_str(meta.get("og:description"))
        title = parser.title or as_str(meta.get("og:title"))
        ld = business_json_ld(parser.json_ld)
        contacts = extract_contacts(parser.text, parser.links, page_url)
        phones = contacts["phones"]
        telephone = as_str(ld.get("telephone"))
        if telephone and _normalise_phone(telephone) not in phones:
            phones.insert(0, _normalise_phone(telephone))
        links = (contacts["whatsapp"] + contacts["socials"])[:MAX_LINKS]

        bio = join_parts(
            [
                description or as_str(ld.get("name")),
                as_str(ld.get("address")),
                f"tel: {' '.join(phones[:MAX_PHONES])}" if phones else None,
                f"email: {contacts['emails'][0]}" if contacts["emails"] else None,
                f"links: {' '.join(links)}" if links else None,
            ],
            sep=" · ",
        )
        image = as_str(meta.get("og:image"))
        observation = ObservationIn(
            platform=self.platform,
            source_url=page_url,
            kind="page",
            external_id=None,
            published_at=parse_dt(ld.get("published") or meta.get("article:published_time")),
            caption_excerpt=excerpt(join_parts([title, description])),
            hashtags=[],
            mentions=[],
            language=as_str(meta.get("og:locale")),
            engagement={},
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=[MediaIn(media_url=image, thumbnail_url=image)] if image else [],
        )
        return ProfileBundle(
            platform=self.platform,
            url=page_url,
            handle=(urlparse(page_url).hostname or "").removeprefix("www.") or None,
            external_id=None,
            display_name=as_str(ld.get("name")) or title,
            bio=excerpt(bio, 600),
            bio_link=as_str(ld.get("url")) or page_url,
            followers=None,
            observations=[observation],
            raw_ref=raw_ref,
        )
