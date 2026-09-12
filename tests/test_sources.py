"""Source adapter tests.

Everything runs in fixture mode: `build_adapters(..., fixture_dir=tests/fixtures)` makes each adapter
read `<fixture_dir>/<adapter name>/<slug>.json` instead of calling its vendor, and the `no_network`
fixture below replaces httpx's transport with something that raises, so a missing short-circuit shows up
as a failed test rather than a silent request.

Slug rule under test: `slugify(query.query)` for discover, `slugify(candidate.url)` for fetch_profile
(`slugify(domain)` for Shopify, where one file serves both).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from bazin.config import Settings
from bazin.models import Candidate, ProfileBundle
from bazin.prices import parse_prices
from bazin.sources.apify import ApifyClient, format_money, parse_dt, robots_allows
from bazin.sources.base import DiscoveryQuery, RawStore, SourceAdapter, slugify
from bazin.sources.overture import bbox, hub_id_of
from bazin.sources.registry import (
    ADAPTER_CLASSES,
    build_adapters,
    configured_adapters,
    missing_credentials,
    web_search_adapter,
)
from bazin.sources.shopify import store_domain
from bazin.sources.urls import is_profile_url

FIXTURES = Path(__file__).parent / "fixtures"
KEYLESS = {
    "apify_token": None,
    "brave_api_key": None,
    "google_cse_key": None,
    "google_cse_cx": None,
    "youtube_api_key": None,
    "etsy_api_key": None,
    "yelp_api_key": None,
}

# (tool, query, platform, market, language, url prefix the candidates must carry)
DISCOVER_CASES = [
    ("apify_instagram", "#bazinriche", "instagram", "SN", None, "https://www.instagram.com/"),
    ("apify_tiktok", "#bazinriche", "tiktok", "SN", None, "https://www.tiktok.com/@"),
    ("apify_facebook", "bazin getzner Dakar", "facebook", "SN", "fr", "https://www.facebook.com/"),
    ("apify_google_maps", "tailleur bazin Dakar", "google_maps", "SN", "fr", "https://www.google.com/maps/"),
    ("brave", "tailleur bazin Dakar", "web", "SN", "fr", "https://"),
    ("google_cse", "tailleur bazin Dakar", "web", "SN", "fr", "https://"),
    ("youtube", "couture bazin", "youtube", "SN", "fr", "https://www.youtube.com/channel/"),
    ("etsy", "bazin riche", "etsy", None, "en", "https://www.etsy.com/shop/"),
    ("overture", "tailor|fabric|clothes|textile @dakar", "osm", "SN", None, "https://www.openstreetmap.org/"),
    ("shopify", "mamagetzner.com", "shopify", "FR", None, "https://mamagetzner.com/"),
]

# (tool, platform, profile url, handle, expected observation kinds)
PROFILE_CASES = [
    ("apify_instagram", "instagram", "https://www.instagram.com/atelier.khadija.dakar/",
     "atelier.khadija.dakar", {"post", "reel"}),
    ("apify_tiktok", "tiktok", "https://www.tiktok.com/@bazin.atelier.bko", "bazin.atelier.bko", {"video"}),
    ("apify_facebook", "facebook", "https://www.facebook.com/atelierbazindakar/", "atelierbazindakar", {"post"}),
    ("apify_google_maps", "google_maps",
     "https://www.google.com/maps/place/?q=place_id:ChIJSbLnDakarBazin0001", None, {"map_place"}),
    ("youtube", "youtube", "https://www.youtube.com/channel/UCk8p2Xb3DakarBazin00012", None, {"video"}),
    ("etsy", "etsy", "https://www.etsy.com/shop/BazinRicheParis", "BazinRicheParis", {"listing"}),
    ("overture", "osm", "https://www.openstreetmap.org/node/4821990331", None, {"map_place"}),
    ("shopify", "shopify", "https://mamagetzner.com/", "mamagetzner.com", {"listing"}),
    ("website", "website", "https://atelierkhadija.sn/", None, {"page"}),
]

# Adapters whose observations must carry a thumbnail or product image.
MEDIA_REQUIRED = {"apify_instagram", "apify_tiktok", "apify_facebook", "youtube", "etsy", "shopify", "website"}
# Adapters whose observations must carry a date (map places and OSM nodes have none).
DATED = {"apify_instagram", "apify_tiktok", "apify_facebook", "youtube", "etsy", "shopify"}


# ---------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any real HTTP call fails the test that made it."""

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("adapter attempted a network call in fixture mode")

    monkeypatch.setattr(httpx.Client, "request", boom)
    monkeypatch.setattr(httpx.Client, "send", boom)


@pytest.fixture
def settings() -> Settings:
    """No credentials, and no .env: adapters must lean on fixture mode alone."""
    return Settings(_env_file=None, **KEYLESS)


@pytest.fixture
def raw_store(tmp_path: Path) -> RawStore:
    return RawStore(tmp_path / "raw")


@pytest.fixture
def adapters(settings: Settings, raw_store: RawStore) -> dict[str, SourceAdapter]:
    return build_adapters(settings, raw_store, FIXTURES)


# ---------------------------------------------------------------- helpers


def query_for(tool: str, text: str, platform: str, market: str | None, language: str | None) -> DiscoveryQuery:
    return DiscoveryQuery(id=None, query=text, platform=platform, tool=tool, market=market, language=language)


def check_observations(bundle: ProfileBundle, adapter: SourceAdapter, kinds: set[str]) -> None:
    tool = adapter.name
    assert bundle.observations, f"{tool}: no observations"
    for obs in bundle.observations:
        assert obs.platform == bundle.platform
        assert obs.kind in kinds, f"{tool}: unexpected kind {obs.kind}"
        assert obs.source_url.startswith("http")
        assert obs.caption_excerpt is None or len(obs.caption_excerpt) <= 300
        assert obs.raw_ref and obs.raw_ref.startswith("file:"), f"{tool}: observation without raw_ref"
        assert obs.acquisition_method == adapter.acquisition_method
        for tag in obs.hashtags:
            assert tag == tag.lower() and not tag.startswith("#"), f"{tool}: bad hashtag {tag!r}"
        for mention in obs.mentions:
            assert mention == mention.lower() and not mention.startswith("@")
        if obs.published_at is not None:
            assert obs.published_at.tzinfo is not None, f"{tool}: naive datetime"
        if tool in DATED:
            assert obs.published_at is not None, f"{tool}: observation without a date"
        if tool in MEDIA_REQUIRED:
            assert obs.media, f"{tool}: observation without media"
            for media in obs.media:
                assert media.media_url.startswith("http")


