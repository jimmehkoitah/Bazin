"""First-party product feeds: `https://<domain>/products.json`, the Shopify JSON endpoint.

The discovery query is a store domain (`mamagetzner.com`). robots.txt is fetched first and honoured for
the `*` agent; a store that disallows /products.json is still returned as a candidate (its home page is
public) but yields no observations.

`/products.json` carries no currency, so it is read from `/meta.json` when the store exposes one, then
from a variant's `presentment_prices`. A listing caption is written
"price: <min variant price> <currency> — <title> — <first 120 chars of the body>" so the price extractor
and the S5 classifier see the price without another fetch.

Fixture slug rule: both discover and fetch_profile key on the DOMAIN, `slugify(domain)`, so one file
serves both (`mamagetzner.com` and `https://mamagetzner.com/` -> mamagetzner-com.json). The file holds
`{"robots_txt": "...", "meta": {...}, "products": {"products": [...]}}` — the bodies of the three GETs.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from ..models import Candidate, MediaIn, ObservationIn, ProfileBundle
from .apify import (
    BROWSER_HEADERS,
    HttpAdapter,
    as_float,
    as_str,
    fetch_text,
    format_money,
    join_parts,
    parse_dt,
    pick,
    request_json,
    robots_allows,
    strip_html,
)
from .base import DiscoveryQuery, excerpt, slugify

log = logging.getLogger(__name__)

MAX_PRODUCTS = 250
BODY_CHARS = 120


def store_domain(text: str) -> str | None:
    """'mamagetzner.com', 'https://mamagetzner.com/' and 'www.mamagetzner.com' all give the same host."""
    value = (text or "").strip()
    if not value:
        return None
    if "//" not in value:
        value = "https://" + value
    host = (urlparse(value).hostname or "").lower().removeprefix("www.")
    return host or None


class ShopifyAdapter(HttpAdapter):
    """Compliant first-party feed: no credentials, robots.txt honoured, excerpts only."""

    name = "shopify"
    platform = "shopify"
    acquisition_method = "feed"

    def is_configured(self) -> bool:
        return True

    # ---------------------------------------------------------- request building

    @staticmethod
    def products_url(domain: str) -> str:
        return f"https://{domain}/products.json"

    @staticmethod
    def robots_url(domain: str) -> str:
        return f"https://{domain}/robots.txt"

    @staticmethod
    def meta_url(domain: str) -> str:
        return f"https://{domain}/meta.json"

    def products_params(self, limit: int) -> dict[str, Any]:
        return {"limit": min(max(limit, 1), MAX_PRODUCTS)}

    def _fetch_store(self, domain: str, limit: int) -> dict:
        robots = fetch_text(self.robots_url(domain), headers=BROWSER_HEADERS)
        products_url = self.products_url(domain)
        if not robots_allows(robots, products_url):
            log.info("shopify: robots.txt disallows %s", products_url)
            return {"robots_txt": robots, "blocked": True, "products": None}
        meta: Any = None
        try:
            meta = request_json("GET", self.meta_url(domain), headers=BROWSER_HEADERS)
        except (httpx.HTTPError, ValueError) as exc:  # /meta.json is optional
            log.debug("shopify: no meta.json for %s (%s)", domain, exc)
        products = request_json(
            "GET", products_url, headers=BROWSER_HEADERS, params=self.products_params(limit)
        )
        return {"robots_txt": robots, "meta": meta, "products": products}

    def _store_payload(self, domain: str, limit: int) -> dict | None:
        payload = self.load_or_fetch(slugify(domain), lambda: self._fetch_store(domain, limit))
        return payload if isinstance(payload, dict) else None

    # ---------------------------------------------------------- mapping

    def _blocked(self, payload: dict, domain: str) -> bool:
        if payload.get("blocked"):
            return True
        return not robots_allows(payload.get("robots_txt"), self.products_url(domain))

    @staticmethod
    def _products(payload: dict) -> list[dict]:
        products = payload.get("products")
        if isinstance(products, dict):
            products = products.get("products")
        return [p for p in products if isinstance(p, dict)] if isinstance(products, list) else []

    @staticmethod
    def _currency(payload: dict, products: list[dict]) -> str | None:
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        currency = as_str(pick(meta, "currency", "currency_code", "moneyFormat"))
        if currency and len(currency) <= 3:
            return currency.upper()
        for product in products:
            for variant in product.get("variants") or []:
                if not isinstance(variant, dict):
                    continue
                presentment = variant.get("presentment_prices")
                if isinstance(presentment, list) and presentment:
                    price = presentment[0].get("price") if isinstance(presentment[0], dict) else None
                    code = as_str(price.get("currency_code")) if isinstance(price, dict) else None
                    if code:
                        return code.upper()
        return None

    @staticmethod
    def _shop_name(payload: dict, products: list[dict], domain: str) -> str:
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        name = as_str(pick(meta, "name", "shop_name", "title"))
        if name:
            return name
        shop = payload.get("shop") if isinstance(payload.get("shop"), dict) else {}
        name = as_str(pick(shop, "name", "title"))
        if name:
            return name
        vendors = [as_str(p.get("vendor")) for p in products]
        vendors = [v for v in vendors if v]
        if vendors and len(set(vendors)) == 1:
            return vendors[0]
        return domain

    @staticmethod
    def _min_price(product: dict) -> float | None:
        prices = [as_float(v.get("price")) for v in product.get("variants") or [] if isinstance(v, dict)]
        prices = [p for p in prices if p is not None]
        return min(prices) if prices else None

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        domain = store_domain(query.query)
        if not domain:
            return []
        payload = self._store_payload(domain, limit)
        if payload is None:  # fixture mode with no recorded store
            return []
        products: list[dict] = []
        if not self._blocked(payload, domain):
            products = self._products(payload)
            self.store_raw(slugify(domain), payload)
        name = self._shop_name(payload, products, domain)
        return [
            Candidate(
                platform=self.platform,
                url=f"https://{domain}/",
                handle=domain,
                title=name,
                snippet=excerpt(as_str(pick(payload, "description"))),
                source_json={"domain": domain, "product_count_in_results": len(products)},
            )
        ]

    def _observation(
        self, product: dict, domain: str, currency: str | None, raw_ref: str | None
    ) -> ObservationIn | None:
        handle = as_str(product.get("handle"))
        if not handle:
            return None
        title = as_str(product.get("title"))
        money = format_money(self._min_price(product), currency)
        body = strip_html(as_str(product.get("body_html")), limit=BODY_CHARS)
        caption = join_parts([f"price: {money}" if money else None, title, body])
        images = product.get("images") if isinstance(product.get("images"), list) else []
        first = next((i for i in images if isinstance(i, dict) and i.get("src")), None)
        media: list[MediaIn] = []
        if first:
            src = as_str(first.get("src"))
            if src:
                media.append(
                    MediaIn(
                        media_url=src,
                        thumbnail_url=src,
                        width=first.get("width") if isinstance(first.get("width"), int) else None,
                        height=first.get("height") if isinstance(first.get("height"), int) else None,
                    )
                )
        return ObservationIn(
            platform=self.platform,
            source_url=f"https://{domain}/products/{handle}",
            kind="listing",
            external_id=as_str(product.get("id")),
            published_at=parse_dt(pick(product, "published_at", "created_at", "updated_at")),
            caption_excerpt=excerpt(caption),
            hashtags=[],
            mentions=[],
            language=None,
            engagement={},
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=media,
        )

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        domain = store_domain(candidate.handle or candidate.url)
        if not domain:
            return None
        payload = self._store_payload(domain, MAX_PRODUCTS)
        if not payload:
            return None
        if self._blocked(payload, domain):
            log.info("shopify: %s disallows the product feed; no observations", domain)
            return None
        products = self._products(payload)
        if not products:
            return None
        raw_ref = self.store_raw(slugify(domain), payload)
        currency = self._currency(payload, products)
        observations = [
            obs
            for obs in (self._observation(p, domain, currency, raw_ref) for p in products[:max_posts])
            if obs is not None
        ]
        return ProfileBundle(
            platform=self.platform,
            url=f"https://{domain}/",
            handle=domain,
            external_id=None,
            display_name=self._shop_name(payload, products, domain),
            bio=excerpt(self._shop_name(payload, products, domain), 600),
            bio_link=f"https://{domain}/",
            followers=None,
            observations=observations,
            raw_ref=raw_ref,
        )
