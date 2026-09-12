-- Bazin discovery engine: system-of-record schema (v0.2)
-- Postgres 16. Only pg_trgm is required. Embeddings are float arrays (in-process ANN is fine at
-- this scale); geography is lat/lon plus H3 cells. Observations are immutable; business facts are derived.

create extension if not exists pg_trgm;

do $$ begin
  create type business_type as enum (
    'fabric_retailer','fabric_wholesaler','brand_partner','tailor','couture_designer',
    'embroiderer','rtw_seller','marketplace_seller','unknown');
exception when duplicate_object then null; end $$;

do $$ begin
  create type business_status as enum (
    'candidate','active','dormant','closed','suspected_scam','duplicate','removed');
exception when duplicate_object then null; end $$;

do $$ begin
  create type platform as enum (
    'instagram','tiktok','facebook','youtube','pinterest','snapchat','etsy','afrikrea','amazon',
    'jumia','coinafrique','expat_dakar','jiji','shopify','website','google_maps','yelp',
    'osm','overture','whatsapp','web','other');
exception when duplicate_object then null; end $$;

do $$ begin
  create type acquisition_method as enum (
    'vendor_submitted','claimed','manual','official_api','open_data','first_party_crawl',
    'third_party_scraper','serp','feed');
exception when duplicate_object then null; end $$;

-- Which sources are allowed, how long their content may be kept, and whether media may be stored.
create table if not exists source_policies (
  id             serial primary key,
  platform       platform not null,
  method         acquisition_method not null,
  terms_status   text not null check (terms_status in ('compliant','grey','off_terms')),
  retention_days int,                          -- null = indefinite
  store_media    boolean not null default false,
  notes          text,
  unique (platform, method)
);

create table if not exists businesses (
  id                        uuid primary key default gen_random_uuid(),
  canonical_name            text not null,
  business_type             business_type not null default 'unknown',
  business_type_confidence  real,
  status                    business_status not null default 'candidate',
  legal_entity_type         text check (legal_entity_type in ('company','sole_trader','unknown')) default 'unknown',
  primary_country           char(2),
  languages                 text[] not null default '{}',
  description               text,                -- our own generated summary, never copied text
  text_embedding            real[],
  image_embedding           real[],              -- mean of media embeddings
  quality_score             real,                -- latest scores.total, denormalised for search
  first_seen_at             timestamptz not null default now(),
  last_observed_active_at   timestamptz,
  notice_sent_at            timestamptz,         -- GDPR art. 14 notice
  objection_at              timestamptz,         -- right to object exercised
  duplicate_of              uuid references businesses(id),
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);
create index if not exists businesses_name_trgm on businesses using gin (canonical_name gin_trgm_ops);
create index if not exists businesses_status on businesses (status, quality_score desc);

-- One business, many handles.
create table if not exists identities (
  id               uuid primary key default gen_random_uuid(),
  business_id      uuid references businesses(id) on delete cascade,
  platform         platform not null,
  handle           text,
  url              text not null,
  external_id      text,
  display_name     text,
  bio              text,                         -- short profile text as shown publicly (<= 600 chars)
  bio_link         text,
  followers        int,
  is_primary       boolean not null default false,
  match_confidence real,
  match_evidence   jsonb,
  last_crawled_at  timestamptz,
  created_at       timestamptz not null default now(),
  unique (platform, url)
);
create index if not exists identities_business on identities (business_id);
create index if not exists identities_handle on identities (platform, lower(handle));

create table if not exists locations (
  id            uuid primary key default gen_random_uuid(),
  business_id   uuid not null references businesses(id) on delete cascade,
  kind          text not null check (kind in ('atelier','shop','pickup','market_stall','online_only','ships_to')),
  country       char(2),
  region        text,
  city          text,
  address       text,
  lat           double precision,
  lon           double precision,
  h3_r5         text,                            -- H3 cells for local narrowing (r5 ~ 250 km2, r7 ~ 5 km2)
  h3_r7         text,
  confidence    real,
  evidence_observation_id uuid
);
create unique index if not exists locations_unique on locations (business_id, kind, coalesce(country, ''), coalesce(city, ''));
create index if not exists locations_h3r5 on locations (h3_r5);
create index if not exists locations_h3r7 on locations (h3_r7);
create index if not exists locations_country on locations (country, kind);

create table if not exists contact_channels (
  id                 uuid primary key default gen_random_uuid(),
  business_id        uuid not null references businesses(id) on delete cascade,
  kind               text not null check (kind in ('whatsapp','phone','email','instagram_dm','website','wa_catalog','snapchat','telegram','other')),
  value              text not null,
  normalized_value   text,                       -- E.164 for numbers, lowercase for emails, host for websites
  verified_at        timestamptz,
  do_not_contact     boolean not null default false,
  suppression_reason text,
  evidence_observation_id uuid,
  unique (business_id, kind, normalized_value)
);
create index if not exists contact_channels_norm on contact_channels (kind, normalized_value);

