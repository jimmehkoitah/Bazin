# Sprint 1 status

Date: 2026-09-12. Branch: `claude/nice-cori-eyoobs`. Everything below runs offline in this repo; live runs need the credentials in section 4.

## 1. What is built

| Spec item | Status | Where |
|---|---|---|
| Postgres schema, migrations, source policies | Done. Schema v0.2 needs only `pg_trgm` (embeddings as float arrays, geo as lat/lon plus H3 cells). | `db/schema.sql`, `bazin/db.py`, `data/source_policies.yaml` |
| Taxonomy loaded, matcher | Done. 76 concepts, 439 labels across fr/en/wo/ha/yo/bm/it, with misspellings and market tags. Native-speaker review still pending. | `data/taxonomy.yaml`, `bazin/taxonomy.py` |
| S1 discovery planner | Done. Sprint-1 hubs (Dakar, Bamako, Paris, New York, Lagos) produce about 1,000 deduplicated queries across web search, Instagram and TikTok hashtags, Facebook, Google Maps, YouTube, Etsy, Overpass and Shopify feeds, prioritised garment × city × occasion first. Optional LLM expansion of phrasings. | `bazin/discovery/planner.py` |
| Source adapters | Apify (Instagram, TikTok, Facebook pages, Google Maps), Brave and Google CSE web search, YouTube Data API, Etsy Open API, Overpass (OSM), Shopify feeds, generic website. Fixture mode for offline runs. See section 5 for what must be verified live. | `bazin/sources/` |
| Ingestion | Done, idempotent: candidates → identities → observations → media refs, with raw payloads kept out of the database. | `bazin/ingest.py` |
| S2 relevance gate | Done. Cheap prefilter for web results, then a Haiku-class structured verdict on bio + captions + thumbnails. | `bazin/pipeline/relevance.py` |
| S3 identity resolution | Done. Rules (shared phone or wa.me, cross-link, same website, shared image hashes) with a Sonnet tie-break; merges businesses. | `bazin/pipeline/identity.py` |
| S4 enrichment | Done. Opus-class structured extraction with evidence quotes; writes locations (geocoded to hubs, H3 cells), contacts (E.164), offers, prices (USD equivalent), ships-to, evidence rows. | `bazin/pipeline/enrich.py` |
| S5 post classification | Done. Concepts, colours, price mentions, intent per post; perceptual hash and colour palette per thumbnail; duplicate-image evidence across accounts. | `bazin/pipeline/classify.py` |
| S6 evidence | Done in code (Cotera not used): ratings from map places and marketplaces, cross-platform identity, repeated posting, conservative complaint search. | `bazin/pipeline/evidence.py` |
| S7 scoring | Done. Weights v0.1 exactly as specified, deterministic, versioned, with feature snapshots; reasons and caveats written by the model from the snapshot only. | `bazin/pipeline/score.py` |
| S8 clustering | Done. Voyage multimodal embeddings (hash embedder offline), PCA + HDBSCAN, noise reassignment, Opus-written labels, hues carried across runs by centroid matching. | `bazin/pipeline/cluster.py` |
| S9 query parsing, hybrid search | Done. `rank = 0.45·query_match + 0.35·quality + 0.20·geo_fit`; local, ships-to and corridor geo fits; thin-local fallback note; clusters returned with hues. | `bazin/search/parse.py`, `bazin/search/rank.py` |
| S11 QA sampler | Done. Random plus risk-weighted sample, two judges with different prompts, disagreements to `audit_queue`. | `bazin/pipeline/qa.py` |
| API and UI | Done. `/search`, `/business/{id}`, `/takedown` (owner removal sets `objection_at` immediately), `/privacy`, `/health`, query logging; one-page UI with cluster legend, cards, contact links. | `bazin/search/api.py`, `bazin/search/static/` |
| CLI | Done. `bazin db migrate`, `seed`, `plan`, `ingest discover|prefilter|profiles`, `gate`, `resolve`, `enrich`, `classify`, `evidence`, `score`, `cluster`, `qa`, `search`, `serve`, `status`, `run-all`. | `bazin/cli.py` |
| LLM layer | Done. Structured outputs (Pydantic schemas), Message Batches for bulk stages, per-call cost recording, budget cap, per-stage model routing, and a deterministic heuristic fallback that runs the whole pipeline without a key. | `bazin/llm/` |
| Tests | 13 core and end-to-end tests green (taxonomy, planner, prices, identity rules, scoring, URL resolution, heuristic LLM, and a database-backed run of ingest → gate → resolve → enrich → classify → evidence → score → cluster → search → QA on synthetic vendors). Adapter fixture tests in `tests/test_sources.py`. | `tests/` |
| Deployment | `render.yaml` blueprint: Postgres, web service, daily pipeline cron, weekly cluster/QA cron. | `render.yaml` |

