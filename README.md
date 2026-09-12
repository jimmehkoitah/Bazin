# Bazin discovery engine

A structured discovery engine for Bazin fabric and West African formalwear vendors: tailors, couture makers, embroiderers, fabric shops and wholesalers across West Africa and the diaspora. It finds vendors from public sources, extracts structured facts with evidence, scores them deterministically, clusters them for browsing, and serves a search API with a small UI.

Documents: `docs/thesis-review.md` (why), `docs/decisions.md` (what was decided), `docs/v1-build-spec.md` (what is being built), `docs/taxonomy-seed.md` (vocabulary).

## Layout

```
bazin/
  config.py            settings, model routing per stage, prices
  db.py                Postgres pool, migrations (db/schema.sql), helpers
  models.py            Pydantic models; the LLM-facing ones are structured-output schemas
  taxonomy.py          concept vocabulary (data/taxonomy.yaml): matching, loading
  hubs.py              hub cities (data/hubs.yaml)
  prices.py            price parsing and USD conversion
  ingest.py            candidates -> identities -> observations/media (idempotent)
  discovery/planner.py S1 query matrix
  sources/             adapters: apify (instagram, tiktok, facebook, google maps), brave, youtube, etsy, overture/osm, shopify, website
  llm/client.py        Claude wrapper: structured outputs, Batches API, cost tracking; HeuristicLLM fallback
  llm/prompts.py       stage prompts
  pipeline/            S2 relevance, S3 identity, S4 enrich, S5 classify, S6 evidence, S7 score, S8 cluster, S11 qa
  search/              S9 parse, rank, FastAPI app, static UI (index, privacy, takedown)
  cli.py               `bazin ...` commands
db/schema.sql          canonical schema; db/migrations/*.sql for later changes
data/                  taxonomy.yaml, hubs.yaml, source_policies.yaml
tests/                 unit tests, DB-backed pipeline test, adapter fixture tests
```

## Setup

```bash
uv venv .venv && uv pip install -e ".[dev]"
cp .env.example .env          # fill in keys; everything runs without them in heuristic/fixture mode
.venv/bin/bazin db migrate
.venv/bin/bazin seed
```

Postgres 16 with `pg_trgm` is the only database requirement. For local tests a cluster on port 54329 is assumed (see `tests/conftest.py`); on Render, set `BAZIN_DATABASE_URL`.

## Running the pipeline

```bash
bazin plan --hub-priority 1                 # S1: ~1,000 queries for Dakar, Bamako, Paris, New York, Lagos
bazin ingest discover --limit 200           # run queries through the configured adapters
bazin ingest prefilter                      # rule out web results with no category vocabulary
bazin ingest profiles --limit 500           # fetch profiles -> observations, media
bazin gate                                  # S2 relevance verdicts (Haiku by default)
bazin resolve                               # S3 identity merge (rules, Sonnet tie-breaks)
bazin enrich                                # S4 structured facts (Opus)
bazin classify                              # S5 per-post concepts, colours, prices (Haiku, vision)
bazin evidence --complaints                 # S6 ratings, cross-platform, complaint search
bazin score                                 # S7 weights v0.1 + reasons/caveats
bazin cluster                               # S8 embeddings + HDBSCAN + labels
bazin qa                                    # S11 two-judge audit sample
bazin search "grand boubou brodé tailleur à Dakar"
bazin serve                                 # http://localhost:8000
bazin status
```

`bazin run-all --fixtures tests/fixtures` runs the whole thing offline against recorded payloads.

Model routing (override with `BAZIN_MODEL_<STAGE>`): relevance and classify on `claude-haiku-4-5`; enrich, cluster labels and the second QA judge on `claude-opus-5`; identity tie-breaks, query parsing and the first judge on `claude-sonnet-5`. Bulk stages go through the Message Batches API (half price). Spend is recorded in `llm_calls` and capped by `BAZIN_LLM_BUDGET_USD`.

Without `BAZIN_ANTHROPIC_API_KEY` (or with `BAZIN_FAKE_LLM=true`) every stage runs a deterministic heuristic implementation over the taxonomy. It is the baseline the model has to beat, and what the tests use.

## Tests

```bash
.venv/bin/python -m pytest -q
```

`tests/test_core.py` needs no database. `tests/test_pipeline.py` needs the local Postgres and exercises ingest, gate, resolve, enrich, classify, evidence, score, cluster and search end to end with synthetic profiles. `tests/test_sources.py` runs every adapter in fixture mode.

## Data posture

Per `docs/decisions.md`: third-party scrapers are accepted sources; every observation carries a `source_policy_id` so any source can be purged in one statement; media is never downloaded into the store (thumbnails are hotlinked, only hashes and palettes are kept); caption excerpts are capped at 300 characters; `/privacy` and `/takedown` are served by the API and an owner's removal request sets `objection_at` immediately.
