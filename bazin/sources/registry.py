"""The adapter registry: name -> adapter, keyed exactly like `discovery_queries.tool`.

    adapters = build_adapters(settings, RawStore(settings.raw_store_dir))
    Ingestor(conn, adapters).run_query(query)

`fixture_dir` switches every adapter into fixture mode: payloads are read from
`<fixture_dir>/<adapter name>/<slug>.json` and nothing touches the network, which is how the tests and
this sandbox run. In fixture mode every adapter reports itself configured; in live mode each one checks
the credentials it actually needs:

    apify_instagram / apify_tiktok / apify_facebook / apify_google_maps   settings.apify_token
    brave                                                                settings.brave_api_key
    google_cse                                                           google_cse_key + google_cse_cx
    youtube                                                              settings.youtube_api_key
    etsy                                                                 settings.etsy_api_key
    overture / shopify / website                                         nothing (open data, feeds, crawl)
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import Settings
from .apify import (
    ApifyFacebookAdapter,
    ApifyGoogleMapsAdapter,
    ApifyInstagramAdapter,
    ApifyTikTokAdapter,
)
from .base import RawStore, SourceAdapter
from .brave import BraveSearchAdapter, GoogleCSEAdapter
from .etsy import EtsyAdapter
from .overture import OverpassAdapter
from .shopify import ShopifyAdapter
from .website import WebsiteAdapter
from .youtube import YouTubeAdapter

log = logging.getLogger(__name__)

ADAPTER_CLASSES: tuple[type[SourceAdapter], ...] = (
    ApifyInstagramAdapter,
    ApifyTikTokAdapter,
    ApifyFacebookAdapter,
    ApifyGoogleMapsAdapter,
    BraveSearchAdapter,
    GoogleCSEAdapter,
    YouTubeAdapter,
    EtsyAdapter,
    OverpassAdapter,
    ShopifyAdapter,
    WebsiteAdapter,
)

# Web search has two interchangeable back ends; Brave is the primary index, Google CSE the fallback.
WEB_SEARCH_ORDER = ("brave", "google_cse")


def build_adapters(
    settings: Settings,
    raw_store: RawStore,
    fixture_dir: Path | None = None,
) -> dict[str, SourceAdapter]:
    """Every adapter, keyed by its name. Configuration is not checked here; callers ask is_configured()."""
    return {cls.name: cls(settings, raw_store, fixture_dir) for cls in ADAPTER_CLASSES}


def configured_adapters(adapters: dict[str, SourceAdapter]) -> dict[str, SourceAdapter]:
    """The subset that can actually run now. The planner's other queries stay pending."""
    return {name: adapter for name, adapter in adapters.items() if adapter.is_configured()}


def web_search_adapter(adapters: dict[str, SourceAdapter]) -> SourceAdapter | None:
    """Brave when its key is present, Google Programmable Search otherwise, None when neither is set."""
    for name in WEB_SEARCH_ORDER:
        adapter = adapters.get(name)
        if adapter is not None and adapter.is_configured():
            return adapter
    return None


def missing_credentials(adapters: dict[str, SourceAdapter]) -> list[str]:
    """Adapter names that cannot run for lack of credentials — useful in the CLI before a long run."""
    return sorted(name for name, adapter in adapters.items() if not adapter.is_configured())
