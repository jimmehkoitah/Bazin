# V1 build spec — Bazin discovery engine

Date: 2026-09-12. Implements the decisions in `decisions.md`. Companion files: `thesis-review.md` (why), `taxonomy-seed.md` (vocabulary), `db/schema.sql` (schema).

Open for Jim's confirmation: the runtime split (section 3.3), Nigeria in scope (assumed yes), the LLM cost tier (section 9), and a small reviewer spend (section 8).

## 1. Goal and scope

Goal for the first eight weeks: a searchable, clustered, geo-aware index of as many Bazin-relevant vendors as $1,000 buys, across Senegal, Mali, Guinea, Gambia, Côte d'Ivoire, Benin, Togo, Nigeria and the diaspora hubs in France, the US, the UK, Italy, the Netherlands, Belgium and Spain, with evidence-backed quality scores and link-outs to every source.

Working targets (assumptions, to be replaced by measured yields after sprint 1):

| Funnel stage | Target |
|---|---|
| Candidate URLs discovered | 8,000 |
| Candidates passing the relevance gate | 4,000 |
| Resolved businesses after identity merge | 2,000 |
| Businesses with a quality score and at least one verified contact channel | 1,000 |
| Businesses in the "recommendable" band (score ≥ 0.6, ≥ 3 evidence items, active in 180 days) | 400 |

Non-goals for v1: transactions, vendor outreach, media hosting, Ankara/Kente/Aso Oke, a polished consumer UI (a functional search page is enough).

## 2. Architecture

```
 discovery                ingestion               understanding              serving
 ─────────                ─────────               ─────────────              ───────
 query matrix  ──►  scrapers / APIs / feeds  ──►  observations (immutable)
 (concepts ×             (Apify, Etsy API,          │
  cities ×               YouTube API, Brave,        ├─► relevance gate ─► identity resolver ─► businesses
  platforms)             classifieds, Shopify,      │                                           │
                         Overture/OSM)              ├─► post classifier (vision) ─► concepts,   │
                                                    │                        colours, prices    │
                                                    ├─► profile enricher ─► locations, contacts,│
                                                    │                        offers             │
 Cotera agents ───────────────────────────────────► evidence (reviews, lookups) ────────────────┤
                                                                                                ▼
                                                                        scorer (deterministic) ─► scores
                                                                        embedder + clusterer ──► clusters
                                                                                                │
                                                                                                ▼
                                                                   search API: parse ─► filter ─► hybrid rank
                                                                   (query_log on every search)
```

Components:

- **Postgres 16 on Render** with pgvector (embeddings), PostGIS (geo) and pg_trgm (name matching). Schema in `db/schema.sql`. Single system of record shared by code and Cotera.
- **Raw payload store**: scraper datasets stay where the scraper puts them (Apify dataset IDs) or in a cheap bucket; `observations.raw_ref` points at them. The database never holds full captions or media bytes.
- **Pipeline workers (Python)**: idempotent stages keyed by `ingest_runs`; LLM stages run through the Message Batches API (asynchronous, half price) except at search time.
- **Cotera agents**: evidence collection where Cotera has tools (Facebook reviews and similar lookups), writing rows into `evidence` via a Postgres integration or a small HTTP endpoint the API exposes.
- **Search API (FastAPI)**: natural-language parse, structured filters, hybrid ranking, query logging. A minimal web page on top.

### 3.3 Runtime split (needs confirmation)

Proposed: bulk work in code in this repo (scraping orchestration, ETL, classification batches, scoring, clustering, search), Cotera for tool-backed lookups and monitoring, one Postgres in between. The reason to keep bulk work in code is cost control and reruns: a 60,000-post classification pass is a batch job with a cost ceiling, not an agent loop. The reason to use Cotera for lookups is that its integrations already exist and the volume is small (one lookup per business, not per post). If Jim prefers everything in Cotera, the schema and agent specs below still apply; the batch jobs become Cotera workflows.

## 4. Data model

See `db/schema.sql`. Design rules:

- `observations` are immutable; every derived fact carries an `evidence_observation_id` or `observation_id` back to what was seen, so any source can be purged and any score explained.
- `source_policies` records, per platform and acquisition method, the terms status, retention and whether media may be stored. Every observation points at one. This is how D2 (accepted risk) stays bounded: an off-terms source can be deleted in one statement.
- Prices carry currency, unit and inclusions, and a USD equivalent at observation time.
- `scores` is append-only; `businesses.quality_score` is a denormalised copy of the latest total for search.
- Rights fields (`notice_sent_at`, `objection_at`, `do_not_contact`, `legal_entity_type`) live on the record, not in a CRM.

