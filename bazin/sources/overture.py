"""Open geo data: OpenStreetMap POIs around a hub city, via the Overpass API.

The planner emits one query per hub, shaped `'tailor|fabric|clothes|textile @<hub_id>'`. The hub id
resolves to a centre through `bazin.hubs.hub_by_id` and becomes a bounding box of ±0.15° (roughly 17 km
north-south), which is the right size for a city's textile districts without dragging in a whole region.

Overture Places parquet is the other half of the open-data plan (see spec section 5); this adapter covers
the OSM half, which is why the tool name is `overture` while the platform is `osm` — attribution is ODbL.

Fixture slug rule:
    discover(query)          -> <fixture_dir>/overture/<slugify(query.query)>.json, an Overpass body
                                e.g. 'tailor|fabric|clothes|textile @dakar'
                                     -> tailor-fabric-clothes-textile-dakar.json
    fetch_profile(candidate) -> <fixture_dir>/overture/<slugify(candidate.url)>.json, same shape
"""

from __future__ import annotations

import logging
import re

from ..hubs import Hub, hub_by_id
from ..models import Candidate, ObservationIn, ProfileBundle
from .apify import HttpAdapter, as_float, as_str, join_parts, request_json
from .base import DiscoveryQuery, excerpt, slugify

log = logging.getLogger(__name__)

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
BBOX_DEGREES = 0.15
SHOP_VALUES = ("fabric", "tailor", "clothes", "boutique", "textile")
CRAFT_VALUES = ("tailor", "dressmaker", "embroiderer")
NAME_PATTERN = "(bazin|getzner|couture|tissu|african|boubou|tailleur)"
TAG_KEYS = ("shop", "craft", "phone", "website", "addr:city", "addr:street")
TAG_FALLBACKS = {
    "phone": ("phone", "contact:phone", "contact:mobile", "mobile"),
    "website": ("website", "contact:website", "contact:facebook", "url"),
}
ELEMENT_URL_RE = re.compile(r"openstreetmap\.org/(node|way|relation)/(\d+)")


def bbox(hub: Hub, degrees: float = BBOX_DEGREES) -> tuple[float, float, float, float]:
    """(south, west, north, east) — the order Overpass expects."""
    return (hub.lat - degrees, hub.lon - degrees, hub.lat + degrees, hub.lon + degrees)


def hub_id_of(query: str) -> str | None:
    match = re.search(r"@([A-Za-z0-9_\-]+)", query or "")
    return match.group(1) if match else None


def _tag(tags: dict, key: str) -> str | None:
    for candidate_key in TAG_FALLBACKS.get(key, (key,)):
        value = as_str(tags.get(candidate_key))
        if value:
            return value
    return None


def _element_latlon(element: dict) -> tuple[float | None, float | None]:
    centre = element.get("center") if isinstance(element.get("center"), dict) else {}
    lat = as_float(element.get("lat")) if element.get("lat") is not None else as_float(centre.get("lat"))
    lon = as_float(element.get("lon")) if element.get("lon") is not None else as_float(centre.get("lon"))
    return lat, lon


def _element_url(element: dict) -> str | None:
    etype = as_str(element.get("type")) or "node"
    eid = element.get("id")
    return f"https://www.openstreetmap.org/{etype}/{eid}" if eid is not None else None


