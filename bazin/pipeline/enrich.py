"""S4. Profile enrichment: structured business facts from bio, captions and thumbnails, with evidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import h3

from ..db import execute, fetch_all, fetch_one
from ..hubs import load_hubs
from ..llm.client import LLM, BatchItem
from ..llm.prompts import ENRICH_SYSTEM_TEMPLATE, concept_catalogue
from ..models import Enrichment
from ..prices import to_usd
from ..taxonomy import normalize, taxonomy
from .identity import extract_phones, website_host

log = logging.getLogger(__name__)


@dataclass
class EnrichStats:
    enriched: int = 0
    failed: int = 0


def business_text(conn, business_id: str, max_captions: int = 30, max_images: int = 5) -> tuple[str, list[str]]:
    idents = fetch_all(conn, "select * from identities where business_id = %s order by is_primary desc, followers desc nulls last", (business_id,))
    obs = fetch_all(
        conn,
        """
        select o.platform, o.kind, o.caption_excerpt, o.hashtags, o.published_at, o.source_url,
               (select coalesce(thumbnail_url, media_url) from media_refs m where m.observation_id = o.id limit 1) as thumb
        from observations o where o.business_id = %s order by o.published_at desc nulls last limit %s
        """,
        (business_id, max_captions),
    )
    lines: list[str] = []
    for i, ident in enumerate(idents):
        lines += [
            f"Identity {i + 1}: {ident['platform']} {ident['url']}",
            f"Handle: {ident['handle'] or ''}",
            f"Name: {ident['display_name'] or ''}",
            f"Bio: {ident['bio'] or ''}",
            f"Link: {ident['bio_link'] or ''}",
            f"Followers: {ident['followers'] or 'unknown'}",
        ]
    lines.append("Recent content:")
    thumbs: list[str] = []
    for o in obs:
        date = o["published_at"].date().isoformat() if o["published_at"] else "undated"
        tags = " ".join(f"#{h}" for h in (o["hashtags"] or [])[:8])
        lines.append(f"- [{date}] ({o['platform']} {o['kind']}) {o['caption_excerpt'] or ''} {tags}".strip())
        if o["thumb"] and len(thumbs) < max_images:
            thumbs.append(o["thumb"])
    return "\n".join(lines), thumbs


def pending_businesses(conn, limit: int = 200) -> list[str]:
    rows = fetch_all(
        conn,
        """
        select b.id from businesses b
        where b.status in ('candidate','active') and b.description is null
          and exists (select 1 from identities i join candidates c on c.identity_id = i.id where i.business_id = b.id and c.relevant = true)
        order by b.first_seen_at limit %s
        """,
        (limit,),
    )
    return [str(r["id"]) for r in rows]


def _geocode(city: str | None, country: str | None) -> tuple[float | None, float | None]:
    if not city:
        return None, None
    for h in load_hubs()[0]:
        if normalize(h.city) == normalize(city) and (not country or h.country == country):
            return h.lat, h.lon
    return None, None


def persist(conn, business_id: str, e: Enrichment) -> None:
    languages = sorted({l.lower()[:2] for l in e.languages if l})
    primary_country = next((l.country for l in e.locations if l.kind != "ships_to" and l.country), None)
    execute(
        conn,
        """
        update businesses set canonical_name = %s, business_type = %s, business_type_confidence = %s, description = %s,
          languages = %s, primary_country = coalesce(%s, primary_country), status = case when status = 'candidate' then 'active' else status end,
          updated_at = now()
        where id = %s
        """,
        (e.canonical_name[:120], e.business_type, e.business_type_confidence, e.summary, languages, primary_country, business_id),
    )
    for loc in e.locations:
        if loc.confidence < 0.3:
            continue
        lat, lon = _geocode(loc.city, loc.country)
        execute(
            conn,
            """
            insert into locations (business_id, kind, country, city, address, lat, lon, h3_r5, h3_r7, confidence)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (business_id, kind, coalesce(country, ''), coalesce(city, '')) do update set
              address = coalesce(excluded.address, locations.address), confidence = greatest(locations.confidence, excluded.confidence),
              lat = coalesce(locations.lat, excluded.lat), lon = coalesce(locations.lon, excluded.lon),
              h3_r5 = coalesce(locations.h3_r5, excluded.h3_r5), h3_r7 = coalesce(locations.h3_r7, excluded.h3_r7)
            """,
            (
                business_id, loc.kind, loc.country, loc.city, loc.address, lat, lon,
                h3.latlng_to_cell(lat, lon, 5) if lat is not None else None,
                h3.latlng_to_cell(lat, lon, 7) if lat is not None else None,
                loc.confidence,
            ),
        )
    for c in e.ships_to:
        c = c.upper()[:2]
        execute(
            conn,
            "insert into locations (business_id, kind, country, confidence) values (%s, 'ships_to', %s, 0.6) on conflict (business_id, kind, coalesce(country, ''), coalesce(city, '')) do nothing",
            (business_id, c),
        )
    for ch in e.contact_channels:
        norm = ch.value.strip()
        if ch.kind in ("phone", "whatsapp"):
            found = extract_phones(ch.value, primary_country)
            if not found:
                continue
            norm = found[0]
        elif ch.kind == "email":
            norm = ch.value.strip().lower()
        elif ch.kind == "website":
            norm = website_host(ch.value) or ch.value.strip().lower()
        else:
            norm = ch.value.strip().lower()
        execute(
            conn,
            "insert into contact_channels (business_id, kind, value, normalized_value) values (%s, %s, %s, %s) on conflict (business_id, kind, normalized_value) do nothing",
            (business_id, ch.kind, ch.value[:200], norm[:200]),
        )
    for o in e.offers:
        execute(
            conn,
            "insert into offers (business_id, garment_concept_id, fabric_concept_id, gender, custom_or_ready, lead_time_days, evidence) values (%s, %s, %s, %s, %s, %s, %s)",
            (business_id, _known(o.garment_concept_id), _known(o.fabric_concept_id), o.gender, o.custom_or_ready, o.lead_time_days, o.evidence[:200]),
        )
    for p in e.prices:
        amt = p.amount_min if p.amount_min is not None else p.amount_max
        execute(
            conn,
            """
            insert into prices (business_id, price_type, currency, amount_min, amount_max, unit, includes_fabric, includes_embroidery,
                                includes_tailoring, is_promo, currency_inferred, usd_equivalent, evidence)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (business_id, p.price_type, p.currency.upper()[:3], p.amount_min, p.amount_max, p.unit, p.includes_fabric, p.includes_embroidery,
             p.includes_tailoring, p.is_promo, p.currency_inferred, to_usd(amt, p.currency), p.evidence[:200]),
        )
    # Evidence rows the scorer reads.
    if any(c.kind in ("phone", "whatsapp") for c in e.contact_channels):
        _evidence(conn, business_id, "phone_number", "Phone or WhatsApp number published in profile")
    if any(c.kind == "website" for c in e.contact_channels):
        _evidence(conn, business_id, "website", "Website linked from profile")
    if any(l.address for l in e.locations):
        _evidence(conn, business_id, "physical_address", "Street address published")
    if e.prices:
        _evidence(conn, business_id, "pricing_clarity", f"{len(e.prices)} price(s) stated publicly")