## 5. Sources and acquisition plan

Posture per D2: third-party scrapers are allowed. Each source gets a `source_policies` row. Costs are estimates for the eight-week window.

| Source | Method | Tool | What we take | Retention | Est. cost |
|---|---|---|---|---|---|
| Instagram | Third-party scraper | Apify `instagram-scraper` (hashtag, profile and post modes), about $1.50 per 1,000 results | Profile bio, link, follower count, last 20–30 posts: caption excerpt, hashtags, thumbnail URL, engagement, date | Indefinite for excerpts and derived tags; media URLs only | $60–90 for ~3,000 profiles and 60,000 posts |
| TikTok | Third-party scraper | Apify `clockworks/tiktok-scraper` (hashtag, discover-page and profile modes), about $1.70 per 1,000 | Same shape as Instagram plus video thumbnail | Same | $30–50 |
| Facebook pages | Third-party scraper | Apify Facebook pages/posts scrapers | Page info, phone, address, recent posts, ratings where visible | Same | $20–40 |
| Facebook groups | Not scraped (login-gated) | Cotera lookup or manual seed of seller names posted in groups | Seller names and phones to resolve elsewhere | — | $0 |
| Google Maps | Third-party scraper for discovery of physical shops; Places API only for resolution | Apify `google-maps-scraper`; Places API for `place_id` | Name, category, address, coordinates, phone, rating summary, website | Coordinates and names from the scraper are stored under an off-terms policy; Places API content is not stored beyond `place_id` | $20–30 |
| Overture Maps and OpenStreetMap | Open data | Overture Places parquet; OSM Overpass | Tailor, textile and fabric shop POIs by city | Indefinite, with attribution | $0 |
| YouTube | Official API | YouTube Data API v3 | Channel and video metadata for "couture bazin", "broderie bazin", "modèle Tabaski" | 30-day refresh rule for statistics | $0 |
| Etsy | Official API | Etsy Open API v3 (Personal then Commercial access) | Shop, listing title, price, ships-to, shop location | Refresh listings within 6 hours when displayed; store our own derived tags indefinitely | $0 |
| Afrikrea | Crawl | First-party crawl of the Rich Bazin category and seller pages | Seller name, country, listing titles and prices | Indefinite for excerpts | $0 |
| Classifieds: CoinAfrique, Expat-Dakar, Jiji | Crawl | Custom scrapers (public listing pages) | Title, price, city, seller phone, date | Indefinite for excerpts | $0 (dev time) |
| Retailer web shops (Shopify) | First-party feed | `/products.json` endpoints, sitemaps, schema.org | Products, prices, currency, location | Indefinite | $0 |
| Pinterest | Third-party scraper or API | Apify Pinterest scraper for board and pin metadata | Pin title, source link (often a seller site or Instagram), image URL | Excerpts only | $10–20 |
| Yelp (US shops) | Official API | Yelp Fusion API | Business name, address, rating, categories | Per Yelp terms (display rules) | $0 |
| Web search for URL discovery | Search API | Brave Search API (independent index) as primary; Google Programmable Search JSON API as a second source | URLs and snippets for taxonomy × city queries | URL and snippet only | $30–60 for ~10,000 queries |
| Snapchat | Manual and low priority | Public profile pages only | Handle and link | — | $0 |

Query matrix for discovery: every concept label in `taxonomy-seed.md` (fabric, garment, occasion, commerce phrases) × every hub city and country × platform-specific operators (hashtags on Instagram and TikTok, `site:` operators in web search, category pages on marketplaces). The Discovery Planner (stage S1) generates and deduplicates it; expect 3,000 to 5,000 distinct queries.

Operational mitigations for the accepted risk: two scraper vendors configured so either can be swapped; conservative rate limits; residential proxies through the scraper vendor; every run recorded in `ingest_runs` with cost; a public privacy notice and a takedown form live before the first crawl; media never downloaded.

## 6. Pipeline stages and agent specs

Each stage below is written so it can run either as Python code calling the Claude API or as a Cotera agent with the same inputs, tools and output schema. Model default: `claude-opus-5` with adaptive thinking; effort `low` for bulk classification, `high` for enrichment and cluster labelling. Cheaper models for bulk stages are Jim's decision (section 9). All LLM outputs use structured outputs against the JSON schemas below; nothing is parsed from free text.