# ---------------------------------------------------------------- registry


def test_registry_covers_every_tool(adapters: dict[str, SourceAdapter]) -> None:
    assert set(adapters) == {
        "apify_instagram", "apify_tiktok", "apify_facebook", "apify_google_maps",
        "brave", "google_cse", "youtube", "etsy", "overture", "shopify", "website",
    }
    assert len(adapters) == len(ADAPTER_CLASSES)
    for name, adapter in adapters.items():
        assert adapter.name == name
        assert adapter.fixture_dir == FIXTURES


def test_fixture_mode_configures_everything(adapters: dict[str, SourceAdapter]) -> None:
    assert missing_credentials(adapters) == []
    assert set(configured_adapters(adapters)) == set(adapters)


def test_platforms_and_methods(adapters: dict[str, SourceAdapter]) -> None:
    expected = {
        "apify_instagram": ("instagram", "third_party_scraper"),
        "apify_tiktok": ("tiktok", "third_party_scraper"),
        "apify_facebook": ("facebook", "third_party_scraper"),
        "apify_google_maps": ("google_maps", "third_party_scraper"),
        "brave": ("web", "serp"),
        "google_cse": ("web", "serp"),
        "youtube": ("youtube", "official_api"),
        "etsy": ("etsy", "official_api"),
        "overture": ("osm", "open_data"),
        "shopify": ("shopify", "feed"),
        "website": ("website", "first_party_crawl"),
    }
    for name, (platform, method) in expected.items():
        assert (adapters[name].platform, adapters[name].acquisition_method) == (platform, method)


def test_only_profile_platforms_support_profiles(adapters: dict[str, SourceAdapter]) -> None:
    assert not adapters["brave"].supports_profiles()
    assert not adapters["google_cse"].supports_profiles()
    assert adapters["brave"].fetch_profile(Candidate(platform="web", url="https://x.test/")) is None
    for name in ("apify_instagram", "apify_tiktok", "apify_facebook", "apify_google_maps",
                 "youtube", "etsy", "overture", "shopify", "website"):
        assert adapters[name].supports_profiles(), name


# ---------------------------------------------------------------- discovery


@pytest.mark.parametrize(("tool", "text", "platform", "market", "language", "prefix"), DISCOVER_CASES)
def test_discover(
    adapters: dict[str, SourceAdapter],
    tool: str,
    text: str,
    platform: str,
    market: str | None,
    language: str | None,
    prefix: str,
) -> None:
    adapter = adapters[tool]
    candidates = adapter.discover(query_for(tool, text, platform, market, language), limit=50)
    assert candidates, f"{tool}: no candidates from {text!r}"
    for candidate in candidates:
        assert candidate.platform == adapter.platform
        assert candidate.url.startswith(prefix), f"{tool}: {candidate.url}"
        assert is_profile_url(candidate.platform, candidate.url), f"{tool}: {candidate.url} is not a profile"
        assert candidate.snippet is None or len(candidate.snippet) <= 300
        assert isinstance(candidate.source_json, dict)


def test_discover_groups_posts_into_one_candidate_per_profile(adapters: dict[str, SourceAdapter]) -> None:
    """Six Instagram posts by three owners must collapse into three profile candidates."""
    posts = json.loads((FIXTURES / "apify_instagram" / "bazinriche.json").read_text())
    candidates = adapters["apify_instagram"].discover(query_for("apify_instagram", "#bazinriche", "instagram", "SN", None))
    assert len(posts) == 6
    assert len(candidates) == 3
    assert {c.handle for c in candidates} == {"atelier.khadija.dakar", "bazin.by.fatou", "getzner.paris.store"}
    khadija = next(c for c in candidates if c.handle == "atelier.khadija.dakar")
    assert khadija.url == "https://www.instagram.com/atelier.khadija.dakar/"
    assert khadija.source_json["post_count_in_results"] == 3
    assert len(khadija.source_json["sample_post_urls"]) <= 5
    assert all(u.startswith("https://www.instagram.com/p/") for u in khadija.source_json["sample_post_urls"])


def test_tiktok_and_youtube_group_by_author(adapters: dict[str, SourceAdapter]) -> None:
    tiktok = adapters["apify_tiktok"].discover(query_for("apify_tiktok", "#bazinriche", "tiktok", "ML", None))
    assert [c.url for c in tiktok] == [
        "https://www.tiktok.com/@bazin.atelier.bko",
        "https://www.tiktok.com/@dakar.couture.hd",
    ]
    assert tiktok[0].source_json["post_count_in_results"] == 3
    youtube = adapters["youtube"].discover(query_for("youtube", "couture bazin", "youtube", "SN", "fr"))
    assert [c.handle for c in youtube] == ["Dakar Couture TV", "Bamako Mode"]
    assert youtube[0].source_json == {
        "video_count_in_results": 3,
        "sample_video_ids": ["bZn1RicheDkr", "bZn2Brodrie8", "bZn3Teinture"],
    }


def test_brave_returns_web_candidates_with_rank(adapters: dict[str, SourceAdapter]) -> None:
    candidates = adapters["brave"].discover(query_for("brave", "tailleur bazin Dakar", "web", "SN", "fr"))
    assert [c.platform for c in candidates] == ["web"] * len(candidates)
    assert [c.source_json["rank"] for c in candidates] == list(range(1, len(candidates) + 1))
    assert all(c.snippet and len(c.snippet) <= 300 for c in candidates)
    assert candidates[0].url == "https://atelierkhadija.sn/"


def test_google_cse_matches_brave_shape(adapters: dict[str, SourceAdapter]) -> None:
    cse = adapters["google_cse"].discover(query_for("google_cse", "tailleur bazin Dakar", "web", "SN", "fr"))
    assert cse and all(c.platform == "web" and c.title and c.snippet for c in cse)
    assert cse[0].source_json == {"rank": 1}