-- Immutable record of something we saw. Never store full captions or media bytes.
create table if not exists observations (
  id                 uuid primary key default gen_random_uuid(),
  identity_id        uuid references identities(id) on delete set null,
  business_id        uuid references businesses(id) on delete set null,
  platform           platform not null,
  source_url         text not null,
  external_id        text,
  kind               text not null check (kind in ('post','reel','video','listing','profile','review','page','map_place','ad','other')),
  observed_at        timestamptz not null default now(),
  published_at       timestamptz,
  caption_excerpt    text check (char_length(caption_excerpt) <= 300),
  hashtags           text[],
  mentions           text[],
  language           text,
  engagement         jsonb,
  raw_ref            text,                       -- pointer to the raw payload store, not content
  acquisition_method acquisition_method not null,
  source_policy_id   int references source_policies(id),
  extractor_version  text,
  content_hash       text,
  unique (platform, source_url)
);
create index if not exists observations_business on observations (business_id, published_at desc);
create index if not exists observations_identity on observations (identity_id);

create table if not exists media_refs (
  id               uuid primary key default gen_random_uuid(),
  observation_id   uuid not null references observations(id) on delete cascade,
  media_url        text not null,
  thumbnail_url    text,
  oembed_url       text,
  phash            text,                         -- perceptual hash for duplicate detection
  dominant_colors  jsonb,                        -- [{"name":"white","hex":"#f4f4f2","share":0.61}, ...]
  visual_tags      text[],
  image_embedding  real[],
  width            int,
  height           int,
  unique (observation_id, media_url)
);
create index if not exists media_phash on media_refs (phash);

-- Controlled vocabulary. Search terms map to concepts; observations are tagged with concepts.
create table if not exists concepts (
  id              text primary key,
  kind            text not null check (kind in ('fabric','garment','technique','occasion','style','color','business_type','signal')),
  parent_id       text references concepts(id),
  canonical_label text not null,
  notes           text
);

create table if not exists concept_labels (
  concept_id  text not null references concepts(id) on delete cascade,
  label       text not null,
  language    text not null,
  market      text,
  weight      real not null default 1.0,
  primary key (concept_id, label, language)
);
create index if not exists concept_labels_label on concept_labels (lower(label));

create table if not exists observation_concepts (
  observation_id    uuid references observations(id) on delete cascade,
  concept_id        text references concepts(id),
  confidence        real,
  extractor_version text,
  primary key (observation_id, concept_id)
);

-- Aggregated per business; recomputed by the scorer.
create table if not exists business_concepts (
  business_id       uuid references businesses(id) on delete cascade,
  concept_id        text references concepts(id),
  evidence_count    int not null default 0,
  last_evidence_at  timestamptz,
  score             real,
  primary key (business_id, concept_id)
);

create table if not exists offers (
  id                  uuid primary key default gen_random_uuid(),
  business_id         uuid not null references businesses(id) on delete cascade,
  observation_id      uuid references observations(id),
  garment_concept_id  text references concepts(id),
  fabric_concept_id   text references concepts(id),
  gender              text check (gender in ('women','men','children','unisex','unknown')),
  custom_or_ready     text check (custom_or_ready in ('custom','ready','both','unknown')),
  lead_time_days      int,
  evidence            text,
  observed_at         timestamptz not null default now()
);
create index if not exists offers_business on offers (business_id);

create table if not exists prices (
  id                  uuid primary key default gen_random_uuid(),
  business_id         uuid not null references businesses(id) on delete cascade,
  observation_id      uuid references observations(id),
  offer_id            uuid references offers(id),
  price_type          text not null check (price_type in ('fabric','tailoring','complete_outfit','embroidery','shipping','other')),
  currency            char(3) not null,
  amount_min          numeric,
  amount_max          numeric,
  unit                text check (unit in ('metre','yard','piece','3m','4m','5m','5yd','10yd','outfit','item','kg','unknown')),
  includes_fabric     boolean,
  includes_embroidery boolean,
  includes_tailoring  boolean,
  is_promo            boolean not null default false,
  is_negotiable       boolean,
  currency_inferred   boolean not null default false,
  usd_equivalent      numeric,
  evidence            text,
  observed_at         timestamptz not null default now()
);
create index if not exists prices_business on prices (business_id, price_type);

-- Anything that supports or undermines a business. Powers scoring; auditable.
create table if not exists evidence (
  id               uuid primary key default gen_random_uuid(),
  business_id      uuid not null references businesses(id) on delete cascade,
  kind             text not null check (kind in (
                     'review','tagged_customer_post','fitting_video','finished_garment','embroidery_closeup',
                     'before_after','marketplace_listing','phone_number','website','repeated_posting',
                     'pricing_clarity','physical_address','brand_partner_listing','cross_platform_identity',
                     'duplicate_image','stock_image','scam_report','negative_review','other')),
  polarity         smallint not null default 1 check (polarity in (-1, 1)),
  source_url       text,
  observation_id   uuid references observations(id),
  extracted_claim  text check (char_length(extracted_claim) <= 300),
  rating           numeric,
  rating_scale     numeric,
  review_count     int,
  confidence       real,
  observed_at      timestamptz not null default now(),
  collected_by     text
);
create index if not exists evidence_business on evidence (business_id, kind);

