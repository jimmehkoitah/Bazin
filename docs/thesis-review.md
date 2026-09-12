# Bazin discovery engine — thesis and plan review

Date: 2026-09-12. Status: review of the founding thesis, data model, ranking rubric, agent list and MVP plan, with due diligence on the claims the plan depends on.

## 0. How this review was produced, and its limits

- Four research threads ran in parallel: platform access and legal exposure; competitors and supply sources; category terminology, prices, geography and seasonality; monetization comparables.
- Direct fetches of primary pages (Getzner, Etsy, Meta, Wikipedia, Senegalese press, etc.) were blocked by this environment's egress policy. Findings therefore rest on search-engine snippets of those pages, captured on 2026-09-12. Anything that a snippet did not settle is marked unverified. Numbers from snippets are capped at medium confidence.
- Login-gated figures (Instagram hashtag totals, Facebook group member counts, Afrikrea's 2026 commission rate) could not be read. Section 12 lists what still needs a logged-in browser session.
- Nothing here is legal advice. The legal section identifies exposure and a defensible posture; a lawyer should sign off before vendor outreach at scale.

## 1. Verdict in brief

The wedge is real but narrower than written, and the plan's assumed engine (crawling Instagram and TikTok) is its weakest part.

1. **"Under-indexed" is true for tailors, couture makers and physical shops, and false for fabric-by-the-yard.** A search for "bazin riche boubou tailor new york" returns zero New York tailors on page one; "trouver un tailleur Dakar" returns blogs and tailoring SaaS tools. But "where to buy authentic getzner bazin online" returns AliExpress, Etsy and Alibaba, i.e. the counterfeit channels, with Getzner's own shop absent. Fabric is over-indexed by the wrong sellers. The gap is services and authenticity, not listings.
2. **The plan conflates three products.** Fabric purchase (commodity, counterfeit risk), garment making (trust and craft service), and ready-to-wear (product). They have different intents, ranking signals, competitors and willingness to pay. Pick makers and tailors as the wedge; treat fabric retail as a secondary facet anchored on authenticity.
3. **The supply does not live where the plan looks.** The densest Bazin commerce is in French-language Facebook sales groups, WhatsApp catalogues, TikTok "vendeur de bazin" content and, in Senegal, Snapchat. Twitter and Reddit have almost none. Instagram matters but is login-walled. Pinterest and YouTube are large, public and ignored by the plan.
4. **Nobody owns the whole space, but "nobody" is wrong.** Afrikrea (ex-ANKA) has 22,000+ sellers and a Rich Bazin category, went through liquidation in 2025, and relaunched as a consumer marketplace on 2026-08-27 under new owners. Yombal (Dakar), Sokofa (diaspora made-to-measure, July 2026), Stitches Africa (Lagos), Malicouture (Mali) and a volunteer French directory (annuaire-couturiers.fr) each cover one slice. None spans retailers, tailors and authenticity across the target countries.
5. **Getzner leaves the "authorized dealer" layer unclaimed.** It has an official online shop and known partners (Bathily Business Group in Bamako, Sy Getzner in Dakar, Mama Getzner in Paris and Harlem, Empire Textiles UK, Jansen Holland NL) but no dealer locator, no partner-store chain, no consumer app and no QR verification. That is the single most valuable partnership and B2B data opportunity in the plan, and the plan does not mention it.
6. **The taxonomy has factual errors and a market-sized blind spot.** Nigeria calls the fabric "shadda" or "guinea brocade" and the garments babban riga, agbada, senator, kaftan; "bazin" is secondary there. "Atiku" is a different fabric. "GP" stands for gratuité partielle, not gratuité de passage. Details in section 2.5.
7. **The ranking rubric is gameable and, as written, risks scoring ethnicity.** "Cultural fit" scored by an LLM should become "category relevance" computed from evidence counts. Scores must be deterministic, versioned and explainable, with LLMs used for extraction only.
8. **The AEO product is sequenced backwards.** Vendors pay for orders, not for representation. Vendor monetization is only sellable once the engine sends measurable WhatsApp click-outs or influences how Google and AI assistants answer. Demand first.
9. **There is no demand-acquisition plan.** Supply cold start is solved by the data engine; demand cold start is not addressed. Programmatic SEO pages per city, garment and occasion, plus a concierge test, are the cheapest path.
10. **Seasonality should drive the whole schedule.** Korité falls around 9–10 March 2027 and Tabaski on 16–17 May 2027. Tailors stop taking custom orders roughly three to four weeks before Tabaski. Pages need to be indexed by February 2027 to catch the year's main peak.

## 2. What the research confirmed or corrected

### 2.1 Where discovery fails today (page-one composition, web results only)

| Buyer query | What page one shows | What is missing |
|---|---|---|
| "where to buy authentic getzner bazin online" | AliExpress, three Etsy pages, Alibaba showroom, Empire Textiles (UK wholesaler), Asatsu Clothing | Getzner's own shop; any official partner; any local shop |
| "bazin riche boubou tailor new york" | A Photoville art exhibition, eBay, a Facebook page, Etsy, two French e-shops, BoubouQueens, Maison Barry | Any New York tailor. Yelp and TikTok surface only when rephrased to "African tailor Harlem" |
| "getzner bazin paris château rouge" | One Facebook page, a TikTok discover page, four Mama Getzner results, then Wikipedia pages about people surnamed Bazin | Every other Château Rouge fabric shop and tailor |
| "trouver un tailleur Dakar" | A blog guide, two tailoring SaaS tools, an expat blog, TikTok, a generic directory, Yombal | Structured, filterable tailor results |

Caveat: the search tool used returns web results only. A live Google check would likely add a Maps 3-pack to the New York query, so re-verify before quoting the "zero tailors" finding.

Implication: product vocabulary ("bazin riche", "grand boubou brodé") is disconnected from local-service indexing. The engine's job is to join the two.

### 2.2 Where the supply actually lives

| Source | Evidence | Scriptable? |
|---|---|---|
| Facebook sales groups (French) | At least ten named groups: "groupe de vente Bazin vip getzner en gros", "La maison de Bazin Getzner", "Vente en gros et détails de bazin import de Dubai", Abidjan Adjamé Roxy group, etc. Member counts login-gated. | No (login-gated). Acquire by vendor self-onboarding. |
| Facebook seller pages | Vente Bazin Getzner (La Courneuve, wa.me link), Bazin Getzner Niamey, Bass Getzner and Maison du Getzner (Dakar), Mama Getzner (Paris) | Partly (public pages), fragile |
| WhatsApp catalogues | The standard order channel. Mama Getzner runs live sales on WhatsApp; Benin and Kaffrine sellers publish "appel et WhatsApp" numbers | No crawl. Contact channel only. |
| TikTok | Tag pages and dozens of auto-generated discover pages ("vente bazin riche dakar", "boutique de bazin paris", "best african tailor in nyc", "couturier nigérian à Paris"). A "Vendeur De Bazin" discover tag showed 434.9K posts (may be stale). | Public pages exist; scraping is against terms (see section 7). Use search-indexed pages only. |
| Instagram | Vendor posts in Dakar, Abidjan, Bamako, Lagos; hashtag counts no longer public | Login-walled; search-indexed pages and oEmbed only |
| Snapchat (Senegal) | "Senegal Clothing" topic with millions of clips (May 2026); Dakar boutiques put "SNAP: handle" in Instagram captions as the order channel; French press describes Snapchat as a parallel market | No |
| YouTube | DT Couture, Broderie Machine, seasonal compilations ("100+ nouveaux styles bazin riche 2026", "Tabaski 2025: la folie des tissus envahit Dakar") | Yes, official Data API |
| Pinterest | Boards with 900+ Getzner pins, 900+ bazin pins, 720 boubou styles, 180 Senegalese tailor pins; ideas hubs | Yes, public and indexed |
| Etsy | 574 "bazin riche" items; 1,000+ "getzner bazin"; grand boubous from £17 to £243, CA$145 to CA$954; titles keyword-stuff "Getzner" | Yes, Open API with attribution |
| Afrikrea / ANKA | Dedicated Rich Bazin category; raw fabric, boubous, couple sets, kids' sets; seller country tagged | Feed or partnership |
| Classifieds | CoinAfrique (SN, CI, BJ, ML, BF), Expat-Dakar, Jiji (NG, SN): price and city per ad, tailor and atelier ads | Yes (public listings) |
| Retailer web shops | Mama Getzner, Empire Textiles, Jansen Holland, dimancheabamako.com, monbazin.com | Yes (product feeds) |
| Twitter/X, Reddit | Minimal commercial signal; a few Kano per-yard price tweets | Deprioritize |

Reorder the plan's discovery sources accordingly: Etsy, Afrikrea, classifieds, retailer feeds, YouTube, Pinterest, Google Maps (for physical shops) first; Instagram and TikTok via search-indexed pages only; Facebook groups and WhatsApp via vendor self-onboarding.

### 2.3 Competitors and adjacent products

| Product | What it does | Why it matters |
|---|---|---|
| Afrikrea (ex-ANKA), Abidjan / New York | Transactional marketplace, 22,000+ sellers in 47 countries, >US$60M cumulative GMV; parent liquidated July 2025, acquired by Global Shop Group October 2025, a reported auth-token leak November 2025, relaunched as Afrikrea 2026-08-27 with ANKA kept for B2B (pay, ship) | Closest competitor and a possible feed partner. Lists what sellers upload; does not index tailors, Instagram or WhatsApp vendors, or physical shops. |
| Yombal.sn, Dakar | Made-to-measure marketplace: pick model, find tailor, buy fabric; secure payment; updated Feb 2026 | Direct competitor for Dakar tailors |
| Sokofa, Nigeria (July 2026) | Diaspora buyers to African artisans; vendor verification; AI fit preview; self-funded | Direct competitor for the diaspora made-to-measure intent |
| Stitches Africa, Lagos | AI body measurement bespoke app targeting diaspora; self-announced US$50M financing programme (single source) | Nigeria-led; watch |
| Malicouture.com, Mali | Tailor showcase with WhatsApp contact | Mali tailor supply source |
| annuaire-couturiers.fr | Volunteer directory of African tailors and fabric shops in France and worldwide | Proves the need; weak product |
| LoveWeddingsNG, BellaNaija Weddings and other wedding directories | Vendor listings; LoveWeddingsNG sells paid featured placement (price on request); BellaNaija runs a vendor programme by email | The monetization comparable that already works in Nigeria |
| Tailor back-office SaaS: Tailora, CoutureSo, CouturArt, Digitailleur, Stylebitt | Order and measurement management for tailors | Data partners, not competitors: their customers are the makers the engine wants |
| Jumia | Eight markets (NG, GH, CI, SN, KE, UG, EG, MA); not in Mali, Gambia or Benin; thin bazin inventory | Not a source |

### 2.4 Getzner

- Getzner Textil AG (Bludenz, Austria): about €490M group revenue in FY2023, roughly 1,600 staff; African clothing damasks reported as about 70% of production (medium confidence).
- Official consumer site getzner-official.at with an online shop ("buy original Getzner brocade online"), product catalogue (e.g. Super Magnum 277-21-433) and a Getzner Boutique in Lustenau; factory shop in Bludenz.
- Known partners: Bathily Business Group (Mali; boutique at Marché ACI 2000, Bamako, since 2016), Sy Getzner (Senegal; Sea Plaza boutique opened April 2023 with Tobias König, Head of Business Unit Africa, present), Mama Getzner (Paris Château Rouge, 44-50 rue Polonceau; Harlem, 253 W 116th St; wholesale from 300 m), JLH Diffusions (French wholesaler serving Dakar, Bamako, Abidjan resellers), Empire Textiles and Majestic London (UK), Jansen Holland (NL). Nigeria: "Getzner Nigeria" (@abadtextile, Kano and Abuja) and Maitangaran Textiles (Kano), official status unverified.
- No dealer locator, no partner-store chain, no consumer app, no QR or serial verification found. Authenticity cues published by Getzner: rose scent, golden edge stamp, woven brand name, branded packaging. Third-party resellers also describe a woven "Getzner Textil Austria" watermark and a hologram label. Chinese "Getzner" sells openly on AliExpress and Alibaba from US$0.35 per yard.
- Evidenced product lines: Super Magnum, Super Magnum Gold XL, Madame Getzner, Phantom XL, Super Wagambari Gold XL, Empire Getzner XL, Wifi Brocade, Yard Material, Atiku Swiss Voile; "Getzner 8" and "Empereur" (Mali resellers, medium confidence). "Chigan" and "Excellence" were not evidenced.
- Getzner sponsors Semaine du Boubou in Bamako and funds CSR projects in Sikasso and Dakar.

Opportunity: a "verified Getzner stockist" facet built from partner evidence, offered to Business Unit Africa as the dealer layer they do not have. Do not make counterfeit accusations; surface evidence and let the brand confirm.

### 2.5 Taxonomy corrections

| Plan says or implies | Correction | Confidence |
|---|---|---|
| Nigeria is a target market using the same vocabulary | Nigerian retail term is "shadda" / "shedda" or "guinea brocade", priced per yard in naira; Getzner line names (Madame Getzner, Phantom, Super Magnum) are used directly; "bazin" is secondary. Garments: babban riga (Hausa), agbada, buba and sokoto, senator, kaftan, jalabiya. Holiday: Sallah. | High |
| "Atiku" as a Bazin name (implicit in Nigeria coverage) | Atiku is a distinct plain or striped cotton "polish" fabric used for kaftans; Getzner sells an "Atiku Swiss Voile" line. Index as a sibling category. | High |
| "GP" = gratuité de passage | GP = "gratuité partielle", from discounted airline-staff tickets; now means travellers who sell baggage allowance. Roughly €10/kg Paris–Dakar versus €25–45/kg for carriers. Platforms: gprelay.com, gpma.app, colisafrique.com, gpbagage.com, Diatta Voyages. | High |
| Wolof garment terms (the draft mentioned "mbaxal") | Mbaxal is a rice dish. Garment terms in captions: taille basse (very heavy), thioup / thioub / cuub (hand-dyed bazin; "modèle thioub Tabaski 2025"), grand boubou 3 pièces, ndoket / ndokette, xaftaan / kaftan, mbubb (rarely used in captions; French "boubou" dominates). | High |
| Getzner line names ("Chigan", "Excellence") | Not evidenced. Use the list in 2.4. | Medium |
| Units are implicit | Senegal, Mali, France trade per mètre and per pièce; Nigeria, Gambia, US, UK trade per yard (5-yard, 10-yard). The price model needs both. | High |
| "Bazin Sikasso", "Getzner Malien" | Not evidenced. Evidenced Malian phrasing: "bazin malien", "bazin du Mali", "teinture artisanale made in Mali", "Getzner teinté", "gala" (the dye). | Medium |
| "Bazin prix", "Bazin wholesale" | Real caption phrasing: "vente en gros et détails", "promo", "disponible sur commande" + price + phone, "prêt à porter et sur mesure", "made in Austria / certifié authentique", "livraison". | High |
| Spelling variants absent | Add: basin riche, bazin rich, shedda, brocard (common misspelling of brocart), bubu, Djezner (Wolof transliteration of Getzner). "Guetzner" and "gitzner" were not found. | Medium |
| "Getzner" as a brand only | In francophone markets "Getzner" is used as a generic noun for the fabric ("grand boubou Getzner brodé", "Bass Getzner", "Mama Getzner"). Treat as both brand and category term. | High |
| Occasions: wedding, Eid, Tabaski, naming ceremony, formal event | Add Korité (Eid al-Fitr), Gamou / Mawlid, Grand Magal de Touba (white bazin), Christmas and New Year (Christian buyers in Senegal, Benin, Nigeria), Sallah (Nigeria), baptême / ngente. | High |
| Other countries not named | Togo (Lomé sellers), Côte d'Ivoire (Abidjan, Adjamé), Mauritania (drâa), Niger and northern Cameroon (gandoura), Guinea. | Medium |

### 2.6 Geography corrections

| Hub | Finding |
|---|---|
| New York, Harlem W 116th St | Real and named: Mama Getzner (253 W 116th), Kilimanjaro fabric and tailoring (117 W 116th), tailors inside Malcolm Shabazz Harlem Market; Yelp lists Kebe's African Fashions, AG Fashion, Yara African Fabrics, Noni Styles, Moshood. But Little Senegal is shrinking with gentrification. Bronx has embroidery shops (2024 Webster Ave). |
| Other US cities | Population data only (Senegalese and Malian communities in Philadelphia, DC, Atlanta, Chicago, Houston, Minneapolis). No shop-level evidence gathered. Cincinnati and Columbus unverified. |
| Paris, Château Rouge / Goutte d'Or | Confirmed as the reference market for wax and bazin; tailors predominantly Senegalese; Mama Getzner owns the search query. |
| Italy | Missing from the plan. Bergamo (about 9,350 Senegalese), Brescia (about 6,716), Milan (about 6,434); clusters in Zingonia, Pontevico, Bovezzo. Kechic (Milan) and senegalmarket.it exist. Low competition. |
| Netherlands | Jansen Holland is a Getzner distributor selling EU-wide in euros. |
| UK | Empire Textiles and Majestic London online; Peckham retail is Nigerian and Ghanaian-led. Senegalese or Gambian-specific London shops not evidenced. |
| Dakar, Bamako, Kano, Lagos, Kaduna, Lomé, Abidjan, Cotonou | All evidenced as seller hubs (Marché HLM Dakar; ACI 2000 and Grand Marché Bamako; Kantin Kwari Kano; Balogun Lagos). |
| Lyon, Marseille, Spain, Belgium, Germany | Not researched. |

### 2.7 Seasonality, September 2026 to September 2027

| Date | Event | Demand effect | Confidence |
|---|---|---|---|
| 25 Dec 2026, 1 Jan 2027 | Christmas, New Year | Secondary peak (Christian buyers) | High |
| ~8 Feb to 8 Mar 2027 | Ramadan | Korité orders placed; few weddings | Medium |
| ~9–10 Mar 2027 | Korité / Eid al-Fitr / Small Sallah | First 2027 peak | Medium |
| ~mid-April 2027 | Practical tailor cutoff | Fabric buying peaks; custom orders close | Medium |
| 16 May 2027 (some calendars 17 May) | Tabaski / Eid al-Adha / Big Sallah | Year's main peak | High (±1 day) |
| ~22 Jul 2027 | Grand Magal de Touba | Mouride buyers, white bazin | Medium |
| 14–15 Aug 2027 | Gamou / Mawlid | Secondary peak, white and pastel bazin | High |
| Nov to May | Wedding season conventions | Unverified | Low |

Tailor mechanics (Senegalese press, May 2026): 50% deposit at order, 50% at delivery; 10 to 15 days for an existing model, 3 to 4 weeks for custom; ateliers working until 4 a.m. before Tabaski; clients complaining that tailoring now costs more than the fabric. "Delivers on time" is the trust signal buyers care about most and the hardest to extract from social posts.

### 2.8 Price bands (snippet-based; medium to low confidence)

| Item | Place | Observed price |
|---|---|---|
| Getzner, per metre | Bamako | 7,500 to 12,500 FCFA by line |
| Getzner, per metre | Dakar (HLM) | about 12,000 FCFA; Tabaski promos 3 m 9,000 F, 5 m 15,000 F |
| Getzner, per metre | Cotonou (classifieds) | 12,000 to 13,000 FCFA; 38,000 F per 3 m |
| Madame Getzner, per yard | Kano (2025) | ₦15,000 |
| Guinea brocade wholesale, per yard | Nigeria | ₦10,500 |
| Imitation "Getzner" | Alibaba, AliExpress | US$0.35 to US$10 per yard; 5 yards US$28 to US$45 |
| Ready thioub outfit | Senegal (TikTok seller) | 75,000 FCFA |
| Men's embroidered grand boubou | Dakar | 65,000 to 150,000 FCFA typical; premium fabric 80,000 to 280,000 plus embroidery 50,000 to 120,000 |
| Bridal complete outfit | Dakar | 180,000 to 650,000 FCFA |
| Full traditional outfit | Nigeria | ₦100,000 to 300,000 |
| Finished grand boubou | Etsy | £17 to £243; CA$145 to CA$954 |
| Paris and New York per-piece prices | — | Not obtained |

Design consequence: the price filter must carry currency, unit and what is included (fabric, embroidery, tailoring). A single "mentioned price" string cannot answer "under $300".

## 3. Thesis-level critique

### 3.1 Three products in one

Fabric buying is a commodity problem with a counterfeit twist: the buyer wants authentic Getzner at a fair price, nearby or shipped. Garment making is a services problem: the buyer wants a maker who can execute a style, on time, at a price, and who will not disappear with the deposit. Ready-to-wear is a product problem already served by Etsy, Afrikrea and Amazon. The plan's search examples mix all three. The evidence says the unmet need is the second one. Recommendation: makers and tailors are the wedge; fabric retail is a secondary facet whose value is the authenticity signal; ready-to-wear is an aggregation of feeds, not a build.

### 3.2 No named buyer

The plan never says who is searching. Candidate personas differ in language and intent:

- A diaspora woman in New York, Paris or Milan planning a wedding or Tabaski outfit without a trusted tailor. French and English, "grand boubou brodé", "taille basse", budget in euros or dollars, shipping via GP.
- A diaspora man needing a grand boubou or xaftaan for Tabaski or Gamou.
- A non-West-African guest invited to a Senegalese or Malian wedding, searching in English ("what to wear to a Senegalese wedding"). Under-served and easy to reach.
- A fabric buyer wanting authentic Getzner, in any market.
- A Nigerian buyer, who does not say "bazin" at all.

Pick one or two for v1. The Francophone diaspora corridor (Dakar and Bamako to Paris, New York, Milan) is coherent in language, garments, occasions and shipping. Nigeria is a separate taxonomy and a separate go-to-market; include it fully or defer it, but do not half-include it.

### 3.3 "Marketplace" promises what the product will not do

There is no transaction. The honest description is a discovery engine, or a directory with evidence. That is fine; say it. Separately, decide whether the transaction layer is ever in scope: deposit escrow for tailors would address the number-one trust failure (deposit paid, garment late or never delivered) and is where a real take rate lives, but it is a different business with fraud and dispute costs. Not for the MVP. Note that Yombal and AirTailor are already trying it.

### 3.4 AEO is sequenced backwards

Vendors pay for orders, not for representation in a layer nobody uses yet. Vendor monetization becomes sellable when either the engine itself sends measurable WhatsApp click-outs, or the engine demonstrably changes what Google, ChatGPT and Perplexity say. The second is unproven for a niche taxonomy (section 8). Sequence: demand first, then claims, then paid features. Also, "AEO" means nothing to a tailor in Dakar; the pitch is "more orders before Tabaski" and "be found by diaspora customers".

### 3.5 No demand plan

Supply cold start is solved by the data engine. Demand cold start is not addressed anywhere. Cheapest paths: programmatic SEO pages per city, garment and occasion (the "bazin riche boubou tailor new york" query has nobody on it); a concierge account on WhatsApp and Instagram that answers requests by hand from the dataset (validates the product and produces real query logs); diaspora associations and wedding planners; a brand partnership.

### 3.6 "Cultural fit" as a score is a liability

Scored by an LLM from bios and captions, "does this profile speak the Bazin language" degrades into inferring national origin. It is also easy to game with hashtags. Replace with "category relevance": count of distinct posts about bazin garments or fabric over time, with decay. Score evidence about the category, never identity.

### 3.7 Vendor accuracy is an image problem, not only a text problem

The plan's risk note about sellers reposting other people's work is right, and the plan's Content Understanding Agent only looks at captions and metadata. Duplicate detection needs perceptual hashes of thumbnails across accounts. Store the hash and derived tags, never the media.

## 4. Data model corrections

Keep the plan's five datasets as the conceptual layer. Correct the cardinality and add the tables below.

| Change | Why |
|---|---|
| Add `identities` (platform, handle, URL, business_id, match confidence, match evidence). A business has many handles. | The plan's Business table has one handle and one platform; real vendors have an Instagram, a TikTok, a Facebook page, a WhatsApp number, sometimes an Etsy shop and a Google Maps place. |
| Add `locations` (business_id, type: atelier / shop / pickup / ships_to, country, city, coordinates, evidence). | A Dakar atelier with a Paris pickup point and shipping to the US is three rows, not one field. |
| Split observations from facts. `observations` are immutable rows with `observed_at`, `source_url`, `acquisition_method`, `extractor_version`; business facts are derived with provenance pointers. | Reproducible rescoring, per-source takedown, audit trail for vendor disputes. |
| Structure prices: `currency`, `amount_min`, `amount_max`, `unit` (metre, pièce, yard, 5-yard, outfit, embroidery, shipping), `includes_fabric`, `includes_embroidery`, `includes_tailoring`, `is_promo`, `is_negotiable`, `observed_at`. | "Under $300" and "Tabaski promo" filters. Naira and CFA volatility. |
| Split `style_taxonomy` (concepts with per-language labels, synonyms, misspellings, parent concept) from `offers` (business × concept × evidence × price). | The plan's Product dataset mixes vocabulary with inventory. |
| `media_refs`: thumbnail URL, oEmbed URL, perceptual hash, visual tags, embedding. No bytes. | Repost detection, visual search, no rehosting. |
| `contact_channels`: type (whatsapp, phone, email, dm, website, wa.me catalogue), value, evidence, verified_at, do_not_contact, suppression_reason. | Consumer contact path and outreach compliance from one table. |
| `claims`, `takedown_requests`, `data_subject_requests`. | Claim flow and GDPR handling. |
| Provenance and licence class on every record: platform, acquisition method (SERP snippet, official API, feed, vendor-submitted, manual), terms category. | Purge an entire acquisition method if the legal posture changes. |
| `content_language` (fr, en, wo, ha, yo, bm) separate from vendor operating languages. | Query matching and outreach language. |
| `score_history`: component scores, weights version, computed_at, inputs snapshot. Never overwrite. | Explain rankings to vendors; detect drift. |
| `business_status`: active, dormant, closed, suspected_scam, duplicate_of. | Staleness is the biggest ongoing quality risk. |
| `search_terms` needs `source` (autocomplete, Trends, People Also Ask, TikTok suggestions, internal query log) and `observed_at`. Log every consumer query from day one. | Without internal query logs the vendor-facing search-term product is guesswork. |

Google Maps place data has caching limits (section 7); design Maps as a discovery and validation source, storing the place ID and your own observations, not Google's content.

## 5. Ranking rubric corrections

- Keep five dimensions; rename and redefine "Cultural fit" as "Category relevance" from evidence counts with time decay.
- Commercial clarity: reward any price anchor, but do not penalise "DM for price" heavily; negotiated pricing is the norm in this market.
- Maker credibility: add negative signals — perceptual-hash duplicates across accounts, stock imagery, watermark mismatch, and captions that only ever show other people's work.
- Trust: add recency decay, account age, engagement sanity, phone-number consistency across platforms, physical address, presence in a brand partner list.
- "Search match" is query-time relevance, not a business attribute. Final rank = f(query relevance, static quality score, freshness). Sponsored slots are a separate, labelled list.
- Deterministic and published: LLMs extract features; a versioned formula scores them. A vendor asking "why am I ranked below X" gets a factual answer.
- Calibration before launch: a gold set of about 200 businesses labelled by two or three culturally fluent raters (Senegalese and Malian diaspora), agreement measured, weights tuned against "would you recommend this maker to your sister".
- Bias check: diaspora vendors with websites and English captions must not systematically outrank Dakar ateliers that live on WhatsApp. Weight the evidence the informal economy produces: customer-tagged posts, fitting videos, repeated product posting, holiday collections.

## 6. Agents, reframed as a pipeline

Five autonomous agents will be hard to evaluate and expensive to rerun. Build a pipeline with LLM stages, each with an input schema, an output schema, an evaluator, a cost budget and idempotent reruns.

| Stage | Input | Output | Notes |
|---|---|---|---|
| 1. Discover | Taxonomy concept × geography × source | Candidate URLs with platform, handle, source type, relevance reason, relevance score | Query generation from the concept graph; hard relevance classifier to prune; dedupe by URL and by identity. Sources ordered per section 2.2. |
| 2. Resolve identity | Candidates | Business clusters with match confidence | Match on phone numbers, wa.me links, cross-links in bios, name similarity, shared thumbnails (perceptual hash). New stage; missing from the plan. |
| 3. Enrich | Business cluster, bio text, last N post texts, thumbnails | Business type, locations, contact channels, price signals, categories, per-field confidence, evidence pointers (URL + quoted text) | Extraction only from observed text and images. Never invent contacts. Validate phone numbers (libphonenumber) and wa.me links. Vision model on thumbnails for garment type, embroidery, colour. |
| 4. Classify content | Observation rows | Concepts, occasion, gender, fabric line, price (currency inferred from location and language), language, buyer intent, visual tags, perceptual hash | The plan's Content Understanding Agent plus vision, hashing and language ID. |
| 5. Score | Features | Component scores, total, reasons, caveats, weights version | Deterministic formula; the LLM writes reasons from features only. |
| 6. QA and evaluation | Random and risk-weighted samples | Per-field precision, drift alerts, human review queue | New stage. First 100 to 300 records reviewed by culturally fluent humans. |
| 7. Publish | Scored businesses | Search index, vendor pages, structured data | Programmatic pages per city × garment × occasion. |
| 8. Taxonomy and demand mining | Autocomplete, People Also Ask, Trends, TikTok suggestions, Reddit and Quora questions, internal query logs | Concept graph updates, query clusters, gap report per vendor | The plan's AEO agent, split into vocabulary building and demand mining. |

Compliance and lifecycle (claims, takedowns, opt-outs, refresh and expiry of stale records) is a workflow, not an agent, and needs to exist before outreach starts.

## 7. Legal and platform posture

Pending: this section is filled from the platform-access and legal research thread.

## 8. Monetization

### 8.1 Comparables (2025–2026, snippet-based)

| Company | Model | Vendor price | Terms and known problems | Confidence |
|---|---|---|---|---|
| WeddingWire / The Knot | Subscription storefront plus featured placement, sold by quote | About $125–150/month entry, past $1,000/month in competitive markets; featured placement $5,000–15,000/year | 12-month contracts; recurring vendor complaints about fake leads and undisclosed lock-in (2025) | Medium |
| Thumbtack | Pay per lead, credits, self-serve | $8 to $150+ per lead by trade | No contract; budget caps; lead-quality disputes common | Medium |
| Google Local Services Ads | Pay per lead with Google Guarantee badge | Average about $53 per lead (Feb 2026 benchmark, 888 contractors) | Works where average tickets are large (about $1,800 in that benchmark) | Medium-high |
| Yelp for Business | CPC ads plus upgrade packages | From $5/day; typical SMB $150–1,000+/month; upgrade package from $270/month | Cancel anytime | Medium-high |
| Fresha | Subscription plus commission on new clients | $19.95/month; 20% commission on each new client once; 2.19–3.30% processing | Commission does not apply to repeat or direct bookings | Medium |
| Etsy | Listing, transaction and payment fees | $0.20 listing; 6.5% transaction; 3% + $0.25 processing; Offsite Ads 12–15% | Effective take 11–22% | High |
| Afrikrea / ANKA | SaaS subscription plus tiered commission | €10/month; 5–8% commission under 20 sales or €2,000/month, 10–15% above; lower if the seller brings own traffic | Official help centre, undated; 2026 re-confirmation not found | Medium-high |
| LoveWeddingsNG | Featured vendor tier, sponsored posts, banners | Quote only | — | Low on price |
| BellaNaija Weddings | Sponsored posts and banners | One stale rate card (about 2017) at ₦105,000 per post | — | Low |
| GEO/AEO agencies (reference only) | Monthly retainer | SMB tier $1,500–5,000/month; DIY tools $10–1,000/month | Intent far exceeds execution: only low single digits of businesses have a resourced programme (Conductor 2026) | Medium |

Willingness-to-pay signals: Nigerian SMBs report spending ₦30,000 to 250,000 per month (about $19 to $160) on Instagram and Facebook boosting (2026, single agency source, medium confidence). A Senegalese agency claims WhatsApp Catalog replaces a website for 70% of SMBs (single claim, low confidence). The most relevant GSMA MSME e-commerce survey covering Nigeria and Senegal dates from October 2023, not 2025–2026. Wave held more than half of Senegal's mobile-money share in 2023; any paid tier for Dakar or Bamako vendors must bill through Wave or Orange Money, which is a build cost, not a pricing detail.

### 8.2 What feeds AI answer engines today

- Google AI Mode and AI Overviews draw local recommendations from Google Business Profile, schema.org structured data and third-party reviews.
- ChatGPT shopping recommendations are increasingly feed-driven: one tracking study (Profound) reports feed-integrated picks rising from about 8% to about 65% of tracked recommendations by early September 2026.
- Perplexity leans on directories, press and Wikipedia.
- Consumer use of AI for local discovery is reported to have jumped from 6% to 45% in a year (BrightLocal 2026; report not directly accessible, medium confidence).
- Implication for the AEO thesis: a niche directory can influence AI answers only by being the structured, authoritative source those systems already read: consistent Business Profile data, schema.org on every vendor page, a merchant-style feed, and press or Wikipedia-grade citations. Selling "AI visibility" as a product to a Dakar tailor is not credible; bundling schema and profile hygiene into the paid tier is.

### 8.3 Brand-side B2B angle

- Vlisco Group (Vlisco, Woodin, Uniwax, GTP; owned by Actis) has spent for decades on anti-counterfeiting: a QR and holospot verification tool, customs training, seizures, after a documented revenue decline attributed to Chinese copies. This proves the problem is worth money to a brand.
- Getzner has no comparable public programme (section 2.4), which is the opening. No precedent was found of any brand licensing dealer-verification data from a third-party discovery platform, so treat the brand contract as a hypothesis to test in one conversation, not a revenue line.

### 8.4 A realistic model at 1,000 to 5,000 vendors

Illustrative, every figure an assumption:

- 3,000 claimed vendors by year two, roughly 40% in diaspora hubs and 60% in West Africa.
- Free claim tier for density; 8 to 12% upgrade to a paid verified badge and structured catalogue. This conversion rate is the single most load-bearing and least verified assumption in the model.
- Prices by market: $25 to $40 per month in diaspora hubs (below WeddingWire, near a Yelp-lite tier, because these are one-to-few-person ateliers); $5 to $10 per month in Dakar, Bamako and Lagos, which is a fraction of the boosting spend already reported.
- Result: core subscription revenue around $60,000 to $65,000 per year at year two; a small capped lead-fee layer adds perhaps $18,000; sponsored placement is immaterial until organic search volume exists (year three or later).
- One brand data or verified-dealer contract at $15,000 to $40,000 per year would rival the entire subscription base.

Read plainly: at this vendor count it is a real but small business unless paid conversion, brand contracts, or vendor count grow well beyond the stated range. The expansion into Ankara, Aso Oke, Kente and other categories is where scale comes from, which is why the beachhead must prove the mechanics rather than the revenue.

### 8.5 Strongest and weakest paths

- Strongest: a low-priced verified badge and structured-catalogue subscription, tiered by market, with schema and profile hygiene bundled in. Direct precedent in Fresha and Afrikrea; substitutes existing boosting spend; maps onto the one pain every comparable shows, which is trust.
- Weakest: pay-per-lead or commission as the primary model in West African markets. Lead-quality disputes are the dominant failure mode of that structure even in the US; cash and mobile-money handoffs make attribution unreliable; a lead price high enough to sustain the platform is unaffordable for everyday orders, and one affordable for a Dakar tailor does not cover servicing.
- Speculative: selling AEO directly to vendors. The defensible versions are the bundled hygiene feature above and, separately, licensing the aggregate taxonomy and verified-dealer data to brands or marketplaces.

## 9. Revised MVP plan with gates

Anchor: Korité about 9–10 March 2027; Tabaski 16–17 May 2027; custom orders close around mid-April 2027.

| Phase | Window | Work | Gate to pass |
|---|---|---|---|
| 0. Foundations | Now to early Oct 2026 | Choose the corridor (recommended: Dakar and Bamako to Paris, New York, Milan; Francophone vocabulary). Taxonomy v0 with native-speaker review. Legal posture memo and source allowlist. Gold-set design. Schema from section 4. | Corridor and persona decided; taxonomy v0 signed off by two native speakers; source allowlist agreed. |
| 1. Data engine | Oct to Nov 2026 | Stages 1 to 6 on the safest sources. 300 candidates to 100 curated makers and shops with evidence. Human audit of 50. | 100 records meeting the "best 100" definition below with at most 5% errors in the audit. |
| 2. Demand and vendor validation | Nov to Dec 2026 | Concierge test on WhatsApp and Instagram answering real requests by hand from the dataset. Claim outreach to 30 of the 100 (this doubles as the GDPR Article 14 notice). 20 buyer interviews. | At least 20 real requests handled; vendor response rate measured; claim rate at least 10%; buyers say they would use it again. |
| 3. Public pages | Jan to Feb 2027 | Programmatic pages per city × garment × occasion with structured data, evidence, link-outs and WhatsApp click; a search box. Query logging. | Pages indexed by mid-February; organic impressions and click-outs measured through Korité. |
| 4. Tabaski run | Mar to May 2027 | "Accepting Tabaski orders until [date]" status field vendors update themselves; refresh cadence weekly; Italy and New York outreach. | Click-outs per vendor; vendor-reported orders; retention of claimed profiles. |
| 5. Monetization experiments | Jun 2027 onward | Verified badge, featured placement (labelled), lead analytics, brand partnership pilot. | Paying vendors and a brand conversation, or a documented reason it did not work. |

"Best 100" definition: at least one verified contact channel; at least three distinct evidence items of bazin garments or fabric in the last twelve months; city-level location; business type at 0.8 confidence or better; no duplicate or fraud flag.

Scope discipline: no Ankara, Kente, Aso Oke or Gele until the Tabaski run has produced click-outs. The expansion story is right; its timing is after proof.

## 10. Under-weighted opportunities

1. Getzner partnership: the dealer layer they do not have, plus a counterfeit problem they have not solved with technology. Business Unit Africa is the door.
2. English-language wedding-guest demand ("what to wear to a Senegalese wedding"): low competition, easy pages, feeds the same vendors.
3. Italy: three Lombardy cities with dense Senegalese communities and almost no discovery products.
4. Tailor SaaS tools (Tailora, CoutureSo, CouturArt, Digitailleur) as supply partners: their customers are exactly the makers, already structured.
5. A time-bound "accepting orders until" field before each holiday: simple, valuable, and vendors will maintain it themselves.
6. Paid concierge matching for bridal and grand-boubou orders: high ticket, and the concierge test already builds the muscle.
7. The taxonomy and concept graph as a licensable asset to marketplaces and AI shopping assistants, once query logs prove it.
8. Deposit escrow, later, if the trust data shows where deposits go wrong.

## 11. Open questions that change the build

1. Who is the first customer of v1: diaspora buyers, or the vendors as a sales lead list? The answer changes source priority, the fields collected and the compliance work.
2. Corridor: Francophone diaspora only (Dakar and Bamako to Paris, New York, Milan), or Nigeria in v1 with its own vocabulary and garments?
3. Source posture: strictly terms-compliant sources only, or accept grey-area third-party scrapers for Instagram and TikTok with mitigation?
4. Who does cultural review? Are there Senegalese or Malian reviewers available, and what is the founder's own connection to the category?
5. Budget and deadline: monthly budget for search APIs, LLM calls and human review, and whether Tabaski 2027 is the target.
6. Stack: code in this repo (Postgres plus a small search index) or an agent platform, and where the datasets should live.
7. Existing assets: any seed vendor lists, relationships with Getzner partners, diaspora associations or wedding planners.

## 12. Still unverified (needs a logged-in browser or a lawyer)

- Afrikrea's 2026 commission rate and Rich Bazin category size.
- Instagram and TikTok hashtag totals; Facebook group member counts; Senegal Snapchat reach.
- BellaNaija and LoveWeddingsNG vendor fees.
- Getzner's official line roster and whether the hologram label is Getzner's or a distributor's.
- Paris and New York per-piece Getzner prices; imitation price differential in-market.
- Korité 2027 and Magal 2027 on an official calendar; wedding-season conventions.
- Shop-level presence in US cities beyond New York; Lyon, Marseille, Spain, Belgium, Germany.
- Google Trends and keyword volumes for the core terms (no published figures surfaced).
