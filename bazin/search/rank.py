"""Hybrid ranking: rank = 0.45·query_match + 0.35·quality + 0.20·geo_fit, over hard-filtered candidates."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..db import fetch_all
from ..hubs import Hub
from ..pipeline.cluster import cosine, hue_to_css
from ..prices import to_usd
from ..taxonomy import taxonomy
from .parse import DIASPORA, WEST_AFRICA, resolve_place
from ..models import ParsedQuery

CONTACT_HREF = {
    "whatsapp": lambda v: "https://wa.me/" + "".join(ch for ch in v if ch.isdigit()),
    "phone": lambda v: "tel:" + v,
    "email": lambda v: "mailto:" + v,
    "website": lambda v: v if v.startswith("http") else "https://" + v,
    "wa_catalog": lambda v: v if v.startswith("http") else "https://" + v,
}


@dataclass
class SearchOptions:
    near: str | None = None
    radius_km: float | None = None
    ships_to: str | None = None
    business_types: list[str] = field(default_factory=list)
    max_usd: float | None = None
    limit: int = 40
    min_local_results: int = 5


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_candidates(conn) -> list[dict[str, Any]]:
    """Everything the ranker needs, one row per eligible business. Small enough to hold in memory at v1 scale."""
    return fetch_all(
        conn,
        """
        select b.id, b.canonical_name, b.business_type, b.primary_country, b.description, b.quality_score, b.text_embedding,
               greatest(b.last_observed_active_at, (select max(o.published_at) from observations o where o.business_id = b.id)) as last_observed_active_at,
               coalesce((select array_agg(concept_id) from business_concepts bc where bc.business_id = b.id), '{}') as concepts,
               coalesce((select jsonb_agg(jsonb_build_object('kind', kind, 'country', country, 'city', city, 'lat', lat, 'lon', lon)) from locations l where l.business_id = b.id), '[]') as locations,
               coalesce((select jsonb_agg(jsonb_build_object('kind', kind, 'value', value)) from contact_channels c where c.business_id = b.id and not c.do_not_contact), '[]') as contacts,
               coalesce((select jsonb_agg(jsonb_build_object('platform', platform, 'url', url, 'handle', handle)) from identities i where i.business_id = b.id), '[]') as identities,
               (select min(usd_equivalent) from prices p where p.business_id = b.id and p.usd_equivalent is not null and p.price_type in ('complete_outfit','tailoring','fabric')) as price_from_usd,
               (select count(*) from evidence e where e.business_id = b.id and e.polarity = 1) as evidence_count,
               (select reasons from scores s where s.business_id = b.id order by computed_at desc limit 1) as reasons,
               (select caveats from scores s where s.business_id = b.id order by computed_at desc limit 1) as caveats,
               (select jsonb_build_object('id', c.id, 'label', c.label, 'hue', c.hue) from business_clusters bc join clusters c on c.id = bc.cluster_id
                  where bc.business_id = b.id and bc.run_id = (select run_id from clusters order by created_at desc limit 1) limit 1) as cluster,
               coalesce((select array_agg(coalesce(m.thumbnail_url, m.media_url)) from (
                  select m.thumbnail_url, m.media_url from media_refs m join observations o on o.id = m.observation_id
                  where o.business_id = b.id order by o.published_at desc nulls last limit 3) m), '{}') as thumbnails,
               coalesce((select array_agg(distinct (c.dominant->>'name')) from (
                  select jsonb_array_elements(m.dominant_colors) as dominant from media_refs m join observations o on o.id = m.observation_id
                  where o.business_id = b.id and m.dominant_colors is not null limit 30) c), '{}') as colors
        from businesses b
        where b.status in ('active','dormant') and b.objection_at is null and b.duplicate_of is null
        """,
    )


def _concept_labels(concept_ids: list[str], tax, limit: int = 12) -> list[str]:
    """Human labels for the card, most specific first, without signal or colour concepts."""
    out: list[str] = []
    for cid in sorted(concept_ids, key=lambda c: -c.count(".")):
        if cid.startswith(("signal.", "color.")) or cid not in tax.concepts:
            continue
        label = tax.concepts[cid].canonical_label
        if label not in out:
            out.append(label)
    return out[:limit]


def concept_overlap(parsed: ParsedQuery, concepts: list[str]) -> float:
    wanted = set(parsed.garment_concept_ids) | set(parsed.fabric_concept_ids) | set(parsed.occasion_ids) | {f"color.{c}" for c in parsed.colors}
    if not wanted:
        return 0.5
    have = set(concepts)
    tax = taxonomy()
    score = 0.0
    for w in wanted:
        if w in have:
            score += 1.0
        elif any(w in tax.ancestors(h) or h in tax.ancestors(w) for h in have):
            score += 0.6
    return score / len(wanted)


def text_match(parsed: ParsedQuery, row: dict[str, Any], query_vec: list[float] | None) -> float:
    sem = cosine(query_vec, row.get("text_embedding")) if query_vec else 0.0
    sem = max(0.0, sem)
    ft = parsed.free_text.lower()
    lexical = 0.0
    if ft:
        doc = f"{row['canonical_name']} {row.get('description') or ''}".lower()
        toks = [t for t in ft.split() if len(t) > 3]
        if toks:
            lexical = sum(1 for t in toks if t in doc) / len(toks)
    return 0.6 * sem + 0.4 * lexical


def geo_fit(row: dict[str, Any], hub: Hub | None, radius_km: float | None, ships_to: str | None) -> tuple[str, float, float | None]:
    locs = row.get("locations") or []
    physical = [l for l in locs if l.get("kind") != "ships_to"]
    ships = {l.get("country") for l in locs if l.get("kind") == "ships_to"}
    if hub is not None:
        best_d = None
        for l in physical:
            if l.get("lat") is not None and l.get("lon") is not None:
                d = haversine_km(hub.lat, hub.lon, float(l["lat"]), float(l["lon"]))
                best_d = d if best_d is None else min(best_d, d)
            elif l.get("country") == hub.country and (l.get("city") or "").lower() == hub.city.lower():
                best_d = 0.0
        if best_d is not None and best_d <= (radius_km or 60.0):
            return "local", 1.0, round(best_d, 1)
        if hub.country in ships or (ships_to and ships_to in ships):
            return "ships_to", 0.6, best_d
        if row.get("primary_country") in WEST_AFRICA and hub.country in DIASPORA:
            return "corridor", 0.4, best_d
        return "none", 0.0, best_d
    if ships_to:
        if any(l.get("country") == ships_to for l in physical):
            return "local", 1.0, None
        if ships_to in ships:
            return "ships_to", 0.8, None
        if row.get("primary_country") in WEST_AFRICA and ships_to in DIASPORA:
            return "corridor", 0.4, None
        return "none", 0.0, None
    return "none", 0.5, None


def search(conn, parsed: ParsedQuery, opts: SearchOptions, query_vec: list[float] | None = None) -> dict[str, Any]:
    hub = resolve_place(opts.near or parsed.location.near)
    ships_to = (opts.ships_to or parsed.location.ships_to or "").upper()[:2] or None
    types = set(opts.business_types or parsed.business_types)
    max_usd = opts.max_usd
    if max_usd is None and parsed.budget:
        max_usd = to_usd(parsed.budget.max, parsed.budget.currency)
    applied = []
    if hub:
        applied.append(f"near {hub.city}" + (f" within {int(opts.radius_km or 60)} km" if hub else ""))
    if ships_to:
        applied.append(f"ships to {ships_to}")
    if types:
        applied.append("type: " + ", ".join(sorted(t.replace("_", " ") for t in types)))
    if max_usd:
        applied.append(f"under ${max_usd:.0f}")
    tax = taxonomy()
    for cid in parsed.garment_concept_ids + parsed.fabric_concept_ids + parsed.occasion_ids:
        if cid in tax.concepts:
            applied.append(tax.concepts[cid].canonical_label)
    for c in parsed.colors:
        applied.append(c)

    rows = load_candidates(conn)
    scored = []
    for r in rows:
        if types and r["business_type"] not in types:
            continue
        if max_usd is not None and r["price_from_usd"] is not None and float(r["price_from_usd"]) > max_usd:
            continue
        fit, gscore, dist = geo_fit(r, hub, opts.radius_km, ships_to)
        if (hub or ships_to) and fit == "none":
            continue
        qm = 0.6 * concept_overlap(parsed, list(r["concepts"])) + 0.4 * text_match(parsed, r, query_vec)
        quality = float(r["quality_score"] or 0.0)
        rank = 0.45 * qm + 0.35 * quality + 0.20 * gscore
        scored.append((rank, fit, dist, r))
    scored.sort(key=lambda t: -t[0])
    notes = []
    locals_ = [s for s in scored if s[1] == "local"]
    if hub and len(locals_) < opts.min_local_results and any(s[1] != "local" for s in scored):
        notes.append(f"Fewer than {opts.min_local_results} local results near {hub.city}; showing vendors that ship to you or work the diaspora corridor.")
    results = []
    cluster_counts: dict[str, dict[str, Any]] = {}
    for rank, fit, dist, r in scored[: opts.limit]:
        cl = r.get("cluster")
        if cl:
            entry = cluster_counts.setdefault(str(cl["id"]), {"id": str(cl["id"]), "label": cl["label"], "hue": cl["hue"], "count": 0})
            entry["count"] += 1
        physical = [l for l in (r["locations"] or []) if l.get("kind") != "ships_to"]
        results.append({
            "id": str(r["id"]),
            "name": r["canonical_name"],
            "business_type": r["business_type"],
            "city": physical[0]["city"] if physical else None,
            "country": physical[0]["country"] if physical else r["primary_country"],
            "score": round(float(r["quality_score"] or 0.0), 3),
            "rank": round(rank, 3),
            "cluster": {"id": str(cl["id"]), "label": cl["label"], "hue": cl["hue"], "css": hue_to_css(cl["hue"])} if cl else None,
            "concepts": _concept_labels(r["concepts"], tax),
            "colors": [c for c in (r["colors"] or []) if c],
            "price_from_usd": float(r["price_from_usd"]) if r["price_from_usd"] is not None else None,
            "ships_to": sorted({l["country"] for l in (r["locations"] or []) if l.get("kind") == "ships_to" and l.get("country")}),
            "contact": [{"kind": c["kind"], "value": c["value"], "href": CONTACT_HREF.get(c["kind"], lambda v: None)(c["value"])} for c in (r["contacts"] or [])],
            "identities": r["identities"] or [],
            "evidence_count": int(r["evidence_count"] or 0),
            "last_active": r["last_observed_active_at"].date().isoformat() if r["last_observed_active_at"] else None,
            "reasons": r["reasons"] or [],
            "caveats": r["caveats"] or [],
            "thumbnails": [t for t in (r["thumbnails"] or []) if t][:3],
            "geo_fit": fit,
            "distance_km": dist,
        })
    return {
        "parsed": parsed.model_dump(),
        "applied_filters": applied,
        "notes": notes,
        "clusters": sorted(cluster_counts.values(), key=lambda c: -c["count"]),
        "results": results,
    }