-- Score history. Never overwritten; the latest row is the live score.
create table if not exists scores (
  id                  uuid primary key default gen_random_uuid(),
  business_id         uuid not null references businesses(id) on delete cascade,
  weights_version     text not null,
  category_relevance  real,
  commercial_clarity  real,
  maker_credibility   real,
  trust               real,
  freshness           real,
  total               real not null,
  inputs              jsonb not null,
  reasons             text[],
  caveats             text[],
  computed_at         timestamptz not null default now()
);
create index if not exists scores_business_latest on scores (business_id, computed_at desc);

create table if not exists clusters (
  id          uuid primary key default gen_random_uuid(),
  run_id      text not null,
  label       text,
  description text,
  hue         smallint check (hue between 0 and 359),
  centroid    real[],
  size        int,
  primary_concepts text[],
  created_at  timestamptz not null default now()
);

create table if not exists business_clusters (
  business_id     uuid references businesses(id) on delete cascade,
  cluster_id      uuid references clusters(id) on delete cascade,
  run_id          text not null,
  membership_prob real,
  primary key (business_id, run_id)
);

create table if not exists search_terms (
  id            uuid primary key default gen_random_uuid(),
  term          text not null,
  language      text,
  market        text,
  intent        text check (intent in ('buy_fabric','find_tailor','style_inspiration','price_comparison','authenticity_check','shipping','other')),
  concept_ids   text[],
  source        text not null,
  volume_proxy  numeric,
  observed_at   timestamptz not null default now(),
  unique (term, language, market, source)
);

-- Every consumer query from day one.
create table if not exists query_log (
  id                    bigserial primary key,
  ts                    timestamptz not null default now(),
  raw_query             text not null,
  parsed                jsonb,
  user_region           text,
  result_count          int,
  clicked_business_ids  uuid[],
  session_hash          text
);

create table if not exists claims (
  id                   uuid primary key default gen_random_uuid(),
  business_id          uuid not null references businesses(id) on delete cascade,
  claimant_email       text,
  claimant_phone       text,
  verification_method  text,
  verified_at          timestamptz,
  marketing_opt_in     boolean not null default false,
  created_at           timestamptz not null default now()
);

create table if not exists takedown_requests (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references businesses(id) on delete set null,
  requester    text,
  reason       text,
  source_url   text,
  received_at  timestamptz not null default now(),
  resolved_at  timestamptz,
  action       text
);

-- Discovery plan and its results.
create table if not exists discovery_queries (
  id            uuid primary key default gen_random_uuid(),
  query         text not null,
  language      text,
  market        text,
  platform      platform not null,
  tool          text not null,                   -- adapter name, e.g. 'apify_instagram', 'brave', 'youtube'
  priority      int not null default 5,          -- 1 = run first
  status        text not null default 'pending' check (status in ('pending','running','done','failed','skipped')),
  last_run_at   timestamptz,
  results_count int,
  created_at    timestamptz not null default now()
);
create unique index if not exists discovery_queries_unique on discovery_queries (platform, query, coalesce(market, ''));
create index if not exists discovery_queries_status on discovery_queries (status, priority);

create table if not exists candidates (
  id                 uuid primary key default gen_random_uuid(),
  discovery_query_id uuid references discovery_queries(id) on delete set null,
  platform           platform not null,
  url                text not null,
  handle             text,
  external_id        text,
  title              text,
  snippet            text check (char_length(snippet) <= 300),
  thumbnail_url      text,
  source_json        jsonb,                      -- the small, non-content payload we keep (counts, ids)
  relevance          jsonb,                      -- S2 verdict
  relevant           boolean,
  identity_id        uuid references identities(id) on delete set null,
  created_at         timestamptz not null default now(),
  unique (platform, url)
);
create index if not exists candidates_relevant on candidates (relevant, platform);

-- LLM spend, per call or per batch item.
create table if not exists llm_calls (
  id                bigserial primary key,
  ts                timestamptz not null default now(),
  stage             text not null,
  model             text not null,
  batch_id          text,
  custom_id         text,
  input_tokens      int not null default 0,
  output_tokens     int not null default 0,
  cache_read_tokens int not null default 0,
  cost_usd          numeric(10,6) not null default 0
);
create index if not exists llm_calls_stage on llm_calls (stage, ts);

-- S11 review queue.
create table if not exists audit_queue (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references businesses(id) on delete cascade,
  reason       text not null,
  judge_a      jsonb,
  judge_b      jsonb,
  agreed       boolean,
  created_at   timestamptz not null default now(),
  resolved_at  timestamptz,
  resolution   text
);

create table if not exists ingest_runs (
  id          uuid primary key default gen_random_uuid(),
  stage       text not null,
  source      text,
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  items_in    int,
  items_out   int,
  cost_usd    numeric,
  notes       text
);

create table if not exists schema_migrations (
  name        text primary key,
  applied_at  timestamptz not null default now()
);
