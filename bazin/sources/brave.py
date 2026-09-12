"""Web search for URL discovery: Brave Search API first, Google Programmable Search as the fallback.

Both adapters emit the same shape — one `web` candidate per result, URL and snippet only — so the
ingest layer can swap them without caring which index answered. Neither has profiles: the candidates
they produce are re-platformed by `sources.urls.resolve_platform` and handed to the platform adapter.

Fixture slug rule: `discover(query)` reads `<fixture_dir>/<name>/<slugify(query.query)>.json`, holding
the raw response body (Brave: `{"web": {"results": [...]}}`, CSE: `{"items": [...]}`).
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import Candidate
from .apify import HttpAdapter, as_str, request_json
from .base import DiscoveryQuery, excerpt, slugify

log = logging.getLogger(__name__)

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
SNIPPET_LIMIT = 300


def _market(query: DiscoveryQuery) -> str | None:
    """ISO 3166-1 alpha-2 market code, upper case, or None when the query has no market."""
    market = (query.market or "").strip()
    return market.upper() if len(market) == 2 else None


def _language(query: DiscoveryQuery) -> str | None:
    language = (query.language or "").strip().lower()
    return language[:2] if len(language) >= 2 else None


class BraveSearchAdapter(HttpAdapter):
    """GET /res/v1/web/search with an X-Subscription-Token header. 20 results per call, maximum."""

    name = "brave"
    platform = "web"
    acquisition_method = "serp"
    max_count = 20

    def is_configured(self) -> bool:
        return self.fixture_dir is not None or bool(self.settings.brave_api_key)

    # ---------------------------------------------------------- request building

    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.settings.brave_api_key or "",
        }

    def params(self, query: DiscoveryQuery, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {"q": (query.query or "").strip(), "count": min(limit, self.max_count)}
        market = _market(query)
        if market:
            params["country"] = market
        language = _language(query)
        if language:
            params["search_lang"] = language
        return params

    # ---------------------------------------------------------- mapping

    def _results(self, payload: Any) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        web = payload.get("web")
        results = web.get("results") if isinstance(web, dict) else None
        if not isinstance(results, list):
            results = payload.get("results")
        return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        payload = self.load_or_fetch(
            slug,
            lambda: request_json("GET", BRAVE_ENDPOINT, headers=self.headers(), params=self.params(query, limit)),
        )
        results = self._results(payload)
        if not results:
            return []
        self.store_raw(slug, payload)
        out: list[Candidate] = []
        for rank, result in enumerate(results[:limit], start=1):
            url = as_str(result.get("url"))
            if not url:
                continue
            out.append(
                Candidate(
                    platform=self.platform,
                    url=url,
                    title=as_str(result.get("title")),
                    snippet=excerpt(as_str(result.get("description")), SNIPPET_LIMIT),
                    source_json={"rank": rank},
                )
            )
        return out

    # No fetch_profile: a SERP hit is a URL, not a profile. The base class returns None, which keeps
    # supports_profiles() False so the ingest layer routes the candidate to its platform adapter.


class GoogleCSEAdapter(HttpAdapter):
    """Google Programmable Search JSON API. Fallback when brave_api_key is missing; 10 results per call."""

    name = "google_cse"
    platform = "web"
    acquisition_method = "serp"
    max_count = 10

    def is_configured(self) -> bool:
        if self.fixture_dir is not None:
            return True
        return bool(self.settings.google_cse_key and self.settings.google_cse_cx)

    # ---------------------------------------------------------- request building

    def params(self, query: DiscoveryQuery, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": self.settings.google_cse_key or "",
            "cx": self.settings.google_cse_cx or "",
            "q": (query.query or "").strip(),
            "num": min(limit, self.max_count),
        }
        market = _market(query)
        if market:
            params["gl"] = market
        language = _language(query)
        if language:
            params["lr"] = f"lang_{language}"
        return params

    # ---------------------------------------------------------- mapping

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        payload = self.load_or_fetch(
            slug, lambda: request_json("GET", CSE_ENDPOINT, params=self.params(query, limit))
        )
        items = payload.get("items") if isinstance(payload, dict) else None
        results = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
        if not results:
            return []
        self.store_raw(slug, payload)
        out: list[Candidate] = []
        for rank, result in enumerate(results[:limit], start=1):
            url = as_str(result.get("link"))
            if not url:
                continue
            out.append(
                Candidate(
                    platform=self.platform,
                    url=url,
                    title=as_str(result.get("title")),
                    snippet=excerpt(as_str(result.get("snippet")), SNIPPET_LIMIT),
                    source_json={"rank": rank},
                )
            )
        return out