def test_google_maps_candidates_carry_place_facts(adapters: dict[str, SourceAdapter]) -> None:
    candidates = adapters["apify_google_maps"].discover(
        query_for("apify_google_maps", "tailleur bazin Dakar", "google_maps", "SN", "fr")
    )
    first = candidates[0]
    assert first.url == "https://www.google.com/maps/place/?q=place_id:ChIJSbLnDakarBazin0001"
    assert first.external_id == "ChIJSbLnDakarBazin0001"
    assert first.source_json["category"] == "Tailor"
    assert first.source_json["rating"] == 4.7
    assert first.source_json["reviews_count"] == 128
    assert (round(first.source_json["lat"], 3), round(first.source_json["lon"], 3)) == (14.675, -17.444)
    assert first.source_json["phone"].startswith("+221")


def test_overpass_candidates_carry_tag_subset(adapters: dict[str, SourceAdapter]) -> None:
    candidates = adapters["overture"].discover(
        query_for("overture", "tailor|fabric|clothes|textile @dakar", "osm", "SN", None)
    )
    assert {c.url for c in candidates} >= {
        "https://www.openstreetmap.org/node/4821990331",
        "https://www.openstreetmap.org/way/998877665",
    }
    tags = candidates[0].source_json["tags"]
    assert set(tags) <= {"shop", "craft", "phone", "website", "addr:city", "addr:street"}
    assert tags["shop"] == "tailor"
    # contact:phone / contact:website are folded into the plain keys.
    sandaga = next(c for c in candidates if c.url.endswith("/node/4821990332"))
    assert sandaga.source_json["tags"]["phone"].startswith("+221")
    assert sandaga.source_json["tags"]["website"].startswith("https://")


def test_shopify_discovers_the_store_itself(adapters: dict[str, SourceAdapter]) -> None:
    candidates = adapters["shopify"].discover(query_for("shopify", "mamagetzner.com", "shopify", "FR", None))
    assert len(candidates) == 1
    assert candidates[0].url == "https://mamagetzner.com/"
    assert candidates[0].title == "Mama Getzner"
    assert candidates[0].source_json == {"domain": "mamagetzner.com", "product_count_in_results": 3}


def test_website_adapter_does_not_discover(adapters: dict[str, SourceAdapter]) -> None:
    assert adapters["website"].discover(query_for("website", "https://atelierkhadija.sn/", "website", None, None)) == []


# ---------------------------------------------------------------- profiles


@pytest.mark.parametrize(("tool", "platform", "url", "handle", "kinds"), PROFILE_CASES)
def test_fetch_profile(
    adapters: dict[str, SourceAdapter],
    tool: str,
    platform: str,
    url: str,
    handle: str | None,
    kinds: set[str],
) -> None:
    adapter = adapters[tool]
    bundle = adapter.fetch_profile(Candidate(platform=platform, url=url, handle=handle), max_posts=30)
    assert bundle is not None, f"{tool}: no bundle for {url}"
    assert bundle.platform == adapter.platform
    assert bundle.url.startswith("http")
    assert bundle.bio, f"{tool}: no bio"
    assert len(bundle.bio) <= 600
    assert bundle.raw_ref and bundle.raw_ref.startswith("file:")
    check_observations(bundle, adapter, kinds)


def test_instagram_profile_details(adapters: dict[str, SourceAdapter]) -> None:
    bundle = adapters["apify_instagram"].fetch_profile(
        Candidate(platform="instagram", url="https://www.instagram.com/atelier.khadija.dakar/")
    )
    assert bundle is not None
    assert bundle.handle == "atelier.khadija.dakar"
    assert bundle.followers == 18437
    assert bundle.bio_link == "https://wa.me/221771234567"
    assert "WhatsApp" in bundle.bio and "Getzner" in bundle.bio
    kinds = [o.kind for o in bundle.observations]
    assert kinds.count("reel") == 1 and kinds.count("post") == 3
    first = bundle.observations[0]
    assert first.engagement == {"likes": 2841, "comments": 168}
    assert "bazinriche" in first.hashtags and "tabaski2026" in first.hashtags
    reel = next(o for o in bundle.observations if o.kind == "reel")
    assert reel.engagement["views"] == 48210
    assert reel.mentions == ["sandaga.tissus"]


def test_instagram_discover_then_fetch_profile(adapters: dict[str, SourceAdapter]) -> None:
    """The candidate URL a discover run emits must be the one the profile fixture is keyed by."""
    adapter = adapters["apify_instagram"]
    candidate = next(
        c for c in adapter.discover(query_for("apify_instagram", "#bazinriche", "instagram", "SN", None))
        if c.handle == "atelier.khadija.dakar"
    )
    assert adapter.has_fixture(slugify(candidate.url))
    bundle = adapter.fetch_profile(candidate)
    assert bundle is not None and bundle.url == candidate.url


