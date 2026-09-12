# Decision log

Decisions made by Jim on 2026-09-12 in response to the thesis review, and their consequences for the build. Newer entries go at the bottom.

| # | Decision | Rationale | Consequences |
|---|---|---|---|
| D1 | No vendor prospecting in v1. Vendors are marketed to only once they are on the platform and want an AEO advantage. | Buyers first; vendor monetization follows demand. | The KASPR-style exposure (scraped contacts monetised through outreach) is off the table. The Article 14 notice and objection flow still exist, but no outbound campaign. Marketing to claimed vendors happens with opt-in collected at claim time. |
| D2 | Accept off-terms scraping risk for Instagram, TikTok, Facebook and similar platforms. | Breadth of supply matters more than platform-terms purity for a discovery engine that links out. | Scrapers are allowed sources. Mitigations that remain in force because they are cheap and bound the downside: link out and never rehost media; keep caption excerpts short; per-observation source policy so any source can be purged; robots.txt honoured on first-party sites; public privacy notice and one-click objection; no Google Places content stored beyond place IDs. Residual risks: IP blocks, account bans, cease-and-desist letters, and a scraper vendor being enjoined mid-project. Design for those operationally (multiple vendors, retry, idempotent reruns). |
| D3 | Breadth: as many vendors as can be found, across all target markets, including Nigeria. | "We want as many vendors as we can find." | The taxonomy carries both Francophone and Nigerian vocabularies from day one (see taxonomy-seed.md). Grouping and geography must make breadth usable: clusters for broad browsing, geo narrowing for local results, with identical scoring in both modes. |
| D4 | No human reviewers. Quality control comes from scraped review data, tool lookups available in Cotera (for example Facebook reviews), triangulation across sources, and model-based judging with audits. | No reviewer pool available. | Evidence collection is a first-class pipeline stage with tools. Scoring must be deterministic over evidence so it can be audited. A small paid reviewer spend remains recommended but optional (see build spec, section 8). |
| D5 | Budget: up to $1,000 now. | — | Budget plan in the build spec, section 9. Opus-tier models by default; cheaper models for bulk stages are Jim's call. |
| D6 | Partnerships are Jim's lane. No lists or relationships today, but Jim is in sales and will prospect stakeholders if partnership is the right lane. | B2B relationship building is a different legal posture from vendor prospecting: companies at functional addresses, opt-out email, CAN-SPAM in the US. | Partnership target list in the build spec, section 10. Priority: Getzner Business Unit Africa and its named partners, Afrikrea, tailor SaaS vendors, diaspora media and associations. |

## Assumptions carried until Jim confirms

- A1: The pipeline runs as Python code in this repo for bulk work (scraping, ETL, scoring, search), with Cotera agents used where Cotera has tools the code does not (review lookups), all sharing one Postgres. Alternative: everything in Cotera with Postgres as the store.
- A2: Postgres lives on Render (the connected workspace needs selecting) with pgvector and PostGIS.
- A3: Python is the implementation language.
- A4: Nigeria is in v1 scope (per D3), with its own vocabulary and garments.