### S1. Discovery planner

- Goal: produce the query matrix and hand each query to the right tool.
- Inputs: concepts and labels (`concepts`, `concept_labels`), hub list, platform list.
- Tools: none (deterministic), plus one LLM call per (concept, market) to propose 3–5 extra colloquial phrasings.
- Output rows: `{query, language, market, platform, tool, priority}`.
- Guardrails: dedupe by normalised query; cap per platform per day; prioritise garment × city × occasion combinations first (they yield makers), fabric × city second.
- Acceptance: at least 80% of queries return at least one relevant candidate in a sample of 100.

### S2. Relevance gate

- Goal: decide whether a candidate profile or page is Bazin-relevant commerce, before spending on enrichment.
- Inputs: platform, handle, bio or page title, up to 10 caption excerpts, up to 3 thumbnail URLs.
- Instructions: judge from what is shown. Relevant means the account sells, makes, embroiders, dyes or wholesales bazin or bazin garments, or is a brand partner. Style pages, fans, aggregators and personal accounts are not relevant unless they sell. Say why in one sentence.
- Output: `{relevant: boolean, business_type_guess: enum, confidence: 0–1, reason: string, language_guess: string}`.
- Guardrails: hashtag-only evidence yields confidence ≤ 0.5; never infer national origin, only category and commerce signals.
- Acceptance: precision ≥ 0.85 on a 100-item audit; recall measured by re-checking 50 rejected items.

### S3. Identity resolver

- Goal: merge handles that are the same business.
- Inputs: candidate identity rows with bio links, phone numbers, emails, names, thumbnails' perceptual hashes.
- Method: deterministic first (shared E.164 phone or wa.me link = same business; explicit cross-link in bio = same; identical website = same; ≥ 3 shared perceptual hashes with same name similarity ≥ 0.8 = same), then LLM tie-break for name-similar pairs with conflicting signals.
- Output: `{business_id, identity_ids[], match_confidence, match_evidence}`.
- Guardrails: never merge across countries on name similarity alone; never merge two accounts that both show different phone numbers unless a bio cross-link exists.
- Acceptance: on a 100-pair audit, ≤ 3 false merges.

### S4. Profile enricher

- Goal: extract structured business facts from a resolved business's bio, link page, last 20–30 caption excerpts and up to 5 thumbnails.
- Tools: phone-number validation (libphonenumber), URL expander for link-in-bio pages, geocoder for city names (Nominatim or Overture), currency conversion table.
- Instructions: extract only what is observed; quote the evidence for every field; when a price is stated, capture currency, amount, unit and what it includes; infer currency from location and language only when the caption omits it, and mark it inferred; record shipping mentions including GP; do not invent contact channels.
- Output:
  `{business_type, business_type_confidence, locations: [{kind, country, city, address?, confidence, evidence}], contact_channels: [{kind, value, evidence}], offers: [{garment_concept_id, fabric_concept_id, gender, custom_or_ready, lead_time_days?, evidence}], prices: [{price_type, currency, amount_min, amount_max, unit, includes_fabric, includes_embroidery, includes_tailoring, is_promo, inferred_currency, evidence}], ships_to: [country codes], languages: [], commerce_signals: {price_shown, dm_to_order, whatsapp, shipping_info, catalogue}, summary: string}`.
- Guardrails: per-field confidence; anything below 0.5 is stored but not shown; summary must not copy caption text.
- Acceptance: field-level accuracy ≥ 0.9 for business type, city and contact channel on a 50-record audit.

### S5. Post classifier (vision)

- Goal: tag every observation with concepts, colours, price mentions, occasion, language and buyer intent, and produce visual tags from the thumbnail.
- Inputs: caption excerpt, hashtags, thumbnail image (fetched at classification time, not stored), platform.
- Output: `{concept_ids: [{id, confidence}], colors: [{name, share}], occasion_ids: [], gender, is_finished_garment, is_fabric_only, is_fitting_or_customer, is_embroidery_closeup, shows_price: {currency, amount, unit} | null, language, buyer_intent: enum, visual_quality: 0–1}`.
- Also computed in code, not by the model: perceptual hash, dominant colour palette (k-means on the thumbnail), image embedding.
- Guardrails: thumbnails only, one per observation, resized small; batch through the Message Batches API; skip observations older than 24 months.
- Acceptance: concept tagging agreement ≥ 0.85 with a 200-item audit set; colour naming agreement ≥ 0.9.