def _known(concept_id: str | None) -> str | None:
    return concept_id if concept_id and concept_id in taxonomy().concepts else None


def _evidence(conn, business_id: str, kind: str, claim: str) -> None:
    exists = fetch_one(conn, "select 1 from evidence where business_id = %s and kind = %s and collected_by = 'enrich' limit 1", (business_id, kind))
    if not exists:
        execute(
            conn,
            "insert into evidence (business_id, kind, polarity, extracted_claim, confidence, collected_by) values (%s, %s, 1, %s, 0.8, 'enrich')",
            (business_id, kind, claim[:300]),
        )


def enrich(conn, llm: LLM, limit: int = 200, use_images: bool = True) -> EnrichStats:
    stats = EnrichStats()
    ids = pending_businesses(conn, limit)
    if not ids:
        return stats
    system = ENRICH_SYSTEM_TEMPLATE.format(catalogue=concept_catalogue(taxonomy(), ("fabric", "garment", "technique", "occasion", "style")))
    items = []
    for bid in ids:
        text, thumbs = business_text(conn, bid)
        items.append(BatchItem(custom_id=bid, user_text=text, images=thumbs if use_images else []))
    results = llm.run_batch("enrich", items, Enrichment, system=system, effort="high", max_tokens=6000)
    for bid, res in results.items():
        if isinstance(res, Exception):
            log.warning("enrich failed for %s: %s", bid, res)
            stats.failed += 1
            continue
        persist(conn, bid, res)
        stats.enriched += 1
    return stats
