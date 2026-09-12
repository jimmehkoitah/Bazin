"""S3. Identity resolution: which handles are the same business.

Deterministic rules first; the LLM only breaks ties between name-similar pairs with conflicting signals.

Rules (any one is enough):
- shared E.164 phone number or wa.me link;
- explicit cross-link (one bio links to the other's URL or @handle);
- identical website host;
- three or more shared perceptual hashes and name similarity >= 0.8.
Never merge across countries on name similarity alone; never merge two identities that show
different phone numbers unless a cross-link exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlparse

import phonenumbers

from ..db import execute, fetch_all, fetch_one
from ..taxonomy import normalize

PHONE_RE = re.compile(r"(?:\+|00)?[\d][\d\s().\-]{6,}\d")
WA_RE = re.compile(r"wa\.me/(\d{6,})")

DEFAULT_REGION_BY_COUNTRY = {
    "SN": "SN", "ML": "ML", "GN": "GN", "GM": "GM", "CI": "CI", "BJ": "BJ", "TG": "TG", "NG": "NG",
    "FR": "FR", "US": "US", "GB": "GB", "IT": "IT", "NL": "NL", "BE": "BE", "ES": "ES", "BF": "BF", "NE": "NE", "MR": "MR",
}


def extract_phones(text: str | None, default_region: str | None = None) -> list[str]:
    """E.164 numbers found in text. Regions tried: explicit default, then the West African and diaspora set."""
    if not text:
        return []
    found: list[str] = []
    for m in WA_RE.finditer(text):
        found.append("+" + m.group(1))
    regions = [default_region] if default_region else []
    regions += ["SN", "ML", "NG", "FR", "US", "GB", "IT", "CI", "BJ", "GN", "GM", "TG"]
    for m in PHONE_RE.finditer(text):
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 8 or len(digits) > 15:
            continue
        parsed = None
        if raw.strip().startswith(("+", "00")):
            try:
                parsed = phonenumbers.parse("+" + digits.lstrip("0") if raw.strip().startswith("00") else raw, None)
            except phonenumbers.NumberParseException:
                parsed = None
        if parsed is None:
            for region in regions:
                try:
                    cand = phonenumbers.parse(raw, region)
                except phonenumbers.NumberParseException:
                    continue
                if phonenumbers.is_valid_number(cand):
                    parsed = cand
                    break
        if parsed and phonenumbers.is_valid_number(parsed):
            found.append(phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
    return list(dict.fromkeys(found))


def website_host(url: str | None) -> str | None:
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower()
    host = host.removeprefix("www.")
    # Link-in-bio aggregators and social hosts are not identifying websites.
    if not host or any(h in host for h in ("linktr.ee", "instagram.com", "tiktok.com", "facebook.com", "wa.me", "whatsapp.com", "youtube.com", "snapchat.com", "beacons.ai", "bio.site", "linkin.bio")):
        return None
    return host


def name_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


@dataclass
class IdentityFacts:
    id: str
    platform: str
    handle: str | None
    url: str
    display_name: str | None
    bio: str | None
    bio_link: str | None
    country: str | None = None
    phones: set[str] = field(default_factory=set)
    hosts: set[str] = field(default_factory=set)
    phashes: set[str] = field(default_factory=set)
    business_id: str | None = None

    @property
    def name(self) -> str:
        return self.display_name or self.handle or self.url


def facts_for(conn, identity_id: str) -> IdentityFacts:
    row = fetch_one(conn, "select * from identities where id = %s", (identity_id,))
    f = IdentityFacts(
        id=str(row["id"]), platform=row["platform"], handle=row["handle"], url=row["url"],
        display_name=row["display_name"], bio=row["bio"], bio_link=row["bio_link"], business_id=str(row["business_id"]) if row["business_id"] else None,
    )
    f.phones = set(extract_phones(f.bio)) | set(extract_phones(f.bio_link))
    host = website_host(f.bio_link)
    if host:
        f.hosts.add(host)
    if f.platform in ("website", "shopify"):
        host = website_host(f.url)
        if host:
            f.hosts.add(host)
    for r in fetch_all(
        conn,
        "select m.phash from media_refs m join observations o on o.id = m.observation_id where o.identity_id = %s and m.phash is not null",
        (identity_id,),
    ):
        f.phashes.add(r["phash"])
    if f.business_id:
        loc = fetch_one(conn, "select country from locations where business_id = %s and kind <> 'ships_to' limit 1", (f.business_id,))
        f.country = loc["country"] if loc else None
    return f


def cross_linked(a: IdentityFacts, b: IdentityFacts) -> bool:
    for x, y in ((a, b), (b, a)):
        text = f"{x.bio or ''} {x.bio_link or ''}".lower()
        if y.handle and (f"@{y.handle.lower()}" in text or f"/{y.handle.lower()}" in text):
            return True
        if y.url and y.url.lower().rstrip("/") in text:
            return True
    return False


def decide(a: IdentityFacts, b: IdentityFacts) -> tuple[str, float, dict]:
    """Return ('same' | 'different' | 'unsure', confidence, evidence)."""
    ev: dict = {}
    if a.id == b.id:
        return "same", 1.0, {"identical": True}
    shared_phones = a.phones & b.phones
    if shared_phones:
        ev["shared_phone"] = sorted(shared_phones)
        return "same", 0.98, ev
    if cross_linked(a, b):
        ev["cross_link"] = True
        return "same", 0.95, ev
    shared_hosts = a.hosts & b.hosts
    if shared_hosts:
        ev["shared_website"] = sorted(shared_hosts)
        return "same", 0.93, ev
    sim = name_similarity(a.name, b.name)
    ev["name_similarity"] = round(sim, 3)
    if a.phones and b.phones and not shared_phones:
        ev["different_phones"] = True
        return "different", 0.9, ev
    if a.country and b.country and a.country != b.country:
        ev["different_countries"] = True
        return "different", 0.85, ev
    shared_hashes = a.phashes & b.phashes
    if len(shared_hashes) >= 3 and sim >= 0.8:
        ev["shared_phashes"] = len(shared_hashes)
        return "same", 0.9, ev
    if sim >= 0.85 and (a.handle and b.handle and normalize(a.handle) == normalize(b.handle)):
        ev["same_handle"] = True
        return "unsure", 0.6, ev
    if sim >= 0.9:
        return "unsure", 0.5, ev
    return "different", 0.7, ev


def candidate_pairs(conn, identity_id: str) -> list[str]:
    """Other identities that could be the same business: shared phone/host tokens or similar names."""
    me = fetch_one(conn, "select handle, display_name, bio_link from identities where id = %s", (identity_id,))
    if not me:
        return []
    name = normalize(me["display_name"] or me["handle"] or "")
    rows = fetch_all(
        conn,
        """
        select id from identities
        where id <> %s and (
          similarity(coalesce(display_name, handle, ''), %s) > 0.45
          or (bio_link is not null and bio_link = %s)
        )
        limit 50
        """,
        (identity_id, name, me["bio_link"]),
    )
    return [str(r["id"]) for r in rows]


def ensure_business(conn, ident: IdentityFacts) -> str:
    """Give an unattached identity its own business row."""
    if ident.business_id:
        return ident.business_id
    row = fetch_one(
        conn,
        "insert into businesses (canonical_name, status) values (%s, 'candidate') returning id",
        (ident.name[:120],),
    )
    bid = str(row["id"])
    execute(conn, "update identities set business_id = %s, is_primary = true where id = %s", (bid, ident.id))
    execute(conn, "update observations set business_id = %s where identity_id = %s and business_id is null", (bid, ident.id))
    return bid


def merge_into(conn, keep: str, drop: str, confidence: float, evidence: dict) -> None:
    """Move everything from business `drop` into `keep` and mark `drop` a duplicate."""
    if keep == drop:
        return
    for table in ("identities", "observations", "locations", "contact_channels", "offers", "prices", "evidence", "business_clusters"):
        try:
            execute(conn, f"update {table} set business_id = %s where business_id = %s", (keep, drop))
        except Exception:
            conn.rollback()
            raise
    execute(
        conn,
        "update identities set match_confidence = %s, match_evidence = %s where business_id = %s and match_confidence is null",
        (confidence, __import__("json").dumps(evidence), keep),
    )
    execute(conn, "update businesses set status = 'duplicate', duplicate_of = %s, updated_at = now() where id = %s", (keep, drop))


def resolve_identity(conn, identity_id: str, llm=None) -> tuple[str, list[str]]:
    """Attach an identity to a business, merging when a rule fires. Returns (business_id, merged_business_ids)."""
    me = facts_for(conn, identity_id)
    my_bid = ensure_business(conn, me)
    merged: list[str] = []
    for other_id in candidate_pairs(conn, identity_id):
        other = facts_for(conn, other_id)
        verdict, conf, ev = decide(me, other)
        if verdict == "unsure" and llm is not None:
            from ..llm.client import SameBusiness

            v: SameBusiness = llm.structured(
                "identity",
                system=None,
                user_text=(
                    f"A: {me.platform} {me.name} bio={me.bio!r} link={me.bio_link!r} phones={sorted(me.phones)} country={me.country}\n"
                    f"B: {other.platform} {other.name} bio={other.bio!r} link={other.bio_link!r} phones={sorted(other.phones)} country={other.country}"
                ),
                schema=SameBusiness,
                effort="low",
            )
            if v.same_business and v.confidence >= 0.7:
                verdict, conf, ev = "same", v.confidence, {**ev, "llm": v.reason}
        if verdict == "same":
            other_bid = ensure_business(conn, other)
            if other_bid != my_bid:
                keep, drop = sorted([my_bid, other_bid])  # stable choice
                merge_into(conn, keep, drop, conf, ev)
                merged.append(drop)
                my_bid = keep
    return my_bid, merged
