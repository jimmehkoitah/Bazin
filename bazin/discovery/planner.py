"""S1. Discovery planner: taxonomy × hubs × platforms -> discovery_queries rows.

Deterministic. An optional LLM expansion adds colloquial phrasings per (concept, market).
Priority 1 = garment × city × occasion (yields makers), 2 = fabric × city, 3 = generic and feeds.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..db import execute, fetch_one
from ..hubs import Hub, hubs, stores
from ..taxonomy import Taxonomy, hashtag_form, normalize, taxonomy

COUNTRY_NAMES = {
    "SN": {"fr": "Sénégal", "en": "Senegal"},
    "ML": {"fr": "Mali", "en": "Mali"},
    "GN": {"fr": "Guinée", "en": "Guinea"},
    "GM": {"fr": "Gambie", "en": "Gambia"},
    "CI": {"fr": "Côte d'Ivoire", "en": "Ivory Coast"},
    "BJ": {"fr": "Bénin", "en": "Benin"},
    "TG": {"fr": "Togo", "en": "Togo"},
    "NG": {"fr": "Nigeria", "en": "Nigeria"},
    "FR": {"fr": "France", "en": "France"},
    "US": {"fr": "États-Unis", "en": "USA"},
    "GB": {"fr": "Angleterre", "en": "UK"},
    "IT": {"fr": "Italie", "en": "Italy", "it": "Italia"},
    "NL": {"fr": "Pays-Bas", "en": "Netherlands"},
    "BE": {"fr": "Belgique", "en": "Belgium"},
    "ES": {"fr": "Espagne", "en": "Spain", "es": "España"},
    "BF": {"fr": "Burkina Faso", "en": "Burkina Faso"},
    "NE": {"fr": "Niger", "en": "Niger"},
    "MR": {"fr": "Mauritanie", "en": "Mauritania"},
}

# Garment and fabric concepts that anchor discovery queries. Signals and colours are not queried.
DISCOVERY_CONCEPTS = [
    "garment.grand_boubou", "garment.boubou", "garment.taille_basse", "garment.ndoket", "garment.kaftan",
    "garment.bridal", "garment.dress", "garment.womens", "garment.mens",
    "garment.agbada", "garment.babban_riga", "garment.senator",
    "fabric.bazin.riche", "fabric.getzner", "fabric.bazin.guinea_brocade", "technique.dyeing", "technique.embroidery",
]
OCCASIONS = ["occasion.tabaski", "occasion.korite", "occasion.wedding"]
MAKER_WORDS = {
    "fr": ["tailleur", "couturier", "couturière", "atelier de couture", "styliste"],
    "en": ["tailor", "seamstress", "fashion designer", "bespoke"],
    "it": ["sarto africano", "sartoria africana"],
}
SHOP_WORDS = {
    "fr": ["boutique bazin", "vente bazin", "magasin de tissus africains", "tissu africain"],
    "en": ["african fabric store", "bazin fabric shop", "african fabrics", "guinea brocade shop"],
    "it": ["tessuti africani", "negozio tessuti africani"],
}
YOUTUBE_GENERIC = ["couture bazin", "broderie bazin", "modèle bazin 2026", "bazin riche getzner", "grand boubou brodé", "shadda styles", "agbada styles"]
ETSY_KEYWORDS = ["bazin riche", "getzner", "getzner bazin", "grand boubou", "bazin dress", "bazin fabric", "guinea brocade", "boubou men", "african brocade fabric", "shadda fabric"]


@dataclass
class PlannedQuery:
    query: str
    platform: str
    tool: str
    market: str | None
    language: str | None
    priority: int


def _lang(hub: Hub) -> str:
    for l in hub.languages:
        if l in ("fr", "en", "it", "es"):
            return l
    return "en"


def _labels(tax: Taxonomy, concept_id: str, hub: Hub, limit: int = 3) -> list[str]:
    labs = tax.labels_for_market(concept_id, hub.country, hub.languages)
    # Prefer short, single-language labels; keep order stable.
    labs = sorted(dict.fromkeys(labs), key=lambda s: (len(s.split()), len(s)))
    return labs[:limit]


def plan_for_hub(tax: Taxonomy, hub: Hub) -> list[PlannedQuery]:
    out: list[PlannedQuery] = []
    lang = _lang(hub)
    city = hub.city
    cname = COUNTRY_NAMES.get(hub.country, {}).get(lang, hub.country)

    def add(q: str, platform: str, tool: str, priority: int, language: str | None = lang) -> None:
        q = " ".join(q.split())
        if q:
            out.append(PlannedQuery(q, platform, tool, hub.country, language, priority))

    # Web search (Brave / Google CSE): garment × city × occasion first, then fabric × city, then makers and shops.
    for cid in DISCOVERY_CONCEPTS:
        is_garment = cid.startswith("garment.")
        for label in _labels(tax, cid, hub, limit=2):
            add(f"{label} {city}", "web", "brave", 1 if is_garment else 2)
            add(f"{label} {cname}", "web", "brave", 2 if is_garment else 3)
            for site in ("instagram.com", "tiktok.com", "facebook.com"):
                add(f'site:{site} "{label}" {city}', "web", "brave", 2)
            if is_garment:
                for occ in OCCASIONS:
                    for olabel in _labels(tax, occ, hub, limit=1):
                        add(f"{label} {olabel} {city}", "web", "brave", 1)
    for w in MAKER_WORDS.get(lang, MAKER_WORDS["en"]):
        add(f"{w} bazin {city}", "web", "brave", 1)
        add(f"{w} boubou {city}", "web", "brave", 1)
        for area in hub.areas[:3]:
            add(f"{w} bazin {area} {city}", "web", "brave", 1)
    for w in SHOP_WORDS.get(lang, SHOP_WORDS["en"]):
        add(f"{w} {city}", "web", "brave", 2)
        for area in hub.areas[:3]:
            add(f"{w} {area}", "web", "brave", 2)

    # Instagram and TikTok hashtags: concept labels alone and combined with the city.
    tags: dict[str, int] = {}
    for cid in DISCOVERY_CONCEPTS:
        for label in _labels(tax, cid, hub, limit=3):
            tags.setdefault(hashtag_form(label), 3)
            tags.setdefault(hashtag_form(f"{label} {city}"), 1)
    for w in ("couture", "tailleur", "mode", "bazin", "boubou"):
        tags.setdefault(hashtag_form(f"{w} {city}"), 1)
    for w in ("bazin", "boubou", "tailleur"):
        tags.setdefault(hashtag_form(f"{w} {cname}"), 2)
    for tag, prio in tags.items():
        if len(tag) < 4:
            continue
        add(f"#{tag}", "instagram", "apify_instagram", prio, language=None)
        add(f"#{tag}", "tiktok", "apify_tiktok", prio, language=None)
    # TikTok also supports free-text search.
    for cid in ("garment.grand_boubou", "garment.taille_basse", "fabric.getzner", "garment.agbada"):
        for label in _labels(tax, cid, hub, limit=1):
            add(f"{label} {city}", "tiktok", "apify_tiktok", 1)
            add(f"tailleur {label} {city}" if lang == "fr" else f"{label} tailor {city}", "tiktok", "apify_tiktok", 1)

    # Facebook pages and Google Maps for physical shops and ateliers.
    for w in MAKER_WORDS.get(lang, MAKER_WORDS["en"])[:2] + SHOP_WORDS.get(lang, SHOP_WORDS["en"])[:2]:
        add(f"{w} {city}", "google_maps", "apify_google_maps", 2)
        add(f"{w} {city}", "facebook", "apify_facebook", 2)
    add(f"bazin getzner {city}", "facebook", "apify_facebook", 1)
    add(f"bazin getzner {city}", "google_maps", "apify_google_maps", 2)

    # YouTube: city-specific and generic.
    for cid in ("garment.grand_boubou", "fabric.getzner", "technique.embroidery"):
        for label in _labels(tax, cid, hub, limit=1):
            add(f"{label} {city}", "youtube", "youtube", 3)

    # Open geo data: one query per hub, resolved by the adapter into category filters.
    add(f"tailor|fabric|clothes|textile @{hub.id}", "overture", "overture", 2, language=None)
    return out


def plan(tax: Taxonomy | None = None, max_priority_hubs: int = 1) -> list[PlannedQuery]:
    tax = tax or taxonomy()
    out: list[PlannedQuery] = []
    for hub in hubs(max_priority_hubs):
        out.extend(plan_for_hub(tax, hub))
    for kw in YOUTUBE_GENERIC:
        out.append(PlannedQuery(kw, "youtube", "youtube", None, None, 3))
    for kw in ETSY_KEYWORDS:
        out.append(PlannedQuery(kw, "etsy", "etsy", None, "en", 2))
    for s in stores():
        out.append(PlannedQuery(s.domain, "shopify", "shopify", s.country, None, 2))
    return dedupe(out)


def dedupe(queries: list[PlannedQuery]) -> list[PlannedQuery]:
    seen: set[tuple[str, str, str]] = set()
    out: list[PlannedQuery] = []
    for q in queries:
        key = (q.platform, normalize(q.query), q.market or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return sorted(out, key=lambda q: (q.priority, q.platform, q.query))


def save(conn, queries: list[PlannedQuery]) -> int:
    """Insert new queries; existing ones keep their status. Returns inserted count."""
    n = 0
    for q in queries:
        row = fetch_one(
            conn,
            """
            insert into discovery_queries (query, language, market, platform, tool, priority)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (platform, query, coalesce(market, '')) do nothing
            returning id
            """,
            (q.query, q.language, q.market, q.platform, q.tool, q.priority),
        )
        if row:
            n += 1
    return n


def expand_with_llm(llm, tax: Taxonomy, hub: Hub, concept_ids: list[str]) -> list[PlannedQuery]:
    """Ask the model for colloquial phrasings per concept for this hub; returns web queries at priority 2."""
    from ..llm.client import QueryExpansion  # local import to keep the planner importable without the client

    out: list[PlannedQuery] = []
    lang = _lang(hub)
    for cid in concept_ids:
        c = tax.concepts[cid]
        known = ", ".join(sorted({l.label for l in c.labels}))
        exp: QueryExpansion = llm.structured(
            "query_expand",
            system=None,
            user_text=(
                f"Concept: {c.canonical_label} ({cid}). Market: {hub.city}, {hub.country}. Language: {lang}. "
                f"Known phrasings: {known}. Propose phrasings shoppers and sellers actually use in this market."
            ),
            schema=QueryExpansion,
            effort="low",
        )
        for phrase in exp.phrasings:
            if normalize(phrase) and normalize(phrase) not in {normalize(l.label) for l in c.labels}:
                out.append(PlannedQuery(f"{phrase} {hub.city}", "web", "brave", hub.country, lang, 2))
    return out


def summary(queries: list[PlannedQuery]) -> dict[str, int]:
    out: dict[str, int] = {}
    for q in queries:
        out[q.tool] = out.get(q.tool, 0) + 1
    out["total"] = len(queries)
    return out


def mark(conn, query_id: str, status: str, results_count: int | None = None) -> None:
    execute(
        conn,
        "update discovery_queries set status = %s, last_run_at = now(), results_count = coalesce(%s, results_count) where id = %s",
        (status, results_count, query_id),
    )