### S6. Evidence collector (Cotera-first)

- Goal: attach reviews and external proof to each business.
- Tools (Cotera where available): Facebook page reviews and recommendations, Google Maps rating and review count, Yelp, Etsy shop reviews via API, Trustpilot lookup, web search for "<name> avis" / "<name> arnaque" / "<name> scam".
- Output rows into `evidence`: `{business_id, kind, polarity, source_url, extracted_claim, rating, rating_scale, confidence, collected_by}`.
- Guardrails: one lookup per business per 30 days; negative evidence requires a source URL; never store full review text, only rating, date and a ≤ 200-character excerpt.
- Acceptance: ≥ 60% of businesses with a physical location get at least one rating source; scam-report false-positive rate ≤ 5% on audit.

### S7. Scorer (deterministic, versioned)

Weights v0.1, all components in 0–1. `n12` means count in the last 12 months.

- `category_relevance = (1 − exp(−n12_relevant_observations / 6)) × max(0.3, share_relevant)`.
- `commercial_clarity = 0.30·price_anchor + 0.30·order_channel + 0.15·shipping_info + 0.15·city_resolved + 0.10·catalogue(≥ 5 product observations)`.
- `maker_credibility` (tailors, designers, embroiderers) `= 0.30·finished_garments(≥ 3) + 0.25·fittings_or_tagged_customers + 0.15·closeups_or_before_after + 0.15·product_examples(≥ 10) + 0.15·distinct_customers(≥ 3) − 0.30·duplicate_images(≥ 2 phash matches to other accounts) − 0.20·stock_images`. For retailers and wholesalers the same slot holds `assortment_and_authenticity = 0.35·distinct_lines(≥ 3) + 0.25·authenticity_evidence + 0.25·brand_partner_listing + 0.15·stock_photos_of_own_shop`.
- `trust = 0.30·reviews(rating-weighted, min 3 reviews for full credit) + 0.20·cross_platform_identity(≥ 2) + 0.15·phone_consistency + 0.10·physical_address + 0.10·website + 0.15·account_age(≥ 12 months) − 0.50·scam_reports − 0.20·negative_reviews(share > 0.3)`, floored at 0.
- `freshness = exp(−days_since_last_active / 120)`.
- `total = (0.25·category_relevance + 0.25·commercial_clarity + 0.25·maker_credibility + 0.25·trust) × (0.7 + 0.3·freshness)`.

The LLM writes `reasons` and `caveats` from the feature snapshot only. Weights change only by version bump after an audit shows why.

### S8. Embedder and clusterer

- Text embedding per business from the generated summary, concept labels and commerce signals (1024-d). Image embedding per media ref (512-d, open CLIP-class model run in code), averaged per business.
- Cluster input: concatenate normalised text and image embeddings, reduce to 64-d (PCA or UMAP), run HDBSCAN with `min_cluster_size` 15; noise points get the nearest cluster with low membership probability.
- Cluster labelling: one LLM call per cluster with 20 sample summaries and the top concept counts; output `{label, description, primary_concepts, typical_price_band, typical_markets}`. Each cluster gets a stable hue for the UI; hues are assigned once and carried across runs by centroid matching.
- Colour facet: garment colour from `media_refs.dominant_colors`, aggregated per business; this is separate from cluster hue and answers "white bazin", "blue Getzner".
- Re-run monthly and before each holiday peak.

### S9. Query understanding (search time)

- Goal: turn a natural-language query into filters plus a semantic query, in the user's language.
- Output: `{garment_concept_ids, fabric_concept_ids, occasion_ids, gender, colors, business_types, budget: {currency, max}, location: {near: place | null, radius_km, ships_to: country | null}, custom_or_ready, luxury_tier, free_text}`.
- Examples: "luxury white Bazin boubou maker for a Senegalese wedding in NYC" → garment grand boubou, colour white, occasion wedding, business types tailor and couture designer, near New York with fallback to ships-to US, luxury tier. "bazin riche femme moins de 200 euros livraison France" → garment women's bazin outfits, budget 200 EUR, ships-to FR.
- Guardrails: never require a filter the index cannot satisfy; when the parse is uncertain, fall back to semantic search and say which filters were applied.

### S10. Taxonomy and demand miner

