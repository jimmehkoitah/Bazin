"""YouTube Data API v3: channels as candidates, recent videos as observations.

discover      search.list(part=snippet, type=video, q, maxResults<=50) grouped by channelId
fetch_profile channels.list(part=snippet,statistics) + search.list(channelId, order=date) + videos.list(statistics)

Fixture slug rule:
    discover(query)          -> <fixture_dir>/youtube/<slugify(query.query)>.json, a search.list body
    fetch_profile(candidate) -> <fixture_dir>/youtube/<slugify(candidate.url)>.json, a dict of the three
                                responses: {"channel": {...}, "search": {...}, "videos": {...}}
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..models import Candidate, MediaIn, ObservationIn, ProfileBundle
from .apify import HttpAdapter, as_int, as_str, engagement, merge_tags, parse_dt, pick, request_json
from .base import DiscoveryQuery, excerpt, mentions_in, slugify

log = logging.getLogger(__name__)

API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_RESULTS = 50
VIDEO_IDS_PER_CALL = 50


def _channel_id(url: str, fallback: str | None = None) -> str | None:
    match = re.search(r"/channel/([A-Za-z0-9_\-]+)", url or "")
    return match.group(1) if match else fallback


def _thumbnail(snippet: dict) -> str | None:
    thumbs = snippet.get("thumbnails") if isinstance(snippet.get("thumbnails"), dict) else {}
    for size in ("maxres", "standard", "high", "medium", "default"):
        entry = thumbs.get(size)
        if isinstance(entry, dict) and entry.get("url"):
            return as_str(entry["url"])
    return None


def _video_id(item: dict) -> str | None:
    ident = item.get("id")
    if isinstance(ident, dict):
        return as_str(pick(ident, "videoId"))
    return as_str(ident)


class YouTubeAdapter(HttpAdapter):
    """Official API, so no scraping policy applies; statistics are refreshed on re-crawl."""

    name = "youtube"
    platform = "youtube"
    acquisition_method = "official_api"

    def is_configured(self) -> bool:
        return self.fixture_dir is not None or bool(self.settings.youtube_api_key)

    # ---------------------------------------------------------- request building

    def search_params(self, query: DiscoveryQuery, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": self.settings.youtube_api_key or "",
            "part": "snippet",
            "type": "video",
            "q": (query.query or "").strip(),
            "maxResults": min(limit, MAX_RESULTS),
        }
        language = (query.language or "").strip().lower()
        if len(language) >= 2:
            params["relevanceLanguage"] = language[:2]
        market = (query.market or "").strip()
        if len(market) == 2:
            params["regionCode"] = market.upper()
        return params

    def channel_params(self, channel_id: str) -> dict[str, Any]:
        return {"key": self.settings.youtube_api_key or "", "part": "snippet,statistics", "id": channel_id}

    def channel_videos_params(self, channel_id: str, max_posts: int) -> dict[str, Any]:
        return {
            "key": self.settings.youtube_api_key or "",
            "part": "snippet",
            "type": "video",
            "channelId": channel_id,
            "order": "date",
            "maxResults": min(max_posts, MAX_RESULTS),
        }

    def video_stats_params(self, video_ids: list[str]) -> dict[str, Any]:
        return {
            "key": self.settings.youtube_api_key or "",
            "part": "statistics",
            "id": ",".join(video_ids[:VIDEO_IDS_PER_CALL]),
        }

    def _get(self, resource: str, params: dict[str, Any]) -> Any:
        return request_json("GET", f"{API_BASE}/{resource}", params=params)

    # ---------------------------------------------------------- mapping

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        payload = self.load_or_fetch(slug, lambda: self._get("search", self.search_params(query, limit)))
        items = payload.get("items") if isinstance(payload, dict) else None
        results = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
        if not results:
            return []
        self.store_raw(slug, payload)
        by_channel: dict[str, list[dict]] = {}
        for item in results:
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            channel_id = as_str(snippet.get("channelId"))
            if channel_id:
                by_channel.setdefault(channel_id, []).append(item)
        out: list[Candidate] = []
        for channel_id, videos in by_channel.items():
            snippet = videos[0].get("snippet") or {}
            title = as_str(snippet.get("channelTitle"))
            sample_ids = [v for v in (_video_id(i) for i in videos[:5]) if v]
            out.append(
                Candidate(
                    platform=self.platform,
                    url=f"https://www.youtube.com/channel/{channel_id}",
                    handle=title,
                    external_id=channel_id,
                    title=title,
                    snippet=excerpt(as_str(snippet.get("title"))),
                    thumbnail_url=_thumbnail(snippet),
                    source_json={"video_count_in_results": len(videos), "sample_video_ids": sample_ids},
                )
            )
        return out

    def _profile_payload(self, slug: str, channel_id: str, max_posts: int) -> dict | None:
        def live() -> dict:
            channel = self._get("channels", self.channel_params(channel_id))
            search = self._get("search", self.channel_videos_params(channel_id, max_posts))
            ids = [v for v in (_video_id(i) for i in (search or {}).get("items", [])) if v]
            videos = self._get("videos", self.video_stats_params(ids)) if ids else None
            return {"channel": channel, "search": search, "videos": videos}

        payload = self.load_or_fetch(slug, live)
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _stats_by_id(videos_payload: Any) -> dict[str, dict]:
        items = videos_payload.get("items") if isinstance(videos_payload, dict) else None
        out: dict[str, dict] = {}
        for item in items or []:
            if not isinstance(item, dict):
                continue
            video_id = _video_id(item)
            stats = item.get("statistics")
            if video_id and isinstance(stats, dict):
                out[video_id] = stats
        return out

    def _observation(self, item: dict, stats: dict, raw_ref: str | None) -> ObservationIn | None:
        video_id = _video_id(item)
        if not video_id:
            return None
        snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        title = as_str(snippet.get("title"))
        description = as_str(snippet.get("description"))
        text = " — ".join(p for p in (title, description) if p)
        thumb = _thumbnail(snippet)
        return ObservationIn(
            platform=self.platform,
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            kind="video",
            external_id=video_id,
            published_at=parse_dt(snippet.get("publishedAt")),
            caption_excerpt=excerpt(text),
            hashtags=merge_tags(text, snippet.get("tags")),
            mentions=mentions_in(text),
            language=as_str(pick(snippet, "defaultAudioLanguage", "defaultLanguage")),
            engagement=engagement(
                views=as_int(stats.get("viewCount")),
                likes=as_int(stats.get("likeCount")),
                comments=as_int(stats.get("commentCount")),
            ),
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=[MediaIn(media_url=thumb, thumbnail_url=thumb)] if thumb else [],
        )

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        channel_id = _channel_id(candidate.url, candidate.external_id)
        if not channel_id:
            return None
        slug = slugify(candidate.url)
        payload = self._profile_payload(slug, channel_id, max_posts)
        if not payload:
            return None
        channels = (payload.get("channel") or {}).get("items") if isinstance(payload.get("channel"), dict) else None
        channel = channels[0] if isinstance(channels, list) and channels else {}
        search_items = (payload.get("search") or {}).get("items") if isinstance(payload.get("search"), dict) else None
        videos = [i for i in (search_items or []) if isinstance(i, dict)]
        if not channel and not videos:
            return None
        raw_ref = self.store_raw(slug, payload)
        snippet = channel.get("snippet") if isinstance(channel.get("snippet"), dict) else {}
        statistics = channel.get("statistics") if isinstance(channel.get("statistics"), dict) else {}
        stats_by_id = self._stats_by_id(payload.get("videos"))
        observations = [
            obs
            for obs in (
                self._observation(v, stats_by_id.get(_video_id(v) or "", {}), raw_ref) for v in videos[:max_posts]
            )
            if obs is not None
        ]
        custom_url = as_str(snippet.get("customUrl"))
        return ProfileBundle(
            platform=self.platform,
            url=candidate.url,
            handle=(custom_url or as_str(snippet.get("title")) or candidate.handle),
            external_id=as_str(channel.get("id")) or channel_id,
            display_name=as_str(snippet.get("title")),
            bio=excerpt(as_str(snippet.get("description")), 600),
            bio_link=None,
            followers=as_int(statistics.get("subscriberCount")),
            observations=observations,
            raw_ref=raw_ref,
        )
