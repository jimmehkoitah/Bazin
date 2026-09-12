"""S7. Deterministic, versioned scoring (weights v0.1). LLMs only write the narrative."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from ..db import execute, fetch_all, fetch_one, jsonb

WEIGHTS_VERSION = "v0.1"

MAKER_TYPES = {"tailor", "couture_designer", "embroiderer"}
RETAIL_TYPES = {"fabric_retailer", "fabric_wholesaler", "brand_partner", "rtw_seller", "marketplace_seller"}

RELEVANT_PREFIXES = ("fabric.bazin", "fabric.getzner", "garment.", "technique.dyeing", "technique.embroidery")


@dataclass
class Features:
    business_type: str = "unknown"
    n12_relevant_observations: int = 0
    n12_observations: int = 0
    price_anchor: bool = False
    order_channel: bool = False
    shipping_info: bool = False
    city_resolved: bool = False
    product_observations: int = 0
    finished_garments: int = 0
    fittings_or_tagged: int = 0
    closeups_or_before_after: int = 0
    distinct_customers: int = 0
    duplicate_images: int = 0
    stock_images: int = 0
    distinct_lines: int = 0
    authenticity_evidence: int = 0
    brand_partner_listing: bool = False
    own_shop_photos: int = 0
    review_count: int = 0
    review_rating_norm: float | None = None  # 0..1
    platforms: int = 0
    phone_consistency: bool = False
    physical_address: bool = False
    website: bool = False
    account_age_months: float | None = None
    scam_reports: int = 0
    negative_review_share: float = 0.0
    days_since_last_active: float | None = None
    concept_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ScoreComponents:
    category_relevance: float
    commercial_clarity: float
    maker_credibility: float
    trust: float
    freshness: float
    total: float


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def category_relevance(f: Features) -> float:
    if f.n12_observations <= 0:
        return 0.0
    share = f.n12_relevant_observations / f.n12_observations
    return _clamp((1 - math.exp(-f.n12_relevant_observations / 6)) * max(0.3, share))


def commercial_clarity(f: Features) -> float:
    return _clamp(
        0.30 * f.price_anchor
        + 0.30 * f.order_channel
        + 0.15 * f.shipping_info
        + 0.15 * f.city_resolved
        + 0.10 * (f.product_observations >= 5)
    )


def maker_credibility(f: Features) -> float:
    if f.business_type in RETAIL_TYPES:
        # assortment_and_authenticity fills the same slot for retailers and wholesalers
        return _clamp(
            0.35 * (f.distinct_lines >= 3)
            + 0.25 * (f.authenticity_evidence > 0)
            + 0.25 * f.brand_partner_listing
            + 0.15 * (f.own_shop_photos > 0)
        )
    return _clamp(
        0.30 * (f.finished_garments >= 3)
        + 0.25 * (f.fittings_or_tagged > 0)
        + 0.15 * (f.closeups_or_before_after > 0)
        + 0.15 * (f.product_observations >= 10)
        + 0.15 * (f.distinct_customers >= 3)
        - 0.30 * (f.duplicate_images >= 2)
        - 0.20 * (f.stock_images > 0)
    )


def trust(f: Features) -> float:
    if f.review_count >= 3 and f.review_rating_norm is not None:
        reviews = f.review_rating_norm
    elif f.review_count > 0 and f.review_rating_norm is not None:
        reviews = 0.5 * f.review_rating_norm
    else:
        reviews = 0.0
    account_age = (f.account_age_months or 0) >= 12
    return _clamp(
        0.30 * reviews
        + 0.20 * (f.platforms >= 2)
        + 0.15 * f.phone_consistency
        + 0.10 * f.physical_address
        + 0.10 * f.website
        + 0.15 * account_age
        - 0.50 * (f.scam_reports > 0)
        - 0.20 * (f.negative_review_share > 0.3)
    )


def freshness(f: Features) -> float:
    if f.days_since_last_active is None:
        return 0.0
    return _clamp(math.exp(-f.days_since_last_active / 120))


def compute(f: Features) -> ScoreComponents:
    cr, cc, mc, tr, fr = category_relevance(f), commercial_clarity(f), maker_credibility(f), trust(f), freshness(f)
    total = (0.25 * cr + 0.25 * cc + 0.25 * mc + 0.25 * tr) * (0.7 + 0.3 * fr)
    return ScoreComponents(cr, cc, mc, tr, fr, round(_clamp(total), 4))


# ---------------------------------------------------------------- features from the database


def features_from_db(conn, business_id: str, now: datetime | None = None) -> Features:
    now = now or datetime.now(timezone.utc)
    biz = fetch_one(conn, "select * from businesses where id = %s", (business_id,))
    if not biz:
        raise KeyError(business_id)
    f = Features(business_type=biz["business_type"])

    obs = fetch_all(
        conn,
        """
        select o.id, o.published_at, o.kind,
               coalesce(array_agg(oc.concept_id) filter (where oc.concept_id is not null), '{}') as concepts
        from observations o
        left join observation_concepts oc on oc.observation_id = o.id
        where o.business_id = %s and o.kind in ('post','reel','video','listing')
        group by o.id
        """,
        (business_id,),
    )
    last_active = None
    for o in obs:
        pub = o["published_at"]
        if pub and (last_active is None or pub > last_active):
            last_active = pub
        recent = pub is None or (now - pub).days <= 365
        if recent:
            f.n12_observations += 1
            if any(c.startswith(RELEVANT_PREFIXES) for c in o["concepts"]):
                f.n12_relevant_observations += 1
        f.product_observations += 1 if o["concepts"] else 0
        for c in o["concepts"]:
            f.concept_counts[c] = f.concept_counts.get(c, 0) + 1
    if last_active:
        f.days_since_last_active = max(0.0, (now - last_active).total_seconds() / 86400)
    elif biz["last_observed_active_at"]:
        f.days_since_last_active = max(0.0, (now - biz["last_observed_active_at"]).total_seconds() / 86400)

    ev = fetch_all(conn, "select kind, polarity, rating, rating_scale, review_count from evidence where business_id = %s", (business_id,))
    ratings: list[float] = []
    for e in ev:
        k = e["kind"]
        if k == "finished_garment":
            f.finished_garments += 1
        elif k in ("fitting_video", "tagged_customer_post"):
            f.fittings_or_tagged += 1
            if k == "tagged_customer_post":
                f.distinct_customers += 1
        elif k in ("embroidery_closeup", "before_after"):
            f.closeups_or_before_after += 1
        elif k == "duplicate_image":
            f.duplicate_images += 1
        elif k == "stock_image":
            f.stock_images += 1
        elif k == "brand_partner_listing":
            f.brand_partner_listing = True
        elif k == "pricing_clarity":
            f.price_anchor = True
        elif k == "physical_address":
            f.physical_address = True
        elif k == "website":
            f.website = True
        elif k == "scam_report":
            f.scam_reports += 1
        elif k == "review":
            f.review_count += int(e["review_count"] or 1)
            if e["rating"] is not None and e["rating_scale"]:
                ratings.append(float(e["rating"]) / float(e["rating_scale"]))
        elif k == "negative_review":
            f.negative_review_share = max(f.negative_review_share, 0.31)
    if ratings:
        f.review_rating_norm = sum(ratings) / len(ratings)

    lines = {c for c in f.concept_counts if c.startswith("fabric.getzner.") or c.startswith("fabric.bazin.")}
    f.distinct_lines = len(lines)
    f.authenticity_evidence = f.concept_counts.get("signal.authenticity", 0)

    contacts = fetch_all(conn, "select kind, normalized_value from contact_channels where business_id = %s", (business_id,))
    kinds = {c["kind"] for c in contacts}
    f.order_channel = bool(kinds & {"whatsapp", "phone", "instagram_dm", "website", "wa_catalog", "email"})
    f.website = f.website or "website" in kinds
    phones = {c["normalized_value"] for c in contacts if c["kind"] in ("phone", "whatsapp") and c["normalized_value"]}

    ids = fetch_all(conn, "select platform, bio, created_at from identities where business_id = %s", (business_id,))
    f.platforms = len({i["platform"] for i in ids})
    if phones and f.platforms >= 2:
        # a phone number that appears in more than one platform's bio
        f.phone_consistency = any(sum(1 for i in ids if i["bio"] and p[-7:] in (i["bio"] or "")) >= 2 for p in phones)

    locs = fetch_all(conn, "select kind, city, address from locations where business_id = %s", (business_id,))
    f.city_resolved = any(l["city"] for l in locs if l["kind"] != "ships_to")
    f.physical_address = f.physical_address or any(l["address"] for l in locs if l["kind"] in ("shop", "atelier", "market_stall"))
    f.shipping_info = any(l["kind"] == "ships_to" for l in locs) or f.concept_counts.get("signal.shipping", 0) > 0
    f.price_anchor = f.price_anchor or bool(fetch_one(conn, "select 1 from prices where business_id = %s limit 1", (business_id,)))

    if biz["first_seen_at"]:
        f.account_age_months = (now - biz["first_seen_at"]).days / 30.0
    return f


def persist(conn, business_id: str, f: Features, s: ScoreComponents, reasons: list[str], caveats: list[str]) -> None:
    execute(
        conn,
        """
        insert into scores (business_id, weights_version, category_relevance, commercial_clarity, maker_credibility,
                            trust, freshness, total, inputs, reasons, caveats)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            business_id, WEIGHTS_VERSION, s.category_relevance, s.commercial_clarity, s.maker_credibility,
            s.trust, s.freshness, s.total, jsonb(asdict(f)), reasons, caveats,
        ),
    )
    execute(conn, "update businesses set quality_score = %s, updated_at = now() where id = %s", (s.total, business_id))
    # refresh the per-business concept aggregate used by search
    execute(conn, "delete from business_concepts where business_id = %s", (business_id,))
    for cid, n in f.concept_counts.items():
        execute(
            conn,
            "insert into business_concepts (business_id, concept_id, evidence_count, score) values (%s, %s, %s, %s)",
            (business_id, cid, n, 1 - math.exp(-n / 3)),
        )
