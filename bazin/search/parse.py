"""S9. Query understanding plus place resolution."""

from __future__ import annotations

from ..hubs import Hub, load_hubs
from ..llm.client import LLM
from ..llm.prompts import QUERY_PARSE_SYSTEM_TEMPLATE, concept_catalogue
from ..models import ParsedQuery
from ..taxonomy import normalize, taxonomy

PLACE_ALIASES = {
    "nyc": "new_york", "new york city": "new_york", "harlem": "new_york", "bronx": "new_york", "brooklyn": "new_york", "manhattan": "new_york",
    "chateau rouge": "paris", "château rouge": "paris", "goutte d'or": "paris", "barbes": "paris", "barbès": "paris", "ile-de-france": "paris",
    "milano": "milan", "londres": "london", "abidjan": "abidjan", "dakar": "dakar", "bamako": "bamako", "lagos": "lagos",
}

WEST_AFRICA = {"SN", "ML", "GN", "GM", "CI", "BJ", "TG", "NG", "BF", "NE", "MR"}
DIASPORA = {"FR", "US", "GB", "IT", "NL", "BE", "ES", "CA", "DE"}


def resolve_place(text: str | None) -> Hub | None:
    if not text:
        return None
    t = normalize(text)
    hubs, _ = load_hubs()
    for alias, hub_id in PLACE_ALIASES.items():
        if normalize(alias) in t:
            return next(h for h in hubs if h.id == hub_id)
    for h in hubs:
        if normalize(h.city) in t:
            return h
    return None


_SYSTEM: str | None = None


def parse_query(llm: LLM, q: str) -> ParsedQuery:
    global _SYSTEM
    if _SYSTEM is None:
        _SYSTEM = QUERY_PARSE_SYSTEM_TEMPLATE.format(catalogue=concept_catalogue(taxonomy(), ("fabric", "garment", "technique", "occasion", "style", "color")))
    return llm.structured("query_parse", system=_SYSTEM, user_text=f"Query: {q}", schema=ParsedQuery, effort="low", max_tokens=800)