Model routing as agreed: Haiku 4.5 for the relevance gate and post classification; Opus 5 for enrichment, cluster labels and the second QA judge; Sonnet 5 for identity tie-breaks, query parsing and the first judge. Override any stage with `BAZIN_MODEL_<STAGE>`.

## 2. What is not done from the sprint-1 list

- Live ingestion has not run: this sandbox cannot reach Apify, Brave, Etsy, Overpass or the social sites. The adapters were written against the vendors' documented APIs and tested on fixtures shaped like their outputs; the first live run will need a verification pass (section 5).
- Gold-set reviewers: approved but not yet recruited. Recruiting text is in section 6.
- Classifieds crawlers (CoinAfrique, Expat-Dakar, Jiji) and Afrikrea crawl: not built yet (sprint 2).
- The GDPR privacy notice is a draft pending legal review; it is served at `/privacy`.

## 3. How to run it

Offline demo (no keys):

```bash
uv venv .venv && uv pip install -e ".[dev]"
BAZIN_FAKE_LLM=true bazin run-all --fixtures tests/fixtures
bazin serve   # http://localhost:8000
```

Live: set the keys below in `.env` (or Render), then the same commands without `--fixtures` and without `BAZIN_FAKE_LLM`.

## 4. What Jim provides

| Item | Why | Notes |
|---|---|---|
| Anthropic API key (`BAZIN_ANTHROPIC_API_KEY`) | All model stages | Budget cap defaults to $400 via `BAZIN_LLM_BUDGET_USD` |
| Voyage AI key (`BAZIN_VOYAGE_API_KEY`) | Embeddings for clustering and semantic search | Free tier covers sprint 1 volumes |
| Apify token (`BAZIN_APIFY_TOKEN`) | Instagram, TikTok, Facebook pages, Google Maps | Starter plan; usage estimate $150–200 for the sprint |
| Brave Search API key (`BAZIN_BRAVE_API_KEY`) | URL discovery | Or Google Programmable Search (`BAZIN_GOOGLE_CSE_KEY` + `_CX`) |
| YouTube Data API key (`BAZIN_YOUTUBE_API_KEY`) | Free | Google Cloud console |
| Etsy developer key (`BAZIN_ETSY_API_KEY`) | Listings and shops | Personal app first; Commercial Access needs a review |
| Render workspace | Postgres and cron jobs | Apply `render.yaml`; or run everything on a laptop with a local Postgres |
| A domain (optional now) | Privacy and takedown pages must be reachable before the first crawl | Any subdomain works |

## 5. Verify on the first live run

- Apify actor input and output field names (`apify/instagram-scraper`, `clockworks/tiktok-scraper`, `apify/facebook-pages-scraper`, `compass/crawler-google-places`) against the adapters' mapping functions; the fixtures encode our best reading of the current schemas.
- Brave Search API quotas and the `country`/`search_lang` parameters for Senegal, Mali and Nigeria.
- Etsy Open API rate limits at the Personal tier (5 requests per second).
- Overpass query timeouts for the Paris and Lagos bounding boxes; shrink the box if needed.
- Thumbnail fetching from Instagram and TikTok CDNs from Render's IPs (signed URLs expire; the classifier skips images it cannot fetch).

## 6. Reviewer recruiting (approved spend, $150–200)

Post on Upwork or Fiverr: "Two reviewers, French-speaking, familiar with Senegalese or Malian fashion (bazin, boubous, Tabaski outfits). Task: review 200 vendor records (name, links, type, city, contact, sample posts) in a spreadsheet and mark whether each is a real vendor, whether the type and city are right, and whether you would recommend them to a family member, with a one-line note. About 6 hours. $75–100." The records come from `bazin qa` output plus a random sample; the spreadsheet export is a one-liner over `businesses` and `evidence`.

## 7. Next (sprint 2)

- First live crawl on the five hubs, capped at 1,000 profiles; measure yields against the funnel targets in the build spec.
- Audit 100 relevance verdicts and 100 identity pairs; tune prompts and weights v0.2 from the gold set.
- Classifieds and Afrikrea crawlers; Pinterest.
- Programmatic pages per city × garment × occasion with schema.org markup, so the index is itself discoverable.
- Claim flow (`claims` table exists; no UI yet).
