"""S6. Evidence collection: ratings, cross-platform identity, repeated posting, complaint searches.

Runs in code (no Cotera). Sources used here: map_place observations (Google Maps and OSM ratings), Etsy/Shopify
listing counts, identities, observation flags, and an optional web search for complaints.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..db import execute, fetch_all, fetch_one
from ..sources.base import DiscoveryQuery

log = logging.getLogger(__name__)

COMPLAINT_WORDS = re.compile(r"\b(arnaque|arnaqueur|escroc|escroquerie|scam|scammer|fraud|voleur|jamais livr|never delivered|ripped off|avis n[ée]gatif)\b", re.I)


@dataclass
class EvidenceStats:
    businesses: int = 0
    rows: int = 0


def _add(conn, business_id: str, kind: str, claim: str, *, polarity: int = 1, source_url: str | None = None, rating=None, scale=None, review_count=None, confidence: float = 0.7, collected_by: str = "evidence") -> bool:
    exists = fetch_one(
        conn,
        "select 1 from evidence where business_id = %s and kind = %s and coalesce(source_url, '') = coalesce(%s, '') and extracted_claim = %s limit 1",
        (business_id, kind, source_url, claim[:300]),
    )
    if exists:
        return False
    execute(
        conn,
        """
        insert into evidence (business_id, kind, polarity, source_url, extracted_claim, rating, rating_scale, review_count, confidence, collected_by)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (business_id, kind, polarity, source_url, claim[:300], rating, scale, review_count, confidence, collected_by),
    )
    return True


def collect_for(conn, business_id: str, search_adapter=None) -> int:
    n = 0
    name = fetch_one(conn, "select canonical_name from businesses where id = %s", (business_id,))["canonical_name"]

    # Ratings captured with map places (Google Maps via scraper, OSM has none) and marketplace listings.
    for r in fetch_all(conn, "select source_url, engagement, platform from observations where business_id = %s and kind in ('map_place','listing','page')", (business_id,)):
        eng = r["engagement"] or {}
        rating = eng.get("rating")
        reviews = eng.get("reviews") or eng.get("reviews_count") or eng.get("review_count")
        if rating is not None and reviews:
            n += _add(conn, business_id, "review", f"{r['platform']}: rating {rating}/5 from {reviews} reviews", source_url=r["source_url"], rating=float(rating), scale=5, review_count=int(reviews), confidence=0.85)
        if r["platform"] in ("google_maps", "osm", "yelp"):
            n += _add(conn, business_id, "physical_address", f"Listed as a place on {r['platform']}", source_url=r["source_url"], confidence=0.8)
        if r["platform"] in ("etsy", "afrikrea", "amazon", "jumia", "shopify"):
            n += _add(conn, business_id, "marketplace_listing", f"Storefront on {r['platform']}", source_url=r["source_url"], confidence=0.9)

    # Cross-platform identity and repeated posting.
    platforms = fetch_all(conn, "select distinct platform from identities where business_id = %s", (business_id,))
    if len(platforms) >= 2:
        n += _add(conn, business_id, "cross_platform_identity", "Same business found on " + ", ".join(sorted(p["platform"] for p in platforms)), confidence=0.8)
    posts = fetch_one(conn, "select count(*) as c, count(distinct date_trunc('month', published_at)) as months from observations where business_id = %s and kind in ('post','reel','video','listing')", (business_id,))
    if posts and posts["c"] >= 10 and posts["months"] >= 3:
        n += _add(conn, business_id, "repeated_posting", f"{posts['c']} posts across {posts['months']} months", confidence=0.8)

    # Complaint search, conservative: the vendor name must appear with a complaint word in title or snippet.
    if search_adapter is not None and name and len(name) >= 4:
        try:
            for term in (f'"{name}" arnaque', f'"{name}" scam'):
                cands = search_adapter.discover(DiscoveryQuery(None, term, "web", search_adapter.name), limit=10)
                for c in cands:
                    text = f"{c.title or ''} {c.snippet or ''}"
                    if name.lower() in text.lower() and COMPLAINT_WORDS.search(text):
                        n += _add(conn, business_id, "scam_report", f"Complaint mention: {(c.title or '')[:120]}", polarity=-1, source_url=c.url, confidence=0.5)
        except Exception as e:  # noqa: BLE001
            log.debug("complaint search failed for %s: %s", name, e)
    return n


def collect(conn, limit: int = 500, search_adapter=None) -> EvidenceStats:
    stats = EvidenceStats()
    rows = fetch_all(
        conn,
        "select id from businesses where status in ('active','candidate') order by updated_at desc limit %s",
        (limit,),
    )
    for r in rows:
        stats.rows += collect_for(conn, str(r["id"]), search_adapter)
        stats.businesses += 1
    return stats
