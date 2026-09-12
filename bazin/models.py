"""Pydantic models shared across stages. The LLM-facing ones double as structured-output schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal[
    "instagram", "tiktok", "facebook", "youtube", "pinterest", "snapchat", "etsy", "afrikrea", "amazon",
    "jumia", "coinafrique", "expat_dakar", "jiji", "shopify", "website", "google_maps", "yelp",
    "osm", "overture", "whatsapp", "web", "other",
]
BusinessType = Literal[
    "fabric_retailer", "fabric_wholesaler", "brand_partner", "tailor", "couture_designer",
    "embroiderer", "rtw_seller", "marketplace_seller", "unknown",
]
AcquisitionMethod = Literal[
    "vendor_submitted", "claimed", "manual", "official_api", "open_data", "first_party_crawl",
    "third_party_scraper", "serp", "feed",
]
ObservationKind = Literal["post", "reel", "video", "listing", "profile", "review", "page", "map_place", "ad", "other"]


# ---------------------------------------------------------------- discovery and ingestion


class Candidate(BaseModel):
    """Something an adapter found that might be a business or a piece of its content."""

    platform: Platform
    url: str
    handle: str | None = None
    external_id: str | None = None
    title: str | None = None
    snippet: str | None = None
    thumbnail_url: str | None = None
    source_json: dict = Field(default_factory=dict, description="Small non-content payload: counts, ids")


class MediaIn(BaseModel):
    media_url: str
    thumbnail_url: str | None = None
    oembed_url: str | None = None
    width: int | None = None
    height: int | None = None


class ObservationIn(BaseModel):
    """An adapter's normalised view of one thing it saw. Immutable once stored."""

    platform: Platform
    source_url: str
    kind: ObservationKind
    external_id: str | None = None
    published_at: datetime | None = None
    caption_excerpt: str | None = Field(default=None, max_length=300)
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    language: str | None = None
    engagement: dict = Field(default_factory=dict)
    raw_ref: str | None = None
    acquisition_method: AcquisitionMethod
    media: list[MediaIn] = Field(default_factory=list)


class ProfileBundle(BaseModel):
    """Everything an adapter returns for one identity: the profile plus recent content."""

    platform: Platform
    url: str
    handle: str | None = None
    external_id: str | None = None
    display_name: str | None = None
    bio: str | None = Field(default=None, max_length=600)
    bio_link: str | None = None
    followers: int | None = None
    observations: list[ObservationIn] = Field(default_factory=list)
    raw_ref: str | None = None


# ---------------------------------------------------------------- S2 relevance gate


class RelevanceVerdict(BaseModel):
    relevant: bool
    business_type_guess: BusinessType
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(max_length=300)
    language_guess: str = Field(description="ISO 639-1 code of the dominant language, or 'unknown'")


# ---------------------------------------------------------------- S4 profile enrichment


class LocationOut(BaseModel):
    kind: Literal["atelier", "shop", "pickup", "market_stall", "online_only", "ships_to"]
    country: str | None = Field(default=None, description="ISO 3166-1 alpha-2")
    city: str | None = None
    address: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(max_length=200, description="Quoted text that supports this")


class ContactOut(BaseModel):
    kind: Literal["whatsapp", "phone", "email", "instagram_dm", "website", "wa_catalog", "snapchat", "telegram", "other"]
    value: str
    evidence: str = Field(max_length=200)


class OfferOut(BaseModel):
    garment_concept_id: str | None = None
    fabric_concept_id: str | None = None
    gender: Literal["women", "men", "children", "unisex", "unknown"] = "unknown"
    custom_or_ready: Literal["custom", "ready", "both", "unknown"] = "unknown"
    lead_time_days: int | None = None
    evidence: str = Field(max_length=200)


class PriceOut(BaseModel):
    price_type: Literal["fabric", "tailoring", "complete_outfit", "embroidery", "shipping", "other"]
    currency: str = Field(description="ISO 4217, e.g. XOF, NGN, EUR, USD, GBP")
    amount_min: float | None = None
    amount_max: float | None = None
    unit: Literal["metre", "yard", "piece", "3m", "4m", "5m", "5yd", "10yd", "outfit", "item", "kg", "unknown"] = "unknown"
    includes_fabric: bool | None = None
    includes_embroidery: bool | None = None
    includes_tailoring: bool | None = None
    is_promo: bool = False
    currency_inferred: bool = Field(default=False, description="True when the caption did not state the currency")
    evidence: str = Field(max_length=200)