def test_tiktok_profile_details(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["apify_tiktok"]
    candidate = adapter.discover(query_for("apify_tiktok", "#bazinriche", "tiktok", "ML", None))[0]
    bundle = adapter.fetch_profile(candidate)
    assert bundle is not None
    assert bundle.url == "https://www.tiktok.com/@bazin.atelier.bko"
    assert bundle.followers == 32400
    assert bundle.bio_link == "https://wa.me/22376451208"
    assert "+223 76 45 12 08" in bundle.bio
    assert all(o.language == "fr" for o in bundle.observations)
    assert bundle.observations[0].engagement == {
        "likes": 24100, "comments": 612, "views": 402000, "shares": 1840,
    }


def test_facebook_profile_has_phone_in_bio(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["apify_facebook"]
    candidate = adapter.discover(query_for("apify_facebook", "bazin getzner Dakar", "facebook", "SN", "fr"))[0]
    assert candidate.url == "https://www.facebook.com/atelierbazindakar/"
    bundle = adapter.fetch_profile(candidate)
    assert bundle is not None
    assert "phone: +221 76 401 22 18" in bundle.bio
    assert bundle.followers == 13402
    assert bundle.bio_link == "https://atelierbazindakar.com"
    assert len(bundle.observations) == 3
    assert bundle.observations[0].engagement == {"likes": 412, "comments": 63, "shares": 28}


def test_google_maps_profile_is_one_map_place(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["apify_google_maps"]
    candidate = adapter.discover(
        query_for("apify_google_maps", "tailleur bazin Dakar", "google_maps", "SN", "fr")
    )[0]
    bundle = adapter.fetch_profile(candidate)
    assert bundle is not None
    assert len(bundle.observations) == 1
    observation = bundle.observations[0]
    assert observation.kind == "map_place"
    assert observation.caption_excerpt == (
        "Atelier Khadija Couture — Tailor — Rue 11 x Avenue Blaise Diagne, Dakar, Sénégal"
    )
    assert observation.engagement == {"rating": 4.7, "reviews": 128}
    assert bundle.bio_link == "https://atelierkhadija.sn/"


def test_osm_profile_is_one_map_place(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["overture"]
    candidate = next(
        c for c in adapter.discover(query_for("overture", "tailor|fabric|clothes|textile @dakar", "osm", "SN", None))
        if c.url.endswith("/node/4821990331")
    )
    bundle = adapter.fetch_profile(candidate)
    assert bundle is not None
    assert bundle.platform == "osm"
    assert len(bundle.observations) == 1
    observation = bundle.observations[0]
    assert observation.kind == "map_place"
    assert observation.caption_excerpt == (
        "Atelier Khadija Couture — tailor — Rue 11 x Avenue Blaise Diagne, Dakar"
    )
    assert "shop=tailor" in bundle.bio and "phone=+221 77 123 45 67" in bundle.bio
    assert bundle.bio_link == "https://atelierkhadija.sn/"


def test_youtube_profile_merges_statistics(adapters: dict[str, SourceAdapter]) -> None:
    bundle = adapters["youtube"].fetch_profile(
        Candidate(platform="youtube", url="https://www.youtube.com/channel/UCk8p2Xb3DakarBazin00012")
    )
    assert bundle is not None
    assert bundle.display_name == "Dakar Couture TV"
    assert bundle.followers == 48200
    assert len(bundle.observations) == 3
    first = bundle.observations[0]
    assert first.source_url == "https://www.youtube.com/watch?v=bZn1RicheDkr"
    assert first.engagement == {"views": 184203, "likes": 9120, "comments": 412}
    assert first.caption_excerpt.startswith("Couture bazin riche : grand boubou brodé étape par étape — ")


def test_etsy_listing_captions_lead_with_the_price(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["etsy"]
    candidate = adapter.discover(query_for("etsy", "bazin riche", "etsy", None, "en"))[0]
    bundle = adapter.fetch_profile(candidate)
    assert bundle is not None
    assert bundle.followers == 1842
    assert "Château Rouge" in bundle.bio
    for observation in bundle.observations:
        assert observation.kind == "listing"
        assert observation.caption_excerpt.startswith("price: ")
        assert set(observation.engagement) == {"views", "num_favorers"}
    first = bundle.observations[0]
    assert first.caption_excerpt == "price: 180 EUR — Bazin Riche Getzner Fabric 5 Yards Royal Blue Damask"
    prices = parse_prices(first.caption_excerpt)
    assert prices and prices[0].amount == 180.0 and prices[0].currency == "EUR"


def test_shopify_listing_captions_lead_with_the_price(adapters: dict[str, SourceAdapter]) -> None:
    bundle = adapters["shopify"].fetch_profile(
        Candidate(platform="shopify", url="https://mamagetzner.com/", handle="mamagetzner.com")
    )
    assert bundle is not None
    assert bundle.display_name == "Mama Getzner"
    assert bundle.bio_link == "https://mamagetzner.com/"
    assert len(bundle.observations) == 3
    for observation in bundle.observations:
        assert observation.caption_excerpt.startswith("price: ")
        assert observation.source_url.startswith("https://mamagetzner.com/products/")
        assert "<p>" not in observation.caption_excerpt  # body_html is stripped of tags
    first = bundle.observations[0]
    assert first.caption_excerpt.startswith("price: 189 EUR — Bazin Riche Getzner Bleu Roi")
    prices = parse_prices(first.caption_excerpt)
    assert prices and prices[0].amount == 189.0 and prices[0].currency == "EUR"


def test_website_profile_extracts_contacts_and_links(adapters: dict[str, SourceAdapter]) -> None:
    bundle = adapters["website"].fetch_profile(Candidate(platform="website", url="https://atelierkhadija.sn/"))
    assert bundle is not None
    assert bundle.display_name == "Atelier Khadija"          # schema.org LocalBusiness name
    assert "Rue 11 x Avenue Blaise Diagne, Dakar" in bundle.bio  # schema.org PostalAddress
    assert "tel: +221771234567" in bundle.bio
    assert "email: contact@atelierkhadija.sn" in bundle.bio
    links = bundle.bio.split("links: ", 1)[1].split()
    assert "https://wa.me/221771234567" in links
    assert "https://www.instagram.com/atelier.khadija.dakar/" in links
    assert "https://www.tiktok.com/@atelierkhadija" in links
    assert "https://www.facebook.com/atelierbazindakar/" in links
    assert not any(link.endswith("/mentions-legales") for link in links)
    observation = bundle.observations[0]
    assert observation.kind == "page"
    assert observation.caption_excerpt.startswith("Atelier Khadija — Couture bazin riche à Dakar — ")
    assert observation.media[0].media_url == "https://atelierkhadija.sn/img/atelier-og.jpg"


def test_prices_survive_into_captions(adapters: dict[str, SourceAdapter]) -> None:
    """The FCFA amounts in social captions must still parse after the 300-character trim."""
    bundle = adapters["apify_instagram"].fetch_profile(
        Candidate(platform="instagram", url="https://www.instagram.com/atelier.khadija.dakar/")
    )
    assert bundle is not None
    prices = parse_prices(bundle.observations[0].caption_excerpt)
    assert any(p.currency == "XOF" and p.amount == 150000 for p in prices)


# ---------------------------------------------------------------- raw store


def test_raw_payloads_are_written_once_per_adapter(
    settings: Settings, tmp_path: Path
) -> None:
    root = tmp_path / "raw"
    adapters = build_adapters(settings, RawStore(root), FIXTURES)
    adapters["apify_instagram"].discover(query_for("apify_instagram", "#bazinriche", "instagram", "SN", None))
    bundle = adapters["apify_instagram"].fetch_profile(
        Candidate(platform="instagram", url="https://www.instagram.com/atelier.khadija.dakar/")
    )
    assert bundle is not None
    written = sorted(p.name for p in (root / "apify_instagram").glob("*.json"))
    assert len(written) == 2
    assert written[0].startswith("bazinriche-")
    stored = json.loads((root / "apify_instagram" / written[0]).read_text())
    assert isinstance(stored, list) and len(stored) == 6
    # Observations point at the file the raw store wrote, not at a copy of the caption.
    assert bundle.observations[0].raw_ref == f"file:apify_instagram/{written[1]}"


# ---------------------------------------------------------------- credentials


def test_is_configured_without_keys(settings: Settings, raw_store: RawStore) -> None:
    live = build_adapters(settings, raw_store, None)
    assert set(configured_adapters(live)) == {"overture", "shopify", "website"}
    assert missing_credentials(live) == [
        "apify_facebook", "apify_google_maps", "apify_instagram", "apify_tiktok",
        "brave", "etsy", "google_cse", "youtube",
    ]


def test_is_configured_with_keys(raw_store: RawStore) -> None:
    settings = Settings(
        _env_file=None,
        apify_token="apify_api_token",
        brave_api_key="brave-key",
        google_cse_key="cse-key",
        google_cse_cx="cse-cx",
        youtube_api_key="yt-key",
        etsy_api_key="etsy-key",
        yelp_api_key=None,
    )
    live = build_adapters(settings, raw_store, None)
    assert missing_credentials(live) == []


def test_google_cse_needs_both_key_and_cx(raw_store: RawStore) -> None:
    half = Settings(_env_file=None, **{**KEYLESS, "google_cse_key": "cse-key"})
    assert not build_adapters(half, raw_store, None)["google_cse"].is_configured()
    both = Settings(_env_file=None, **{**KEYLESS, "google_cse_key": "k", "google_cse_cx": "cx"})
    assert build_adapters(both, raw_store, None)["google_cse"].is_configured()


def test_web_search_falls_back_to_google_cse(raw_store: RawStore) -> None:
    none_set = build_adapters(Settings(_env_file=None, **KEYLESS), raw_store, None)
    assert web_search_adapter(none_set) is None

    cse_only = Settings(_env_file=None, **{**KEYLESS, "google_cse_key": "k", "google_cse_cx": "cx"})
    assert web_search_adapter(build_adapters(cse_only, raw_store, None)).name == "google_cse"

    both = Settings(_env_file=None, **{**KEYLESS, "brave_api_key": "b", "google_cse_key": "k",
                                       "google_cse_cx": "cx"})
    assert web_search_adapter(build_adapters(both, raw_store, None)).name == "brave"

    fixtures = build_adapters(Settings(_env_file=None, **KEYLESS), raw_store, FIXTURES)
    assert web_search_adapter(fixtures).name == "brave"


# ---------------------------------------------------------------- request building
#
# Live mode is unreachable from this sandbox, so the request builders are asserted directly.


def test_apify_actor_path_uses_tilde() -> None:
    assert ApifyClient.actor_path("apify/instagram-scraper") == "apify~instagram-scraper"
    assert ApifyClient.actor_path("clockworks/tiktok-scraper") == "clockworks~tiktok-scraper"


def test_instagram_run_inputs(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["apify_instagram"]
    hashtag = adapter.discover_input(query_for("apify_instagram", "#BazinRiche", "instagram", "SN", None), 40)
    assert hashtag["directUrls"] == ["https://www.instagram.com/explore/tags/bazinriche/"]
    assert hashtag["resultsType"] == "posts" and hashtag["resultsLimit"] == 40
    free_text = adapter.discover_input(query_for("apify_instagram", "bazin dakar", "instagram", "SN", None), 10)
    assert free_text["search"] == "bazin dakar" and free_text["searchType"] == "hashtag"
    profile = adapter.profile_input("https://www.instagram.com/atelier.khadija.dakar/", 25)
    assert profile == {
        "directUrls": ["https://www.instagram.com/atelier.khadija.dakar/"],
        "resultsType": "details",
        "resultsLimit": 25,
        "addParentData": False,
    }


def test_tiktok_run_inputs(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["apify_tiktok"]
    hashtag = adapter.discover_input(query_for("apify_tiktok", "#BazinRiche", "tiktok", "ML", None), 30)
    assert hashtag["hashtags"] == ["bazinriche"] and "searchQueries" not in hashtag
    free_text = adapter.discover_input(query_for("apify_tiktok", "tailleur bazin bamako", "tiktok", "ML", "fr"), 30)
    assert free_text["searchQueries"] == ["tailleur bazin bamako"] and "hashtags" not in free_text
    assert adapter.profile_input("bazin.atelier.bko", 20)["profiles"] == ["bazin.atelier.bko"]
    assert adapter.discover_input(query_for("apify_tiktok", "#x", "tiktok", None, None), 5)["resultsPerPage"] == 5


def test_google_maps_run_inputs(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["apify_google_maps"]
    run_input = adapter.discover_input(
        query_for("apify_google_maps", "tailleur bazin Dakar", "google_maps", "SN", "fr"), 25
    )
    assert run_input["searchStringsArray"] == ["tailleur bazin Dakar"]
    assert run_input["maxCrawledPlacesPerSearch"] == 25 and run_input["language"] == "fr"
    candidate = Candidate(platform="google_maps", url="https://www.google.com/maps/place/?q=place_id:ChIJabc")
    assert adapter.profile_input(candidate, "ChIJabc")["placeIds"] == ["ChIJabc"]
    assert adapter.profile_input(candidate, None)["startUrls"] == [{"url": candidate.url}]


def test_facebook_run_inputs(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["apify_facebook"]
    assert adapter.actor == "apify/facebook-pages-scraper"
    assert adapter.posts_actor == "apify/facebook-posts-scraper"
    search = adapter.discover_input(query_for("apify_facebook", "bazin Dakar", "facebook", "SN", "fr"), 15)
    assert search["searchQueries"] == ["bazin Dakar"] and search["resultsLimit"] == 15
    url = "https://www.facebook.com/atelierbazindakar/"
    assert adapter.page_input(url)["startUrls"] == [{"url": url}]
    assert adapter.posts_input(url, 12)["resultsLimit"] == 12


def test_brave_request(adapters: dict[str, SourceAdapter], raw_store: RawStore) -> None:
    adapter = adapters["brave"]
    params = adapter.params(query_for("brave", "tailleur bazin Dakar", "web", "SN", "fr"), 50)
    assert params == {"q": "tailleur bazin Dakar", "count": 20, "country": "SN", "search_lang": "fr"}
    assert adapter.params(query_for("brave", "x", "web", None, None), 5)["count"] == 5
    keyed = build_adapters(Settings(_env_file=None, **{**KEYLESS, "brave_api_key": "secret"}), raw_store, None)
    assert keyed["brave"].headers()["X-Subscription-Token"] == "secret"


def test_google_cse_request(adapters: dict[str, SourceAdapter]) -> None:
    params = adapters["google_cse"].params(query_for("google_cse", "bazin", "web", "FR", "fr"), 50)
    assert params["num"] == 10 and params["gl"] == "FR" and params["lr"] == "lang_fr"
    assert params["q"] == "bazin"


def test_youtube_request(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["youtube"]
    params = adapter.search_params(query_for("youtube", "couture bazin", "youtube", "SN", "fr"), 200)
    assert params["part"] == "snippet" and params["type"] == "video"
    assert params["maxResults"] == 50 and params["relevanceLanguage"] == "fr" and params["regionCode"] == "SN"
    assert adapter.channel_params("UC123")["part"] == "snippet,statistics"
    videos = adapter.channel_videos_params("UC123", 10)
    assert videos["channelId"] == "UC123" and videos["order"] == "date" and videos["maxResults"] == 10
    assert adapter.video_stats_params(["a", "b"]) ["id"] == "a,b"


def test_etsy_request(adapters: dict[str, SourceAdapter], raw_store: RawStore) -> None:
    adapter = adapters["etsy"]
    params = adapter.search_params(query_for("etsy", "bazin riche", "etsy", None, "en"), 500)
    assert params == {"keywords": "bazin riche", "limit": 100, "includes": "Shop,Images"}
    assert adapter.shop_listings_params(10) == {"limit": 10, "includes": "Images", "state": "active"}
    keyed = build_adapters(Settings(_env_file=None, **{**KEYLESS, "etsy_api_key": "etsy-key"}), raw_store, None)
    assert keyed["etsy"].headers()["x-api-key"] == "etsy-key"


def test_overpass_query_building(adapters: dict[str, SourceAdapter]) -> None:
    from bazin.hubs import hub_by_id

    assert hub_id_of("tailor|fabric|clothes|textile @dakar") == "dakar"
    assert hub_id_of("no hub here") is None
    dakar = hub_by_id("dakar")
    south, west, north, east = bbox(dakar)
    assert round(north - south, 4) == round(east - west, 4) == 0.3
    assert south < dakar.lat < north and west < dakar.lon < east
    ql = adapters["overture"].overpass_ql((south, west, north, east), limit=200)
    assert ql.startswith("[out:json][timeout:60];")
    assert 'node["shop"~"^(fabric|tailor|clothes|boutique|textile)$",i]' in ql
    assert 'way["craft"~"^(tailor|dressmaker|embroiderer)$",i]' in ql
    assert '["name"~"(bazin|getzner|couture|tissu|african|boubou|tailleur)",i]' in ql
    assert ql.rstrip().endswith("out body center 200;")
    assert "14.5428,-17.5967,14.8428,-17.2967" in ql
    assert adapters["overture"].element_ql("node", "4821990331").startswith("[out:json]")


def test_unknown_hub_is_not_an_error(adapters: dict[str, SourceAdapter]) -> None:
    assert adapters["overture"].discover(query_for("overture", "tailor @atlantis", "osm", None, None)) == []
    assert adapters["overture"].discover(query_for("overture", "tailor shops", "osm", None, None)) == []


def test_shopify_urls_and_domains(adapters: dict[str, SourceAdapter]) -> None:
    assert store_domain("mamagetzner.com") == "mamagetzner.com"
    assert store_domain("https://www.mamagetzner.com/collections/all") == "mamagetzner.com"
    assert store_domain("") is None
    adapter = adapters["shopify"]
    assert adapter.products_url("mamagetzner.com") == "https://mamagetzner.com/products.json"
    assert adapter.robots_url("mamagetzner.com") == "https://mamagetzner.com/robots.txt"
    assert adapter.products_params(1000) == {"limit": 250}


def test_shopify_honours_a_disallowing_robots_txt(
    settings: Settings, raw_store: RawStore, tmp_path: Path
) -> None:
    fixtures = tmp_path / "fixtures"
    (fixtures / "shopify").mkdir(parents=True)
    payload = json.loads((FIXTURES / "shopify" / "mamagetzner-com.json").read_text())
    payload["robots_txt"] = "User-agent: *\nDisallow: /products.json\nDisallow: /admin\n"
    (fixtures / "shopify" / "blocked-store-com.json").write_text(json.dumps(payload))
    adapter = build_adapters(settings, raw_store, fixtures)["shopify"]
    candidates = adapter.discover(query_for("shopify", "blocked-store.com", "shopify", None, None))
    assert len(candidates) == 1                       # the store is still a candidate
    assert candidates[0].source_json["product_count_in_results"] == 0
    assert adapter.fetch_profile(candidates[0]) is None  # but the feed is not read


def test_website_robots_url(adapters: dict[str, SourceAdapter]) -> None:
    adapter = adapters["website"]
    assert adapter.robots_url("https://atelierkhadija.sn/boutique") == "https://atelierkhadija.sn/robots.txt"
    assert adapter.headers()["User-Agent"].startswith("Mozilla/5.0")


# ---------------------------------------------------------------- live plumbing
#
# The vendors are unreachable from here, so httpx is handed canned responses instead: this is the only
# way to exercise the live URLs, headers and poll loop before someone runs this on a networked machine.


class FakeHttp:
    """Stands in for httpx.Client.request; records every call and replays canned bodies.

    Patched onto the class as an instance, so — unlike a plain function — it is not a descriptor and
    never receives the client as a first argument.
    """

    def __init__(self, route: dict[str, object] | None = None, text: dict[str, str] | None = None):
        self.route = route or {}
        self.text = text or {}
        self.calls: list[dict] = []

    def __call__(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        params: dict | None = None,
        json: object = None,
        data: object = None,
    ) -> httpx.Response:
        self.calls.append(
            {"method": method, "url": url, "headers": headers or {}, "params": params or {},
             "json": json, "data": data}
        )
        request = httpx.Request(method, url)
        for fragment, body in self.route.items():
            if fragment in url:
                return httpx.Response(200, json=body, request=request)
        for fragment, body_text in self.text.items():
            if fragment in url:
                return httpx.Response(200, text=body_text, request=request)
        return httpx.Response(404, text="not found", request=request)

    def urls(self) -> list[str]:
        return [call["url"] for call in self.calls]


def live_adapters(raw_store: RawStore, **keys: str) -> dict[str, SourceAdapter]:
    return build_adapters(Settings(_env_file=None, **{**KEYLESS, **keys}), raw_store, None)


def test_apify_run_is_start_poll_then_dataset(monkeypatch: pytest.MonkeyPatch, raw_store: RawStore) -> None:
    http = FakeHttp({
        "/runs": {"data": {"id": "RUN1", "status": "RUNNING", "defaultDatasetId": "DS1"}},
        "/actor-runs/RUN1": {"data": {"id": "RUN1", "status": "SUCCEEDED", "defaultDatasetId": "DS1"}},
        "/datasets/DS1/items": [
            {"ownerUsername": "Bazin.Dakar", "ownerId": "42", "url": "https://www.instagram.com/p/AAA/"}
        ],
    })
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store, apify_token="apify_api_tok")["apify_instagram"]
    candidates = adapter.discover(query_for("apify_instagram", "#bazinriche", "instagram", "SN", None), limit=20)

    assert [c.url for c in candidates] == ["https://www.instagram.com/bazin.dakar/"]
    assert http.urls() == [
        "https://api.apify.com/v2/acts/apify~instagram-scraper/runs",
        "https://api.apify.com/v2/actor-runs/RUN1",
        "https://api.apify.com/v2/datasets/DS1/items",
    ]
    start, _poll, items = http.calls
    assert start["method"] == "POST" and start["params"] == {"token": "apify_api_tok"}
    assert start["json"]["directUrls"] == ["https://www.instagram.com/explore/tags/bazinriche/"]
    assert items["params"] == {"token": "apify_api_tok", "clean": "true", "limit": 20}


def test_apify_failed_run_raises(monkeypatch: pytest.MonkeyPatch, raw_store: RawStore) -> None:
    from bazin.sources.apify import ApifyError

    http = FakeHttp({
        "/runs": {"data": {"id": "RUN2", "status": "RUNNING", "defaultDatasetId": "DS2"}},
        "/actor-runs/RUN2": {"data": {"id": "RUN2", "status": "FAILED"}},
    })
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store, apify_token="tok")["apify_tiktok"]
    with pytest.raises(ApifyError):
        adapter.discover(query_for("apify_tiktok", "#bazinriche", "tiktok", None, None))


def test_brave_live_request(monkeypatch: pytest.MonkeyPatch, raw_store: RawStore) -> None:
    http = FakeHttp({
        "api.search.brave.com": {"web": {"results": [{"url": "https://x.test/", "title": "X",
                                                     "description": "bazin riche"}]}}
    })
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store, brave_api_key="brave-key")["brave"]
    candidates = adapter.discover(query_for("brave", "bazin Dakar", "web", "SN", "fr"), limit=50)

    assert [c.url for c in candidates] == ["https://x.test/"]
    call = http.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://api.search.brave.com/res/v1/web/search"
    assert call["headers"]["X-Subscription-Token"] == "brave-key"
    assert call["params"] == {"q": "bazin Dakar", "count": 20, "country": "SN", "search_lang": "fr"}


def test_shopify_live_reads_robots_then_the_feed(
    monkeypatch: pytest.MonkeyPatch, raw_store: RawStore
) -> None:
    products = {"products": [{
        "id": 1, "title": "Bazin riche", "handle": "bazin-riche", "body_html": "<p>Getzner</p>",
        "published_at": "2026-04-01T10:00:00+02:00",
        "variants": [{"price": "150.00"}], "images": [{"src": "https://cdn.test/a.jpg"}],
    }]}
    http = FakeHttp(
        route={"/products.json": products, "/meta.json": {"name": "Test Store", "currency": "EUR"}},
        text={"/robots.txt": "User-agent: *\nDisallow: /admin\n"},
    )
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store)["shopify"]
    bundle = adapter.fetch_profile(Candidate(platform="shopify", url="https://teststore.test/"))

    assert http.urls()[:3] == [
        "https://teststore.test/robots.txt",
        "https://teststore.test/meta.json",
        "https://teststore.test/products.json",
    ]
    assert http.calls[2]["params"] == {"limit": 250}
    assert bundle is not None and bundle.display_name == "Test Store"
    assert bundle.observations[0].caption_excerpt == "price: 150 EUR — Bazin riche — Getzner"


def test_website_live_skips_a_disallowed_page(
    monkeypatch: pytest.MonkeyPatch, raw_store: RawStore
) -> None:
    http = FakeHttp(text={"/robots.txt": "User-agent: *\nDisallow: /\n", "/": "<html></html>"})
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store)["website"]
    assert adapter.fetch_profile(Candidate(platform="website", url="https://blocked.test/")) is None
    assert http.urls() == ["https://blocked.test/robots.txt"]  # the page itself is never fetched


def test_overpass_live_posts_the_query(monkeypatch: pytest.MonkeyPatch, raw_store: RawStore) -> None:
    http = FakeHttp({"overpass-api.de": {"elements": [
        {"type": "node", "id": 1, "lat": 14.7, "lon": -17.4, "tags": {"name": "Tissus", "shop": "fabric"}}
    ]}})
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store)["overture"]
    candidates = adapter.discover(query_for("overture", "tailor|fabric @dakar", "osm", "SN", None))

    assert [c.url for c in candidates] == ["https://www.openstreetmap.org/node/1"]
    call = http.calls[0]
    assert call["method"] == "POST" and call["url"] == "https://overpass-api.de/api/interpreter"
    assert "[out:json]" in call["data"]["data"] and "14.5428,-17.5967" in call["data"]["data"]


def test_youtube_live_calls_three_endpoints(monkeypatch: pytest.MonkeyPatch, raw_store: RawStore) -> None:
    http = FakeHttp({
        "/youtube/v3/channels": {"items": [{"id": "UC1", "snippet": {"title": "T", "description": "D"},
                                            "statistics": {"subscriberCount": "10"}}]},
        "/youtube/v3/search": {"items": [{"id": {"videoId": "V1"},
                                          "snippet": {"title": "t", "description": "d",
                                                      "publishedAt": "2026-01-02T03:04:05Z",
                                                      "thumbnails": {"high": {"url": "https://i.test/v.jpg"}}}}]},
        "/youtube/v3/videos": {"items": [{"id": "V1", "statistics": {"viewCount": "9"}}]},
    })
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store, youtube_api_key="yt-key")["youtube"]
    bundle = adapter.fetch_profile(Candidate(platform="youtube", url="https://www.youtube.com/channel/UC1"))

    assert http.urls() == [
        "https://www.googleapis.com/youtube/v3/channels",
        "https://www.googleapis.com/youtube/v3/search",
        "https://www.googleapis.com/youtube/v3/videos",
    ]
    assert all(call["params"]["key"] == "yt-key" for call in http.calls)
    assert http.calls[2]["params"]["id"] == "V1"
    assert bundle is not None and bundle.followers == 10
    assert bundle.observations[0].engagement == {"views": 9}


def test_etsy_live_calls_carry_the_api_key(monkeypatch: pytest.MonkeyPatch, raw_store: RawStore) -> None:
    http = FakeHttp({"/listings/active": {"results": [{
        "listing_id": 1, "title": "Bazin", "shop": {"shop_id": 7, "shop_name": "Boutique"},
        "price": {"amount": 4500, "divisor": 100, "currency_code": "EUR"},
    }]}})
    monkeypatch.setattr(httpx.Client, "request", http)
    adapter = live_adapters(raw_store, etsy_api_key="etsy-key")["etsy"]
    candidates = adapter.discover(query_for("etsy", "bazin riche", "etsy", None, "en"), limit=10)

    assert [c.url for c in candidates] == ["https://www.etsy.com/shop/Boutique"]
    call = http.calls[0]
    assert call["url"] == "https://openapi.etsy.com/v3/application/listings/active"
    assert call["headers"]["x-api-key"] == "etsy-key"
    assert call["params"]["includes"] == "Shop,Images"


def test_transient_failures_are_retried_then_succeed(
    monkeypatch: pytest.MonkeyPatch, raw_store: RawStore
) -> None:
    from bazin.sources import apify as apify_module

    monkeypatch.setattr(apify_module.time, "sleep", lambda _seconds: None)
    attempts = {"n": 0}
    body = {"web": {"results": [{"url": "https://ok.test/", "title": "ok", "description": "d"}]}}

    # A plain function patched onto the class IS a descriptor, so it receives the client as `_client`.
    def flaky(_client: httpx.Client, method: str, url: str, **kwargs: object) -> httpx.Response:
        attempts["n"] += 1
        request = httpx.Request(method, url)
        if attempts["n"] == 1:
            return httpx.Response(503, text="busy", request=request)
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx.Client, "request", flaky)
    adapter = live_adapters(raw_store, brave_api_key="k")["brave"]
    assert [c.url for c in adapter.discover(query_for("brave", "x", "web", None, None))] == ["https://ok.test/"]
    assert attempts["n"] == 2


# ---------------------------------------------------------------- shared helpers


def test_robots_allows() -> None:
    robots = "User-agent: *\nDisallow: /admin\nAllow: /products.json\n"
    assert robots_allows(robots, "https://shop.test/products.json")
    assert not robots_allows(robots, "https://shop.test/admin/orders")
    assert robots_allows(None, "https://shop.test/anything")
    assert robots_allows("", "https://shop.test/anything")


def test_parse_dt_always_returns_aware_datetimes() -> None:
    assert parse_dt("2026-08-14T18:42:11.000Z").isoformat() == "2026-08-14T18:42:11+00:00"
    assert parse_dt(1786867925).tzinfo is not None
    assert parse_dt(1786867925000).year == 2026          # milliseconds
    assert parse_dt("2026-02-12T10:00:00+01:00").utcoffset().seconds == 3600
    assert parse_dt(None) is None and parse_dt("") is None and parse_dt("not a date") is None


def test_format_money_uses_tokens_the_price_parser_knows() -> None:
    assert format_money(150000, "XOF") == "150000 FCFA"
    assert format_money(180.0, "EUR") == "180 EUR"
    assert format_money(45.5, "USD") == "45.50 USD"
    assert format_money(None, "EUR") is None
    parsed = parse_prices(f"price: {format_money(150000, 'XOF')} — grand boubou")
    assert parsed[0].currency == "XOF" and parsed[0].amount == 150000


# ---------------------------------------------------------------- missing fixtures


@pytest.mark.parametrize(("tool", "platform"), [(t, p) for t, _q, p, _m, _l, _u in DISCOVER_CASES])
def test_missing_fixture_is_empty_not_a_request(
    adapters: dict[str, SourceAdapter], tool: str, platform: str
) -> None:
    """No fixture means no candidates — never a live call (the no_network fixture would raise)."""
    assert adapters[tool].discover(query_for(tool, "query with no fixture @nowhere", platform, None, None)) == []


@pytest.mark.parametrize(("tool", "platform", "url"), [(t, p, u) for t, p, u, _h, _k in PROFILE_CASES])
def test_missing_profile_fixture_is_none(
    adapters: dict[str, SourceAdapter], tool: str, platform: str, url: str
) -> None:
    unknown = Candidate(platform=platform, url=url.replace("https://", "https://unknown."), handle="nobody")
    assert adapters[tool].fetch_profile(unknown) is None
