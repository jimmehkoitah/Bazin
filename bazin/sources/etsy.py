"""Etsy Open API v3: shops as candidates, active listings as observations.

discover      GET /v3/application/listings/active?keywords=&limit=&includes=Shop,Images  (x-api-key header)
fetch_profile GET /v3/application/shops/{shop_id}
              GET /v3/application/shops/{shop_id}/listings/active?includes=Images

`ObservationIn` has no source_json, so a listing's price is written at the start of `caption_excerpt`
("price: 45 USD — <title>") where the price extractor and the S5 classifier will both see it.

Fixture slug rule:
    discover(query)          -> <fixture_dir>/etsy/<slugify(query.query)>.json, a listings/active body
    fetch_profile(candidate) -> <fixture_dir>/etsy/<slugify(candidate.url)>.json,
                                {"shop": {...}, "listings": {...}} — the two response bodies
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..models import Candidate, MediaIn, ObservationIn, ProfileBundle
from .apify import (
    HttpAdapter,
    as_int,
    as_str,
    engagement,
    format_money,
    join_parts,
    parse_dt,
    pick,
    request_json,
)
from .base import DiscoveryQuery, excerpt, slugify

log = logging.getLogger(__name__)

API_BASE = "https://openapi.etsy.com/v3/application"
MAX_LIMIT = 100


def _shop_name_from_url(url: str) -> str | None:
    match = re.search(r"/shop/([A-Za-z0-9_\-]+)", url or "")
    return match.group(1) if match else None


def _listing_price(listing: dict) -> tuple[float | None, str | None]:
    """Etsy money is {amount, divisor, currency_code}; a plain number is tolerated too."""
    price = listing.get("price")
    if isinstance(price, dict):
        amount = as_int(price.get("amount"))
        divisor = as_int(price.get("divisor")) or 100
        value = amount / divisor if amount is not None and divisor else None
        return value, as_str(price.get("currency_code"))
    if price is not None:
        try:
            return float(price), as_str(listing.get("currency_code"))
        except (TypeError, ValueError):
            return None, as_str(listing.get("currency_code"))
    return None, as_str(listing.get("currency_code"))


def _listing_image(listing: dict) -> str | None:
    images = listing.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict):
                url = as_str(pick(image, "url_570xN", "url_fullxfull", "url_680x540", "url"))
                if url:
                    return url
    return as_str(pick(listing, "image_url_570xN", "MainImage"))


def _listing_url(listing: dict) -> str | None:
    url = as_str(listing.get("url"))
    if url:
        return url
    listing_id = as_str(listing.get("listing_id"))
    return f"https://www.etsy.com/listing/{listing_id}" if listing_id else None


class EtsyAdapter(HttpAdapter):
    """Official API. Listing content is refreshed on re-crawl; only our derived tags are kept long-term."""

    name = "etsy"
    platform = "etsy"
    acquisition_method = "official_api"

    def is_configured(self) -> bool:
        return self.fixture_dir is not None or bool(self.settings.etsy_api_key)

    # ---------------------------------------------------------- request building

    def headers(self) -> dict[str, str]:
        return {"x-api-key": self.settings.etsy_api_key or "", "Accept": "application/json"}

    def search_params(self, query: DiscoveryQuery, limit: int) -> dict[str, Any]:
        return {
            "keywords": (query.query or "").strip(),
            "limit": min(limit, MAX_LIMIT),
            "includes": "Shop,Images",
        }

    def shop_listings_params(self, max_posts: int) -> dict[str, Any]:
        return {"limit": min(max_posts, MAX_LIMIT), "includes": "Images", "state": "active"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return request_json("GET", f"{API_BASE}{path}", headers=self.headers(), params=params)

    # ---------------------------------------------------------- mapping

    @staticmethod
    def _shop_of(listing: dict) -> dict:
        shop = listing.get("shop")
        if isinstance(shop, dict):
            return shop
        shop_id = listing.get("shop_id")
        return {"shop_id": shop_id} if shop_id is not None else {}

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        slug = slugify(query.query)
        payload = self.load_or_fetch(
            slug, lambda: self._get("/listings/active", self.search_params(query, limit))
        )
        results = payload.get("results") if isinstance(payload, dict) else None
        listings = [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []
        if not listings:
            return []
        self.store_raw(slug, payload)
        by_shop: dict[str, list[dict]] = {}
        shops: dict[str, dict] = {}
        for listing in listings:
            shop = self._shop_of(listing)
            name = as_str(pick(shop, "shop_name", "shopName"))
            if not name:
                continue
            by_shop.setdefault(name, []).append(listing)
            shops.setdefault(name, shop)
        out: list[Candidate] = []
        for name, shop_listings in by_shop.items():
            shop = shops[name]
            sample_ids = [i for i in (as_str(x.get("listing_id")) for x in shop_listings[:5]) if i]
            out.append(
                Candidate(
                    platform=self.platform,
                    url=f"https://www.etsy.com/shop/{name}",
                    handle=name,
                    external_id=as_str(pick(shop, "shop_id")),
                    title=as_str(pick(shop, "title", "shop_name")) or name,
                    snippet=excerpt(as_str(pick(shop, "announcement", "title"))
                                    or as_str(shop_listings[0].get("title"))),
                    thumbnail_url=_listing_image(shop_listings[0]),
                    source_json={
                        "listing_count_in_results": len(shop_listings),
                        "sample_listing_ids": sample_ids,
                    },
                )
            )
        return out

    def _profile_payload(self, slug: str, candidate: Candidate, max_posts: int) -> dict | None:
        def live() -> dict:
            shop_id = candidate.external_id
            shop_name = candidate.handle or _shop_name_from_url(candidate.url)
            if not shop_id and shop_name:
                found = self._get("/shops", {"shop_name": shop_name, "limit": 1})
                results = (found or {}).get("results") or []
                if results and isinstance(results[0], dict):
                    shop_id = as_str(results[0].get("shop_id"))
            if not shop_id:
                return {}
            shop = self._get(f"/shops/{shop_id}")
            listings = self._get(f"/shops/{shop_id}/listings/active", self.shop_listings_params(max_posts))
            return {"shop": shop, "listings": listings}

        payload = self.load_or_fetch(slug, live)
        return payload if isinstance(payload, dict) else None

    def _observation(self, listing: dict, raw_ref: str | None) -> ObservationIn | None:
        url = _listing_url(listing)
        if not url:
            return None
        amount, currency = _listing_price(listing)
        money = format_money(amount, currency)
        title = as_str(listing.get("title"))
        caption = join_parts([f"price: {money}" if money else None, title])
        image = _listing_image(listing)
        return ObservationIn(
            platform=self.platform,
            source_url=url,
            kind="listing",
            external_id=as_str(listing.get("listing_id")),
            published_at=parse_dt(
                pick(listing, "original_creation_timestamp", "creation_timestamp", "created_timestamp")
            ),
            caption_excerpt=excerpt(caption),
            hashtags=[],
            mentions=[],
            language=as_str(listing.get("language")),
            engagement=engagement(
                views=as_int(listing.get("views")),
                num_favorers=as_int(listing.get("num_favorers")),
            ),
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=[MediaIn(media_url=image, thumbnail_url=image)] if image else [],
        )

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        slug = slugify(candidate.url)
        payload = self._profile_payload(slug, candidate, max_posts)
        if not payload:
            return None
        shop = payload.get("shop") if isinstance(payload.get("shop"), dict) else {}
        if isinstance(shop.get("results"), list) and shop["results"]:
            shop = shop["results"][0]
        listings_body = payload.get("listings") if isinstance(payload.get("listings"), dict) else {}
        results = listings_body.get("results") if isinstance(listings_body, dict) else None
        listings = [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []
        if not shop and not listings:
            return None
        raw_ref = self.store_raw(slug, payload)
        shop_name = as_str(pick(shop, "shop_name")) or candidate.handle or _shop_name_from_url(candidate.url)
        bio = join_parts(
            [as_str(pick(shop, "announcement")), as_str(pick(shop, "title")), as_str(pick(shop, "sale_message"))],
            sep=" · ",
        )
        observations = [
            obs for obs in (self._observation(x, raw_ref) for x in listings[:max_posts]) if obs is not None
        ]
        return ProfileBundle(
            platform=self.platform,
            url=f"https://www.etsy.com/shop/{shop_name}" if shop_name else candidate.url,
            handle=shop_name,
            external_id=as_str(pick(shop, "shop_id")) or candidate.external_id,
            display_name=as_str(pick(shop, "shop_name", "title")),
            bio=excerpt(bio, 600),
            bio_link=as_str(pick(shop, "url", "website")),
            followers=as_int(pick(shop, "num_favorers")),
            observations=observations,
            raw_ref=raw_ref,
        )
