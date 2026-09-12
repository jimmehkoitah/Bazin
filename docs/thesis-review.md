# Bazin discovery engine — thesis and plan review

Date: 2026-09-12. Status: review of the founding thesis, data model, ranking rubric, agent list and MVP plan, with due diligence on the claims the plan depends on. Decisions taken in response are in `decisions.md`; the build that implements them is in `v1-build-spec.md`. Where this review and the decision log disagree (source posture, outreach), the decision log wins.

## 0. How this review was produced, and its limits

- Four research threads ran in parallel: platform access and legal exposure; competitors and supply sources; category terminology, prices, geography and seasonality; monetization comparables.
- Direct fetches of primary pages (Getzner, Etsy, Meta, Wikipedia, Senegalese press, etc.) were blocked by this environment's egress policy. Findings therefore rest on search-engine snippets of those pages, captured on 2026-09-12. Anything that a snippet did not settle is marked unverified. Numbers from snippets are capped at medium confidence.
- Login-gated figures (Instagram hashtag totals, Facebook group member counts, Afrikrea's 2026 commission rate) could not be read. Section 12 lists what still needs a logged-in browser session.
- Nothing here is legal advice. The legal section identifies exposure and a defensible posture; a lawyer should sign off before vendor outreach at scale.

## 1. Verdict in brief

The wedge is real but narrower than written, and the plan's assumed engine (automated collection from Instagram and TikTok, with vendor contacts warehoused for outreach) is the part that does not survive 2025–2026 platform terms and regulator guidance. The compliant version of the plan is a claim-first directory seeded by hand and by open and first-party data.

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
11. **Automated collection from Instagram, TikTok, Facebook and Pinterest is off-terms, and the case law the plan implicitly relies on no longer covers it.** Meta's terms have banned automated collection logged in or out since 1 January 2025; TikTok's July 2026 terms ban extraction outright; SerpApi is defending suits from Google and Reddit; Google Places may not be used to build a directory. Human curation, seller-claimed profiles, open geo data, first-party sites and official APIs used as rendering layers are the compliant engine (section 7).
12. **"Real sales engagement" to vendors is a per-country state machine, not a campaign.** Cold WhatsApp and cold Instagram DMs are policy violations everywhere; cold email is straightforward in the US, limited to registered companies at functional addresses in the UK and France, and not available in Italy; the GDPR Article 14 notice must be the first message. CNIL's KASPR decision (scraped professional contacts, database sold for prospecting, €240,000 and an order to delete everything) is the closest analogue to the plan's outreach model.

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
| Facebook seller pages | Vente Bazin Getzner (La Courneuve, wa.me link), Bazin Getzner Niamey, Bass Getzner and Maison du Getzner (Dakar), Mama Getzner (Paris) | No automated collection (Meta terms). Human curation and seller claims. |
| WhatsApp catalogues | The standard order channel. Mama Getzner runs live sales on WhatsApp; Benin and Kaffrine sellers publish "appel et WhatsApp" numbers | No crawl. Contact channel only. |
| TikTok | Tag pages and dozens of auto-generated discover pages ("vente bazin riche dakar", "boutique de bazin paris", "best african tailor in nyc", "couturier nigérian à Paris"). A "Vendeur De Bazin" discover tag showed 434.9K posts (may be stale). | Public pages exist; automated extraction is barred by TikTok's July 2026 terms. Human curation and seller claims; link out. |
| Instagram | Vendor posts in Dakar, Abidjan, Bamako, Lagos; hashtag counts no longer public | Login-walled; automated collection barred since January 2025. oEmbed for display; human curation; sellers connecting their own accounts. |
| Snapchat (Senegal) | "Senegal Clothing" topic with millions of clips (May 2026); Dakar boutiques put "SNAP: handle" in Instagram captions as the order channel; French press describes Snapchat as a parallel market | No |
| YouTube | DT Couture, Broderie Machine, seasonal compilations ("100+ nouveaux styles bazin riche 2026", "Tabaski 2025: la folie des tissus envahit Dakar") | Yes, official Data API (30-day storage cap) |
| Pinterest | Boards with 900+ Getzner pins, 900+ bazin pins, 720 boubou styles, 180 Senegalese tailor pins; ideas hubs | Review-gated Standard API; scraping barred |
| Etsy | 574 "bazin riche" items; 1,000+ "getzner bazin"; grand boubous from £17 to £243, CA$145 to CA$954; titles keyword-stuff "Getzner" | Yes, Open API (Commercial Access review; 6-hour freshness cap; verbatim disclaimer) |
| Afrikrea / ANKA | Dedicated Rich Bazin category; raw fabric, boubous, couple sets, kids' sets; seller country tagged | Feed or partnership |
| Classifieds | CoinAfrique (SN, CI, BJ, ML, BF), Expat-Dakar, Jiji (NG, SN): price and city per ad, tailor and atelier ads | Probably, but their terms on automated access were not checked |
| Retailer web shops | Mama Getzner, Empire Textiles, Jansen Holland, dimancheabamako.com, monbazin.com | Yes (first-party feeds; respect robots.txt) |
| Twitter/X, Reddit | Minimal commercial signal; a few Kano per-yard price tweets | Deprioritize |

Reorder the plan's discovery sources accordingly: seller claims and referrals, open geo data (Overture, OpenStreetMap), retailer feeds and first-party sites, Etsy and Afrikrea, YouTube, classifieds (terms to check) first; Instagram, TikTok, Facebook and Pinterest by human curation and official embeds only; Facebook groups and WhatsApp via vendor self-onboarding. Google Places only to resolve and dedupe. Section 7 gives the reasons.

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
| No Wolof garment vocabulary | Garment terms that appear in captions: taille basse (very heavy), thioup / thioub / cuub (hand-dyed bazin; "modèle thioub Tabaski 2025"), grand boubou 3 pièces, ndoket / ndokette, xaftaan / kaftan, mbubb (rare in captions; French "boubou" dominates). Do not add "mbaxal", which some word lists include: it is a rice dish. | High |
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
| Rights fields on every business record: `source_url`, `collected_at`, `notice_sent_at`, `legal_entity_type` (registered company or sole trader), `country`, `objection_at`. Objection hard-deletes and propagates to derived indexes. | GDPR Article 14, PECR, CNIL and NDPA rules all turn on these fields (section 7). |
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
| 1. Discover | Taxonomy concept × geography × source | Candidate URLs with platform, handle, source type, relevance reason, relevance score | Sources per section 7.4: seller signups and referrals, open geo data, first-party sites and feeds, official APIs, official search APIs for URL discovery, and human curation for Instagram, TikTok and Facebook. Query generation from the concept graph; hard relevance classifier to prune; dedupe by URL and by identity. |
| 2. Resolve identity | Candidates | Business clusters with match confidence | Match on phone numbers, wa.me links, cross-links in bios, name similarity, shared thumbnails (perceptual hash). New stage; missing from the plan. |
| 3. Enrich | Business cluster, bio text, last N post texts, thumbnails | Business type, locations, contact channels, price signals, categories, per-field confidence, evidence pointers (URL + quoted text) | Extraction only from observed text and images. Never invent contacts. Validate phone numbers (libphonenumber) and wa.me links. Vision model on thumbnails for garment type, embroidery, colour. |
| 4. Classify content | Observation rows | Concepts, occasion, gender, fabric line, price (currency inferred from location and language), language, buyer intent, visual tags, perceptual hash | The plan's Content Understanding Agent plus vision, hashing and language ID. |
| 5. Score | Features | Component scores, total, reasons, caveats, weights version | Deterministic formula; the LLM writes reasons from features only. |
| 6. QA and evaluation | Random and risk-weighted samples | Per-field precision, drift alerts, human review queue | New stage. First 100 to 300 records reviewed by culturally fluent humans. |
| 7. Publish | Scored businesses | Search index, vendor pages, structured data | Programmatic pages per city × garment × occasion. |
| 8. Taxonomy and demand mining | Autocomplete, People Also Ask, Trends, TikTok suggestions, Reddit and Quora questions, internal query logs | Concept graph updates, query clusters, gap report per vendor | The plan's AEO agent, split into vocabulary building and demand mining. |

Compliance and lifecycle (claims, takedowns, opt-outs, refresh and expiry of stale records) is a workflow, not an agent, and needs to exist before outreach starts.

## 7. Legal and platform posture

Not legal advice. Findings are from search snippets of primary and secondary sources; dates are as visible in the snippet; items a snippet did not settle are marked unverified. A lawyer should review before outreach at scale. The direction, however, is not ambiguous: the plan's assumed engine (automated collection from Instagram and TikTok, contacts warehoused for outreach) is the part of the plan that does not survive contact with 2025–2026 terms, case law and regulator guidance.

### 7.1 Platform terms and case law

| Topic | Finding | Posture | Source and date |
|---|---|---|---|
| Meta (Instagram, Facebook) terms | Rewritten after Meta lost to Bright Data: automated access or collection without permission is prohibited "regardless of whether... undertaken while logged-in." In force since 1 Jan 2025. | No-go for automated collection | socialmediatoday.com, Nov 2024 |
| Meta v. Bright Data | Jan 2024 summary judgment for Bright Data turned on the old terms ("Meta left the gate open"); Meta dropped the case Feb 2024. Superseded prospectively by the wording above. | Spent | Eric Goldman blog, Proskauer, Jan 2024 |
| Instagram logged-out surface | Profiles render but cut off after roughly 6–12 posts; hashtag and location pages show a top 9; Stories and Reels behind the wall. | Enough to confirm a shop exists, not to build a catalogue | scrapfly.io and others, 2026 (month unverified) |
| Instagram official API | Reads only accounts that authorised your app; no public discovery endpoint per vendor sources; whether Business Discovery still returns other public business accounts by username is the single most important open question. Advanced access needs app review and business verification. | Safe only for sellers who connect their own account | hikerapi.com, storrito.com, 2026 (unverified) |
| Meta oEmbed | Since 15 Jun 2026 callable with an app token or tokenless, no app review; public posts, carousels and Reels; docs say it is for embedding only, "not to be used for any other purpose." | Safe for display; no-go as an extraction pipeline | developers.facebook.com, Jun 2026 |
| TikTok terms | US terms updated 15 Jul 2026 prohibit scraping, crawling or extracting any data by automated means without written approval. Research API and Commercial Content API are for vetted researchers and qualified organisations, not commercial products. | No-go for automated collection | developers.tiktok.com; commentary 2026 |
| Pinterest | Scraping prohibited; Standard API tier is review-gated; 18 Aug 2026 revision adds AI-training prohibitions; further update 12 Nov 2026. | No-go for scraping; grey via reviewed API | policy.pinterest.com, Aug 2026 |
| YouTube Data API | Non-authorised data storable no longer than 30 days; statistics likewise. | Safe as a refresh layer, not a store | developers.google.com, Jun 2026 |
| X / Twitter | Pay-per-use since Feb 2026: $0.005 per post read; legacy tiers closed. | Lawful, economically marginal, weak channel anyway | 2026 secondary sources |
| Reddit | Free tier non-commercial only; commercial use requires a paid agreement. Reddit sued Perplexity, SerpApi, Oxylabs and AWMProxy on 22 Oct 2025 over scraping via Google results; DMCA circumvention claims survived a motion to dismiss. | No-go on the free tier; the SERP intermediary layer is under attack | searchengineland.com, Bloomberg Law |
| Google Places API | Only the place ID may be stored indefinitely; coordinates for 30 days; names, addresses, phones, ratings, reviews and photos may not be cached. Terms bar use "in a listings or directory service." Places API (New) does not relax this. | Resolver only; no-go as the directory's datastore | developers.google.com policies; secondary sources 2026 (exact clause text unverified) |
| SerpApi | Sued by Google on 19 Dec 2025 (DMCA circumvention of SearchGuard) and by Reddit; no indemnity. | No-go as a dependency | blog.google, Dec 2025 |
| Bright Data SERP | Markets certifications and its 2024 wins; states compliance with terms and data-protection law "remains the user's responsibility." | Grey; risk contractually pushed to you | brightdata.com, 2026 |
| Apify-style scrapers | Still operating at scale (Instagram scraper about 350K users); their legal posture cites Bright Data and hiQ and explicitly excludes GDPR, UK and non-US regimes. | Grey to no-go for an EU/UK/West Africa footprint | apify.com, 2026 |
| Etsy Open API | Listing content displayed no more than 6 hours stale, other content 24 hours; no caching beyond what serving users requires; mandatory verbatim trademark disclaimer; Commercial Access requires manual review. | Safe as a live view, not a warehouse | etsy.com developer terms (effective date unverified) |
| Copyright | Perfect 10 v. Amazon (9th Cir. 2007): thumbnails plus link-back in a search index are transformative fair use. Thomson Reuters v. Ross (D. Del. Feb 2025): not fair use where the product substitutes for the source. | Safe for thumbnails and short snippets that drive traffic to the source; design against substitution | Wikipedia, EFF; OSU copyright office Mar 2026 |
| hiQ v. LinkedIn | CFAA does not reach public websites (9th Cir. Apr 2022), but the case ended in a $500,000 consent judgment on contract and tort claims with an order to delete all scraped data. | Scraping public pages is not a federal crime; it is still actionable | Justia; Proskauer, Dec 2022 |
| Open geo data | Overture Maps Places (CDLA-Permissive 2.0) and OpenStreetMap (ODbL) are storable, redistributable and commercially usable with attribution; ODbL share-alike on derived databases needs analysis. | Safe; the only place spine you may own | docs.overturemaps.org; osmfoundation.org |

### 7.2 Personal data

| Topic | Finding | Consequence |
|---|---|---|
| GDPR Article 14 | Notice within one month of collection and at the latest at first communication. The disproportionate-effort exemption is read restrictively and cannot survive first contact: having their address proves notice was feasible. | The privacy notice goes in the first message, every time. |
| EDPB web-scraping guidelines 03/2026 (7 Jul 2026, consultation to 30 Oct 2026) | Legitimate interest with a rigorous three-part test; pre-collection filters, minimisation, public notice, pre-collection opt-out; robots.txt, CAPTCHAs and login walls treated as indicators of data subjects' expectations. Scope is generative AI; transfer to a directory is by analogy. | Honour robots.txt and login walls; keep a documented legitimate-interest assessment per source. |
| CNIL v. KASPR (5 Dec 2024) | €240,000 fine (one EDPB page says €200,000) for scraping professional contacts into a database sold for prospecting; CNIL ordered deletion of the entire database. Case closed 4 Mar 2026 after compliance. | This is the closest analogue to "scrape vendor contacts, monetise outreach." It is the downside case. |
| CNIL guidance on scraping for marketing (2020) and B2B prospecting | Scraped contact data needs consent before marketing use; B2B email is opt-out only to functional professional addresses; auto-entrepreneurs and individual enterprises are treated as natural persons and need opt-in; ten prospecting penalty decisions in 2025. | France: no cold email to sole-trader tailors; functional company addresses only. |
| UK PECR | Corporate bodies may be emailed without consent; sole traders and most partnerships are individual subscribers and need consent or soft opt-in. Opt-out and sender identification in every email. | UK: registered companies only. |
| Italy | Consent required for promotional email; the Garante treats double opt-in as the minimum; tracking pixels need prior consent by 28 Oct 2026. | Italy: no cold email at all. |
| Nigeria NDPA 2023 | Extraterritorial; processing more than 200 data subjects in six months, or operating in e-commerce, makes you a "data controller of major importance" with registration and a DPO; absolute right to object to direct marketing. | Registration is likely required as soon as Nigerian sellers are listed. |
| Senegal Loi 2008-12 | Prior declaration of processing to the CDP (Art. 18); enforcement against foreign entities described as weak. | A cheap one-off filing; do it. Mali, Gambia and Benin regimes not researched. |
| US CAN-SPAM | No consent required, business or consumer; accurate headers, ad identification, postal address, opt-out honoured within 10 business days; penalties up to $53,088 per email. | The US is the one jurisdiction where cold B2B email is straightforward. |
| CCPA | The B2B contact exemption expired 1 Jan 2023. | California sellers get notice, access, deletion and opt-out rights. |
| Sole traders | No exemption; a sole trader's business contact details are personal data. | Treat every tailor and shop record as personal data unless demonstrably a registered company. |

### 7.3 Outreach channels

| Channel | Rule | Posture |
|---|---|---|
| WhatsApp Business Platform | Opt-in required before any message; a published WhatsApp number is not opt-in; unsolicited bulk messaging and "contacting people without clear opt-in" are named causes of restriction; numbers carry a quality rating and templates are paused then disabled on spam reports; business verification required from Jan 2026. | Cold WhatsApp: never. Consumers clicking a wa.me link to contact a seller is fine (user-initiated). |
| Instagram DM | Meta opens a 24-hour window only after a user-initiated message, Story reply or comment; cold outbound DM is prohibited and not available via the official API. | Only after the seller engages first. |
| Email | See 7.2 by country. | US: yes. UK and France: registered companies at functional addresses. Italy: no. Nigeria and Senegal: allowed with absolute objection right and filings. |

### 7.4 What this means for the architecture

1. **Invert the supply model.** Seller-submitted and seller-claimed data is the only tier-one source. Build the claim and signup flow first, seed it from open and first-party data, and treat platform content as a rendering layer over records the seller owns. It is also the only path that ever legitimises WhatsApp or Instagram messaging.
2. **Tier two: open geo data.** Overture Places and OpenStreetMap for physical shops in Dakar, Bamako, Banjul, Lagos, Cotonou, Harlem, Château Rouge and Lombardy. Check ODbL share-alike before publishing a derived database.
3. **Tier three: sellers' own websites and feeds**, respecting robots.txt: Shopify stores, schema.org markup, sitemaps, contact pages. First-party provenance, no platform terms in the way.
4. **Tier four: official APIs as rendering layers, never stores.** Etsy Commercial Access, Meta oEmbed, Pinterest Standard, YouTube Data API. Store the ID, fetch the content, cache with a TTL that respects each platform's cap.
5. **Google Places is a resolver, not a source.** Persist the place ID; use it to disambiguate and dedupe; never render Places-derived names or phones on a directory page.
6. **Replace SerpApi-style dependencies with official search APIs for URL discovery**: Google Programmable Search JSON API (official, paid per query, supports site-restricted queries) and Brave Search API (independent index, commercial terms) are candidates; both need a terms check on retention before use, but either is a categorically safer dependency than a vendor under two active suits. Store the URL and a short snippet, then fetch first-party.
7. **Human curation is compliant where automation is not.** A culturally fluent researcher browsing Instagram or TikTok and recording facts about a business is not "automated means" under any of the terms above; GDPR still applies to the record. The "best 100" the plan wants should be built by hand, which is also what quality required. Automation arrives through claimed profiles and first-party sources.
8. **Link out, do not copy in.** Store thumbnail URLs and hotlink or embed; keep captions to short excerpts; make the link-back the prominent action. Perfect 10 protects that shape; Thomson Reuters v. Ross is the risk if a page replaces the visit to the seller's post.
9. **Build the rights machinery into the schema.** Per-source legitimate-interest assessment; public privacy notice; on every record: `source_url`, `collected_at`, `notice_sent_at`, `legal_entity_type`, `country`; a one-click objection that hard-deletes and propagates; a pre-collection opt-out list checked at ingest.
10. **Outreach is a per-country state machine, and the Article 14 notice is the first message.** Send a strictly informational notice (what is listed, why, rights, how to correct, claim or remove), with no paid upsell, so it is a legal notice rather than prospecting. Marketing to a vendor begins only after they claim, which creates the relationship and the consent. Ranked by risk: US email; UK and France to registered companies at functional addresses; Nigeria and Senegal with filings; Italy not at all; Instagram DM only after the seller engages; WhatsApp cold never. Have a lawyer confirm the notice-versus-prospecting line for France before sending.

### 7.5 Legal items still unverified

- Whether Instagram's Business Discovery endpoint still returns other public business accounts by username in 2026 (highest-value open question).
- Exact current wording of Google's "listings or directory service" prohibition and the Etsy developer terms' effective date.
- Whether EDPB Guidelines 03/2026 formally reach directories, or only generative-AI training.
- Mali, Gambia and Benin data-protection regimes; Nigeria's 2025 implementing directive.
- Retention terms for Google Programmable Search and Brave Search API results; Serper.dev's posture (nothing found).
- Terms of service of CoinAfrique, Expat-Dakar and Jiji on automated access (not researched).
- ODbL share-alike consequences for a directory built partly on OpenStreetMap data.

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
| 0. Foundations | Now to early Oct 2026 | Choose the corridor (recommended: Dakar and Bamako to Paris, New York, Milan; Francophone vocabulary). Taxonomy v0 with native-speaker review. Legal posture memo and source allowlist; public privacy notice; per-source legitimate-interest assessment; CDP declaration for Senegal and NDPA registration check for Nigeria. Gold-set design. Schema from section 4. | Corridor and persona decided; taxonomy v0 signed off by two native speakers; source allowlist and privacy notice agreed. |
| 1. Data engine | Oct to Nov 2026 | Stages 1 to 6 on the sources in section 7.4. The first 100 are built by hand by culturally fluent researchers from open geo data, first-party sites, official APIs and manual review of social profiles, with the pipeline structuring and scoring what they record. 300 candidates to 100 curated makers and shops with evidence. Human audit of 50. | 100 records meeting the "best 100" definition below with at most 5% errors in the audit. |
| 2. Demand and vendor validation | Nov to Dec 2026 | Concierge test on WhatsApp and Instagram answering real requests by hand from the dataset (buyers contact the account; the account never cold-messages sellers). Article 14 notice plus claim invitation to 30 of the 100, sent per the country rules in section 7.3: US and registered companies first, no cold email in Italy, no cold WhatsApp or DMs anywhere. 20 buyer interviews. | At least 20 real requests handled; vendor response rate measured; claim rate at least 10%; buyers say they would use it again. |
| 3. Public pages | Jan to Feb 2027 | Programmatic pages per city × garment × occasion with structured data, evidence, link-outs and WhatsApp click; a search box. Query logging. | Pages indexed by mid-February; organic impressions and click-outs measured through Korité. |
| 4. Tabaski run | Mar to May 2027 | "Accepting Tabaski orders until [date]" status field vendors update themselves; refresh cadence weekly; New York outreach by email; Italy through claimed profiles, diaspora associations and local partners rather than cold email. | Click-outs per vendor; vendor-reported orders; retention of claimed profiles. |
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
3. Source posture: build the first 100 by hand and grow through claimed profiles, open data and first-party sources (the compliant path in section 7), or accept off-terms scraping risk for Instagram and TikTok? Section 7 argues for the first; the decision is yours.
4. Who does cultural review? Are there Senegalese or Malian reviewers available, and what is the founder's own connection to the category?
5. Budget and deadline: monthly budget for search APIs, LLM calls and human review, and whether Tabaski 2027 is the target.
6. Stack: code in this repo (Postgres plus a small search index) or an agent platform, and where the datasets should live.
7. Existing assets: any seed vendor lists, relationships with Getzner partners, diaspora associations or wedding planners.
8. Sales engagement: which vendors you intend to contact, through which channel, in which countries. Section 7.3 rules out cold WhatsApp and Instagram DMs everywhere, and cold email in Italy and to sole traders in the UK and France; the rest needs the Article 14 notice as the first message.

## 12. Still unverified (needs a logged-in browser or a lawyer)

- Afrikrea's 2026 commission rate and Rich Bazin category size.
- Instagram and TikTok hashtag totals; Facebook group member counts; Senegal Snapchat reach.
- BellaNaija and LoveWeddingsNG vendor fees.
- Getzner's official line roster and whether the hologram label is Getzner's or a distributor's.
- Paris and New York per-piece Getzner prices; imitation price differential in-market.
- Korité 2027 and Magal 2027 on an official calendar; wedding-season conventions.
- Shop-level presence in US cities beyond New York; Lyon, Marseille, Spain, Belgium, Germany.
- Google Trends and keyword volumes for the core terms (no published figures surfaced).
- The legal items in section 7.5, above all whether Instagram's Business Discovery endpoint still returns other public business accounts.