class OverpassAdapter(HttpAdapter):
    """One POST per hub; nothing here needs credentials, so it is always configured."""

    name = "overture"
    platform = "osm"
    acquisition_method = "open_data"

    def is_configured(self) -> bool:
        return True

    # ---------------------------------------------------------- request building

    def overpass_ql(self, box: tuple[float, float, float, float], limit: int = 200, timeout: int = 60) -> str:
        """Shops and crafts in the categories we care about, plus anything whose name looks like Bazin."""
        area = "{:.4f},{:.4f},{:.4f},{:.4f}".format(*box)
        shops = "|".join(SHOP_VALUES)
        crafts = "|".join(CRAFT_VALUES)
        clauses: list[str] = []
        for kind in ("node", "way"):
            clauses.append(f'  {kind}["shop"~"^({shops})$",i]({area});')
            clauses.append(f'  {kind}["craft"~"^({crafts})$",i]({area});')
            clauses.append(f'  {kind}["name"~"{NAME_PATTERN}",i]({area});')
        body = "\n".join(clauses)
        return f"[out:json][timeout:{timeout}];\n(\n{body}\n);\nout body center {limit};"

    def element_ql(self, etype: str, eid: str, timeout: int = 30) -> str:
        return f"[out:json][timeout:{timeout}];\n{etype}({eid});\nout body center;"

    def _post(self, ql: str) -> object:
        return request_json("POST", OVERPASS_ENDPOINT, data={"data": ql})

    # ---------------------------------------------------------- mapping

    def _source_json(self, element: dict) -> dict:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        lat, lon = _element_latlon(element)
        values: dict[str, object] = {"lat": lat, "lon": lon}
        subset = {key: _tag(tags, key) for key in TAG_KEYS}
        values["tags"] = {k: v for k, v in subset.items() if v}
        return {k: v for k, v in values.items() if v not in (None, {})}

    def _elements(self, payload: object) -> list[dict]:
        elements = payload.get("elements") if isinstance(payload, dict) else None
        return [e for e in elements if isinstance(e, dict)] if isinstance(elements, list) else []

    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        hub_id = hub_id_of(query.query)
        if not hub_id:
            log.warning("overture: query %r has no @hub_id", query.query)
            return []
        slug = slugify(query.query)
        try:
            hub = hub_by_id(hub_id)
        except KeyError:
            log.warning("overture: unknown hub %r", hub_id)
            return []
        payload = self.load_or_fetch(slug, lambda: self._post(self.overpass_ql(bbox(hub), limit=max(limit, 50))))
        elements = self._elements(payload)
        if not elements:
            return []
        self.store_raw(slug, payload)
        out: list[Candidate] = []
        for element in elements[:limit]:
            url = _element_url(element)
            if not url:
                continue
            tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
            source_json = self._source_json(element)
            kind = _tag(tags, "shop") or _tag(tags, "craft")
            out.append(
                Candidate(
                    platform=self.platform,
                    url=url,
                    external_id=f"{element.get('type')}/{element.get('id')}",
                    title=as_str(tags.get("name")),
                    snippet=excerpt(join_parts([as_str(tags.get("name")), kind, _tag(tags, "addr:street")])),
                    source_json=source_json,
                )
            )
        return out

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        match = ELEMENT_URL_RE.search(candidate.url or "")
        if not match:
            return None
        etype, eid = match.group(1), match.group(2)
        slug = slugify(candidate.url)
        payload = self.load_or_fetch(slug, lambda: self._post(self.element_ql(etype, eid)))
        elements = self._elements(payload)
        if not elements:
            return None
        raw_ref = self.store_raw(slug, payload)
        element = elements[0]
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        name = as_str(tags.get("name"))
        kind = _tag(tags, "shop") or _tag(tags, "craft")
        where = ", ".join(p for p in (_tag(tags, "addr:street"), _tag(tags, "addr:city")) if p) or None
        observation = ObservationIn(
            platform=self.platform,
            source_url=candidate.url,
            kind="map_place",
            external_id=f"{etype}/{eid}",
            published_at=None,
            caption_excerpt=excerpt(join_parts([name, kind, where])),
            hashtags=[],
            mentions=[],
            language=None,
            engagement={},
            raw_ref=raw_ref,
            acquisition_method=self.acquisition_method,
            media=[],
        )
        summary = " · ".join(f"{key}={_tag(tags, key)}" for key in TAG_KEYS if _tag(tags, key)) or None
        return ProfileBundle(
            platform=self.platform,
            url=candidate.url,
            handle=None,
            external_id=f"{etype}/{eid}",
            display_name=name,
            bio=excerpt(summary, 600),
            bio_link=_tag(tags, "website"),
            followers=None,
            observations=[observation],
            raw_ref=raw_ref,
        )