class CommerceSignals(BaseModel):
    price_shown: bool = False
    dm_to_order: bool = False
    whatsapp: bool = False
    shipping_info: bool = False
    catalogue: bool = Field(default=False, description="Repeated product posts with consistent presentation")


class Enrichment(BaseModel):
    business_type: BusinessType
    business_type_confidence: float = Field(ge=0, le=1)
    canonical_name: str = Field(max_length=120)
    locations: list[LocationOut] = Field(default_factory=list)
    contact_channels: list[ContactOut] = Field(default_factory=list)
    offers: list[OfferOut] = Field(default_factory=list)
    prices: list[PriceOut] = Field(default_factory=list)
    ships_to: list[str] = Field(default_factory=list, description="ISO 3166-1 alpha-2 codes")
    languages: list[str] = Field(default_factory=list, description="ISO 639-1 codes")
    commerce_signals: CommerceSignals = Field(default_factory=CommerceSignals)
    summary: str = Field(max_length=600, description="Our own words; never copied caption text")


# ---------------------------------------------------------------- S5 post classification


class ConceptHit(BaseModel):
    id: str
    confidence: float = Field(ge=0, le=1)


class ColorShare(BaseModel):
    name: Literal[
        "white", "blue", "gold", "black", "red", "green", "pink", "purple", "yellow", "brown",
        "grey", "beige", "orange", "turquoise", "multi",
    ]
    share: float = Field(ge=0, le=1)


class PriceMention(BaseModel):
    currency: str
    amount: float
    unit: str = "unknown"


class PostClassification(BaseModel):
    concept_ids: list[ConceptHit] = Field(default_factory=list)
    colors: list[ColorShare] = Field(default_factory=list)
    occasion_ids: list[str] = Field(default_factory=list)
    gender: Literal["women", "men", "children", "unisex", "unknown"] = "unknown"
    is_finished_garment: bool = False
    is_fabric_only: bool = False
    is_fitting_or_customer: bool = False
    is_embroidery_closeup: bool = False
    shows_price: PriceMention | None = None
    language: str = "unknown"
    buyer_intent: Literal["buy_fabric", "find_tailor", "style_inspiration", "price_comparison", "authenticity_check", "shipping", "other"] = "other"
    visual_quality: float = Field(default=0.5, ge=0, le=1)


# ---------------------------------------------------------------- S8 cluster labelling


class ClusterLabel(BaseModel):
    label: str = Field(max_length=60)
    description: str = Field(max_length=300)
    primary_concepts: list[str] = Field(default_factory=list)
    typical_price_band: str | None = None
    typical_markets: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- S9 query parsing


class BudgetOut(BaseModel):
    currency: str
    max: float


class LocationQuery(BaseModel):
    near: str | None = Field(default=None, description="Place name as the user wrote it, or null")
    radius_km: float | None = None
    ships_to: str | None = Field(default=None, description="ISO 3166-1 alpha-2, or null")


class ParsedQuery(BaseModel):
    garment_concept_ids: list[str] = Field(default_factory=list)
    fabric_concept_ids: list[str] = Field(default_factory=list)
    occasion_ids: list[str] = Field(default_factory=list)
    gender: Literal["women", "men", "children", "unisex", "unknown"] = "unknown"
    colors: list[str] = Field(default_factory=list)
    business_types: list[BusinessType] = Field(default_factory=list)
    budget: BudgetOut | None = None
    location: LocationQuery = Field(default_factory=LocationQuery)
    custom_or_ready: Literal["custom", "ready", "both", "unknown"] = "unknown"
    luxury_tier: bool = False
    free_text: str = Field(default="", description="What remains after filters are removed, for semantic search")
    language: str = "unknown"


# ---------------------------------------------------------------- S7 reasons and S11 judging


class ScoreNarrative(BaseModel):
    reasons: list[str] = Field(default_factory=list, max_length=5)
    caveats: list[str] = Field(default_factory=list, max_length=5)


class JudgeVerdict(BaseModel):
    business_type_ok: bool
    location_ok: bool
    contact_ok: bool
    score_plausible: bool
    issues: list[str] = Field(default_factory=list, max_length=6)
    overall: Literal["accept", "fix", "reject"]