- Sources: search-engine autocomplete and People Also Ask for seed terms, TikTok search suggestions, Google Trends related queries where retrievable, Reddit and Quora questions, and above all `query_log`.
- Output rows into `search_terms` with intent and mapped concepts; a monthly gap report per business (concepts buyers search for that the business's evidence never mentions). The gap report is the seed of the vendor-facing product.

### S11. QA sampler

- Weekly: 50 random records plus 50 risk-weighted (new merges, high scores with few evidence items, price outliers). Two independent LLM judgements with different prompts; disagreements and rule violations go to a review queue for Jim and Claude to check. Track per-field precision over time in `ingest_runs.notes`.

## 7. Search, geography and clustering ("colour-coded vectorisation")

Retrieval flow:

1. Parse the query (S9).
2. Hard filters: business status active or dormant, objection not set, ships-to or geo constraint if the user set one, budget if set (on `prices.usd_equivalent`), business types if set.
3. Candidate scoring: `rank = 0.45·query_match + 0.35·quality_score + 0.20·geo_fit`, where `query_match` blends full-text match on concept labels (BM25 via Postgres full text) with cosine similarity to the query embedding, and image similarity when the user supplies an image or picks a style tile.
4. Group the top results by cluster and show the cluster label and hue, so a broad query ("bazin for Tabaski") reads as a browsable set of styles, while a narrow one ("white grand boubou tailor within 20 km of Harlem") reads as a ranked list.

Geography model:

- Every location has a PostGIS point and an H3 resolution-7 cell. "Near me" is a radius query on the point; local browsing uses the H3 cell and its ring.
- `ships_to` rows make cross-border sellers eligible for a region without pretending they are local; the UI labels them "ships to you" and "diaspora corridor" (Dakar or Bamako to the user's country).
- Accuracy when narrowing: quality scores are region-independent, so narrowing never changes how good a result is, only which results are eligible. If a narrowed query returns fewer than five recommendable results, the API appends ships-to results and says so rather than padding with weak locals.

Clusters are the "broad" mode; filters are the "narrow" mode; both use the same score. Cluster hue is a UI aid, garment colour is a facet, and the two must not be confused in the interface.

## 8. Quality control without reviewers

- Triangulation rules in the scorer: phone consistency across platforms, cross-platform identity, review presence, repeated posting, brand-partner listings.
- Negative evidence: duplicate images across accounts (perceptual hash), stock images, scam and complaint searches, negative review share.
- Two-pass model judging with disagreement routing (S11).
- Audits: 50 records a week reviewed by Jim and Claude against the evidence links; findings feed weight and prompt changes.
- Recommended optional spend: two culturally fluent diaspora reviewers (Senegalese and Malian, French-speaking) at about $75–100 each for a one-off 200-record gold set, sourced from Upwork or Fiverr. This is the cheapest way to know whether the scores mean anything. It fits inside the budget below.

## 9. Budget ($1,000 ceiling, eight weeks)

Model prices from the Claude API reference: Opus 5 $5 input / $25 output per million tokens; Sonnet 5 $2 / $10; Haiku 4.5 $1 / $5; Message Batches at half price. Token volumes are assumptions for 3,000 profiles, 60,000 posts and 15,000 classified thumbnails (five per profile).

| Item | Basis | Opus 5 everywhere (batch) | Opus 5 for enrichment, Haiku 4.5 for bulk (batch) |
|---|---|---|---|
| Post classification (S5) | 60,000 posts × ~400 input, ~150 output tokens | ~$170 | ~$35 |
| Thumbnail vision (S5) | 15,000 images × ~1,500 input tokens | ~$60 | ~$12 |
| Profile enrichment (S4) | 3,000 × ~3,000 input, ~500 output | ~$40 | ~$40 (kept on Opus) |
| Relevance gate (S2) | 8,000 × ~800 input, ~80 output | ~$20 | ~$4 |
| Cluster labels, QA judging, query parsing | small | ~$20 | ~$15 |
| Text embeddings | 3,000 businesses + 60,000 observations | under $10 | under $10 |
| Scrapers (Apify plans and usage) | section 5 | $150–200 | $150–200 |
| Web search API (Brave, Google Programmable Search) | ~10,000 queries | $30–60 | $30–60 |
| Postgres on Render | 2 months | $15–40 | $15–40 |
| Domain and hosting for the search page | — | ~$20 | ~$20 |
| Optional gold-set reviewers | 2 people | $150–200 | $150–200 |
| **Total** | | **~$690–840** | **~$480–640** |

Both fit. The Opus-everywhere column buys higher ceiling on the bulk stages; the mixed column buys headroom for a second crawl before Korité. Jim decides.

## 10. Partnership targets for Jim

These are B2B relationship conversations with companies, which is a different posture from vendor prospecting: functional addresses, opt-out email, CAN-SPAM in the US, and no sole traders. Ordered by leverage.

| Target | Who | Why | The ask |
|---|---|---|---|
| Getzner Textil, Business Unit Africa | Tobias König, Head of Business Unit Africa (Bludenz, Austria) | They have no dealer locator, no partner-store chain, no verification tool, and a counterfeit problem; we can be the authorized-stockist layer | Confirm their partner list; pilot a "verified Getzner stockist" badge; explore co-marketing before Tabaski 2027 |
| Sy Getzner / SBG, Dakar | Ousmane Sy (sbg-sn.com; Sea Plaza boutique) | Getzner's flagship partner in Senegal; credibility with Dakar sellers | Verified partner listing; introductions to tailors they supply |
| Bathily Business Group, Bamako | Baka Bathily (ACI 2000 boutique; Semaine du Boubou) | Getzner's decades-long Mali partner; Semaine du Boubou is a discovery event | Same as above; event presence |
| Mama Getzner, Paris and Harlem | Owner (Château Rouge, 44-50 rue Polonceau; 253 W 116th St) | Owns the Paris search query; runs WhatsApp live sales; offers tailoring | Verified listing; referral of the tailors they work with |
| JLH Diffusions, France | Wholesale Getzner supplier to Dakar, Bamako, Abidjan resellers; publishes an anti-fake guide | Reseller network across three countries | Reseller list for verified listings; co-author the authenticity guide |
| Empire Textiles (UK), Jansen Holland (NL), Majestic London | Getzner distributors in the UK and EU | Coverage of UK and Benelux diaspora | Verified listings; product feeds |
| Afrikrea / Global Shop Group | New owners after the October 2025 acquisition; relaunched August 2026 | 22,000 sellers, Rich Bazin category, diaspora demand | Feed or affiliate partnership; they gain discovery, we gain structured supply |
| Tailor SaaS: Tailora, CoutureSo, CouturArt, Digitailleur, Stylebitt | Founders | Their customers are exactly the makers we want, already structured | Opt-in directory sync for their tailors |
| Yombal.sn, Malicouture.com | Founders | Dakar and Mali tailor supply; possible overlap | Listing partnership or acquisition of their tailor directory |
| DT Couture, Broderie Machine (YouTube) | Channel owners | Large Francophone audiences of tailors and buyers | Content partnership; "find a maker" links |
| Little Africa (Paris), diaspora associations in New York and Lombardy, wedding planners (e.g. Happiness Dakar) | Editors and organisers | Demand-side distribution before Korité and Tabaski | Cross-links, a directory page on their sites, event presence |

## 11. Sprint 1 (two weeks)

Deliverables:

1. Postgres provisioned with the schema; `source_policies` seeded; privacy notice and takedown form live at the future domain.
2. Concepts and labels loaded from `taxonomy-seed.md`; S1 query matrix generated and reviewed.
3. Instagram, TikTok, Etsy, YouTube and Overture ingestion running end to end into `observations` for Dakar, Bamako, Paris, New York and Lagos, capped at 1,000 profiles.
4. S2 relevance gate and S3 identity resolver on those profiles; first audit of 100 items.
5. S4 and S5 on the first 300 businesses; first scores with weights v0.1; first cluster run.
6. A `/search` endpoint with S9 parsing, filters and hybrid ranking, plus a one-page UI.
7. Cotera evidence agent (S6) writing into `evidence` for 100 businesses.

What Jim provides: the Render workspace choice (or another Postgres), API keys for Apify, Brave Search, YouTube Data API, Etsy (developer account), Anthropic, and the way Cotera agents will write to Postgres or to the HTTP endpoint.

Success criteria for the sprint: 300 scored businesses, ≥ 85% precision on the relevance audit, ≤ 3 false merges in 100 pairs, a working search that returns sensible results for the four buyer queries in the thesis.

## 12. Open questions

1. Runtime split as proposed in 3.3, or everything in Cotera?
2. Nigeria in v1 (assumed yes)?
3. Opus 5 everywhere, or Opus 5 for enrichment and Haiku 4.5 for bulk classification?
4. Spend $150–200 of the budget on two gold-set reviewers (recommended)?
5. Python as the implementation language (assumed)?
