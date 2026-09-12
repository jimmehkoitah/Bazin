# Research digest: vocabulary, platforms, places

Compiled 2026-09-12 from four research threads (terminology and demand; competitors and supply sources; platform terms and legal; monetization). Method: web search across English and French, with primary-page fetches blocked by the sandbox's egress policy, so findings rest on search-result excerpts of the cited pages. Confidence: H = seen in seller captions or primary pages, M = secondary source or single snippet, L = inferred. Login-gated numbers (Instagram hashtag totals, Facebook group sizes) could not be read.

## 1. The language split, and why it matters

| Market | Commerce language | Fabric name | Garment names | Price unit and currency |
|---|---|---|---|---|
| Senegal | French, Wolof | bazin, bazin riche, Getzner (used as a generic noun), thioup/thioub/cuub for dyed bazin | grand boubou (3 pièces), taille basse, ndoket, xaftaan/kaftan, mbubb (rare in captions) | per mètre, per pièce; FCFA (XOF), written "150 000 F", "150.000 FCFA", "150k" |
| Mali | French, Bambara | bazin, bazin malien, bazin du Mali, Getzner teinté, teinture artisanale, gala (the dye) | grand boubou, boubou brodé | per mètre; FCFA |
| Côte d'Ivoire, Benin, Togo, Burkina, Niger | French | bazin riche, Getzner, gandoura (Niger, Cameroon, for the garment) | grand boubou, boubou | per mètre, per 3 m / 4 m / 5 m cuts; FCFA |
| Guinea | French | bazin, Getzner | boubou | GNF |
| Mauritania | French, Hassaniya | bazin damassé | drâa (boubou mauritanien) | MRU |
| Nigeria | English, Hausa, Yoruba | shadda / shedda, guinea brocade, "supreme bazin shadda"; "bazin" only secondary; Getzner line names used directly (Madame Getzner, Phantom, Super Magnum) | babban riga (Hausa north), agbada with buba and sokoto (Yoruba south-west), senator, kaftan, jalabiya | per yard (5-yard, 10-yard); naira (₦) |
| Gambia | English, Wolof | bazin, brocade | boubou; holiday "Tobaski" | per yard; GMD |
| France, Belgium | French | bazin, Getzner, brocart (misspelled "brocard" in captions) | grand boubou, boubou brodé | per mètre; EUR |
| Italy (Lombardy) | Italian, French | bazin, tessuti africani | boubou | EUR |
| UK | English (Nigerian and Ghanaian-led retail) | guinea brocade, Getzner brocade, shedda | agbada, senator | per yard; GBP |
| US (Harlem, Bronx) | English, French, Wolof | bazin, Getzner, brocade | boubou, grand boubou | per yard; USD |

Consequences for the build: discovery queries are generated per hub in that hub's languages; the classifier infers currency from location and language when a caption omits it; a Nigerian search for "shadda" must reach the same fabric concept as a Dakar search for "bazin riche"; and "Getzner" is both a brand and, in French markets, the word for the fabric.

## 2. Full taxonomy

The machine-readable version is `data/taxonomy.yaml` (76 concepts, 439 labels); the readable version with evidence levels is `docs/taxonomy-seed.md`. The tables below list every label with where it was observed.

### 2.1 Fabric

| Concept | Labels (language, market) | Observed at | Conf. |
|---|---|---|---|
| Bazin (root) | bazin (any); basin (misspelling); brocade (en); brocart (fr); brocard (fr misspelling, common in captions); damask (en); damassé (fr); tissu bazin (fr) | Instagram and Threads captions ("Collection TABASKI 2026 Bazin + brocard bleu Taille du 34 au 50", instagram.com/p/DXshAMPgr1X); Wikipedia Boubou/Senegalese kaftan | H |
| Bazin riche | bazin riche (any); rich bazin (en); bazin rich, basin riche (misspellings, Etsy titles); super riche, bazin super riche (fr, Jumia CI "Bazin Super Riche Bonheur") | Etsy market pages (etsy.com/es/market/bazin_riche, 574 items; etsy.com/market/women_bazin_riche 722); jumia.ci/mlp-k-bazin | H |
| Guinea brocade / shadda | guinea brocade, guinea cloth, shadda, shedda, supreme bazin shadda (en, NG) | Nigerian Facebook group post "Quality Guinea brocade Supreme bazin Shadda 10500 per yard" (facebook.com/groups/996146843797025/posts/9639071216171168); jumia.com.ng/mlp-guinea-brocade; Jansen Holland category "Bazin Riche – Brocade – Shedda" (jansenholland.com/bazin-riche); Wikipedia Balogun Market ("shadda, and brocade") | H |
| Getzner | getzner (any); djezner (Wolof transliteration, TikTok "THIOUB DJEZNER model 75,000 FCFA"); bazin getzner, getzner brodé, getzner original, getzner authentique (fr); getzner bazin (en) | tiktok.com/discover/model-thioub-tabaski-2025; seneweb "Grand Boubou Getzner Brodé"; facebook.com/BassGetzner; mamagetzner.com | H |
| Getzner lines | Super Magnum, Super Magnum Gold XL, Madame Getzner, Phantom XL, Super Wagambari Gold XL, Empire Getzner XL, Wifi Brocade, Yard Material, Atiku Swiss Voile (all evidenced at empiretextiles.com/products/Brocade and getzner-official.at product catalogue "Super Magnum 277-21-433"); Getzner 8, Empereur (Bamako resellers via radiojeunessesahel.com, M). "Chigan" and "Excellence": not evidenced anywhere | Kano sellers price by line: "Madame Getzner ₦15,000/yd" (x.com/MuhaAly/status/1947305581393445284), "Phantom Getzner ₦8,500/yd" (facebook.com/ABUMAHARTEXTIL), "Super Magnum ₦5,200/yd" (facebook.com/Kwari01) | H/M |
| Imitation bazin | bazin moins riche, bazin ordinaire, bazin chinois (fr); chinese bazin, "austrian quality" (en, AliExpress titles) | jumia.ci "Bazin Moins Riche Blanc"; aliexpress.com/popular/bazin-riche-getzner; alibaba.com/showroom/getzner-bazin (brand squatting, from US$0.35/yd) | H |
| Other bazin brands | Bauer Fulda (Expat-Dakar and CoinAfrique SN ads, 10,000 F/m); Drews, Ganila, Suprême textile (Facebook group name "Vente de Bazin, getzner, drews, ganila, suprême textile") | facebook.com/groups/669074674465183 | M |
| Atiku (sibling, not bazin) | atiku, atiku fabric, cotton polish (en, NG) | pwfabrics.co "significance of Atiku fabric"; jumia.com.ng/mlp-atiku-fabric; Getzner's own "Atiku Swiss Voile" line | H |
| Out of scope | wax, ankara, pagne, bogolan, lace/dentelle, aso oke, kente, adire | used as negative signals in the relevance gate | H |

### 2.2 Garment

| Concept | Labels | Observed at | Conf. |
|---|---|---|---|
| Boubou | boubou (any); bubu (misspelling, Alibaba "bazin riche bubu"); mbubb (Wolof, rare in captions); tenue bazin, tenue en bazin (fr); bazin outfit (en) | encyclopedia.com boubou entry; Wikipedia Senegalese kaftan | H |
| Grand boubou | grand boubou, grand boubou 3 pièces, trois pièces, grand boubou brodé, boubou brodé (fr); gandoura (Niger, Cameroon: "Gandoura, also called Grand Boubou", africtudes.com) | maisondaavi.com 2026-03-23 Tabaski guide ("three-piece grand boubou remains the absolute reference"); foireconnect.com "grand boubou brodé" 85,000 FCFA; facebook.com/6pointneuf "Grand Boubou Bazin Getzner disponible sur commande prix 150000f" | H |
| Kaftan | kaftan, caftan (fr); xaftaan (Wolof); kaftan Moussa (women's Tabaski kaftan, SN) | Wikipedia Senegalese kaftan; maisondaavi.com Tabaski 2026 | H |
| Taille basse | taille basse, modèle taille basse (fr) | tiktok.com/discover/les-model-taille-basse-au-senegal; pinterest.com/alimagueye/taille-basse-bazin | H |
| Ndoket | ndoket, ndokette (Wolof); boubou à la française | Wikipedia Boubou (clothing) | M |
| Babban riga | babban riga, babbar riga (Hausa) | guardian.ng traditional clothing; omirenstyles.com babbar-riga | H |
| Agbada | agbada, buba and sokoto, 3 pieces agbada, agbada set (NG) | alibaba showroom "shadda brocade nigeria style" ("often used for agbada, buba, sokoto") | H |
| Senator | senator, senator style, senator wear (NG) | clothingalhaji.com (Kaduna) | H |
| Jalabiya | jalabiya, jalabia (NG north, Niger) | clothingalhaji.com | M |
| Drâa | drâa, boubou mauritanien | voyagemauritanie.com | M |
| Bridal | tenue de mariée, robe de mariée bazin, tenue mariage (fr); bridal bazin, wedding bazin (en) | diodioglow.com "budget mariage Sénégal 2026" (bridal outfit 180,000–650,000 FCFA) | M |
| Women's, men's, children's, couple sets, dresses, shirts | bazin femme, bazin homme, ensemble homme, chemise bazin, robe bazin, ensemble enfant, ensemble couple (fr); women bazin, men's bazin set, bazin dress, kids bazin, couple bazin (en) | Afrikrea Rich Bazin category (couple sets, kids' sets); Etsy "men 3 pieces boubou" 975 results; pinterest ideas "chemise bazin riche homme" | H |

### 2.3 Technique

| Concept | Labels | Observed at | Conf. |
|---|---|---|---|
| Embroidery | broderie, brodé, brodée, broderie machine, broderie main, bazin brodé (fr); embroidery, embroidered (en) | YouTube channel "Broderie Machine"; seneweb "Grand Boubou Getzner Brodé: une tunique pour séduire Dieu"; diodioglow embroidery 50,000–120,000 FCFA | H |
| Dyeing | thioup, thioub, cuub (Wolof); teinture, bazin teint, teinture artisanale, teinture de Bamako, Getzner teinté (fr); gala (Bambara); tie-dye bazin (en) | facebook.com/bazingetluxe "Bazin getzner teinture artisanale made in Mali la meilleur galla … à Bamako"; ikasougou.com/malibazin "bazin getzner teinté"; jiji.sn "bazin thioup getzner ordinateur et perlage" | H |
| Tailoring | couture, sur mesure, prêt-à-porter, tailleur, couturier, couturière, atelier, styliste, modéliste (fr); tailor, seamstress, bespoke, made to measure, fashion designer (en) | lesoleil.sn 2026-05-14 "Préparatifs Tabaski 2026: rush chez les tailleurs et cherté de la couture"; instagram.com/p/DTxrutXjNZD "prêt à porter et sur mesure" | H |
| Beading | perlage, perles, strass (fr); beading, stones (en) | jiji.sn listing "ordinateur et perlage" | M |

### 2.4 Occasion (with the 2026–2027 calendar)

| Concept | Labels | Dates | Conf. |
|---|---|---|---|
| Tabaski (Eid al-Adha) | tabaski, tenue tabaski, modèle tabaski 2026/2027, collection tabaski (fr); tobaski (GM); eid al-adha; aïd el-kébir; big sallah (NG) | 16 May 2027 (some calendars 17 May); tailors stop taking custom orders about 3–4 weeks before | H |
| Korité (Eid al-Fitr) | korité, mode korité (fr); eid al-fitr; small sallah (NG) | about 9–10 March 2027 | M |
| Gamou / Mawlid | gamou, maouloud, mawlid, Tivaouane (SN) | 14–15 August 2027 | H |
| Grand Magal de Touba | magal, grand magal, Touba (SN; white bazin) | about 22 July 2027 | M |
| Wedding | mariage, mariage sénégalais, mariée (fr); wedding, senegalese wedding, malian wedding, bride (en); owambe, aso ebi (Yoruba) | year-round; season conventions unverified | H |
| Naming ceremony | baptême (fr); ngente (Wolof); naming ceremony | — | M |
| Christmas / New Year | Noël, fêtes de fin d'année (fr); Christmas, New Year (en) | 25 Dec 2026, 1 Jan 2027 (Christian buyers in SN, BJ, NG) | H |
| Sallah | sallah, sallah outfit (NG) | as Eid dates | M |
| Ceremony / formal | cérémonie, tenue de fête, soirée, gala (fr); formal wear (en) | — | M |

### 2.5 Commerce phrases that mark a seller (the signals the extractor keys on)

| Signal | Phrases actually seen |
|---|---|
| Wholesale | vente en gros et détails, gros et détail, en gros, grossiste, import de Dubai, usine (Facebook group "Vente en gros et détails de bazin import de Dubai (00223…)"; Mama Getzner wholesale from 300 m) |
| Retail | vente en détail, boutique, magasin, shop, store |
| Order channel | DM pour commander, commande en DM, en MP, inbox, DM to order, DM for price; WhatsApp, appel et WhatsApp, wa.me links (facebook.com/getznerbazin La Courneuve "wa.me/33774139802"; Benin seller "13,000 F/m — +229 90 72 60 05 appel et WhatsApp") |
| Snapchat channel | "SNAP 👻: handle" in Dakar boutique captions (instagram.com/6point9_/p/CyYq8LZI1Ia) |
| Availability | disponible, disponible sur commande, sur commande, en stock, épuisé, précommande |
| Shipping | livraison, livraison partout, livraison par GP, GP Dakar Paris, expédition, envoi, DHL, ships to, worldwide shipping, nationwide delivery. GP = "gratuité partielle" (traveller courier), about €10/kg Paris–Dakar; platforms gprelay.com, gpma.app, colisafrique.com, gpbagage.com, Diatta Voyages |
| Payment | Wave, Orange Money, avance, acompte, 50% (deposit 50/50 per maisondaavi.com 2026-02-15), PayPal |
| Timing | délai, prêt en, avant Tabaski, dernière commande, clôture des commandes (10–15 days for an existing model, 3–4 weeks custom) |
| Authenticity | original, authentique, certifié, made in Austria, lisière, signature dorée, parfum (rose scent), contrefaçon, faux Getzner, vrai Getzner (jlhdiffusions.com and mamagetzner.com anti-fake guides; getzner-official.at quality promise) |
| Promotion | promo, promotion, solde(s), prix cassé, réduction (TikTok "bazin getzner promo"; Dakar HLM5 Tabaski promo 3 m 9,000 F / 4 m 12,000 F / 5 m 15,000 F) |
| Price | prix, FCFA, F CFA, CFA, "F" after a number, le mètre, la pièce, per yard, ₦, naira |

### 2.6 Spelling and transliteration variants to index

basin riche, bazin rich, shedda, shadda, brocard, bubu, thioup/thioub/cuub, Djezner, ndoket/ndokette, xaftaan/kaftan/caftan, babban/babbar riga, jalabia, korite (no accent), bapteme, noel. Not evidenced: guetzner, gitzner, bazan, tchoup.

### 2.7 Corrections to the original plan's terms

- "GP" is gratuité partielle, not gratuité de passage (dakaractu.com, senef.fr, teranga-services.com).
- "Mbaxal" is a rice dish, not a garment.
- "Atiku" is a different fabric, not a bazin name.
- "Bazin Sikasso" and "Getzner Malien" were not found in use; "bazin malien", "bazin du Mali", "Getzner teinté" are.
- "Chigan" and "Excellence" are not evidenced Getzner lines.
- "Bazin prix" and "Bazin wholesale" are not how sellers write; "vente en gros et détails", "promo", "disponible sur commande" are.

## 3. Where the data surfaces, platform by platform

Ranked by how much Bazin commerce actually lives there, with what is readable.

| Rank | Platform | What is there | Evidence | Readable? |
|---|---|---|---|---|
| 1 | Facebook (groups and pages) | The densest French-language trade, especially Mali and Senegal wholesale-retail. Named sales groups: "groupe de vente Bazin vip getzner en gros", "La maison de Bazin Getzner 🇲🇱", "Modèle de Bazin homme et femme et vente…", "Saïd couture et broderie vente des pagne et Bazin", "Vente de Bazin, getzner, drews, ganila, suprême textile", "groupe de vente Bazin chic", "Groupe Bazin bonheur… Bamako Mali", "Vente en gros et détails de bazin import de Dubai", "Vente Bazin riche super gold", "Vente de bazin en gros et en détail Abidjan Adjamé Roxy". Seller pages: Vente Bazin Getzner (La Courneuve), Bazin Getzner Niamey, Bazin Getzner Austria (grossiste-détail), Bass Getzner and Maison du Getzner (Dakar), Mama Getzner (Paris), bazinsetaccessoires (how-to-spot-fake video) | facebook.com/groups/308169010835042, /1331885920563368, /2143842188990703, /438311013622438, /669074674465183, /814877525878716, /1107664799755307, /1338451282914249, /278674391932818; facebook.com/getznerbazin, /bazingetznerniamey, /bazingetzner.grossistedetail, /BassGetzner, /mamagetzner | Groups are login-gated (member counts unreadable); public pages partly readable; Meta bans automated collection (accepted risk, D2) |
| 2 | WhatsApp | The standard order channel everywhere: numbers in bios and captions, wa.me links, WhatsApp Business catalogues, live sales (Mama Getzner "live sales on WhatsApp +33 6 05 79 70 21"); Kaffrine vendors sell via WhatsApp, TikTok and Facebook (fr.allafrica.com/stories/202503290114.html) | mamagetzner.com; facebook.com/getznerbazin; Benin seller pages | Not a crawlable surface. Captured as contact channels; consumers click through |
| 3 | TikTok | Tag pages (/tag/bazin, /tag/bazinriche, /tag/bazinmali🇲🇱) and dozens of auto-generated discover pages: vendeur-de-bazin (434.9K posts shown, may be stale), bazin-getzner, bazin-riche-getzner(-homme, -modele-2025), boutique-de-bazin-paris, vente-bazin-riche-dakar, models-coupoul-getzner-tabaski-2025, model-boubou-homme-getzner-nigerian, meilleur-tailleur-au-senegal-a-dakar, best-african-tailor-in-nyc, nyc-nigerian-tailors, couturier-nigerian-a-paris, magasin-de-tissus-a-dakar, gp-cotonou-dakar-envoi-colis. Seller accounts: @bazin_riche_getzner (Lomé), @alphabazin01, @mamagetzner.com, @iboukun224 (Guinea, anti-fake explainers), @platinumstore0, @bassoum.design.officiel. Price content: Dakar HLM5 Tabaski promos, RTW grand boubou 60,000 F, "THIOUB DJEZNER model 75,000 FCFA" | tiktok.com/discover/vendeur-de-bazin; tiktok.com/discover/vente-bazin-riche-dakar; tiktok.com/@bazin_riche_getzner; tiktok.com/@iboukun224/video/7548238954202483974 | Public pages render logged-out; July 2026 terms bar extraction (accepted risk) |
| 4 | Instagram | Vendor posts from Dakar, Abidjan, Bamako, Lagos; captions carry prices, sizes ("Taille du 34 au 50"), "prêt à porter et sur mesure", WhatsApp and Snapchat handles. Hashtag clusters: #bazin with #malian, #modesenegalaise, #tabaski, #malianwedding (best-hashtags.com/hashtag/bazin). Hashtag counts are no longer public | instagram.com/p/DXshAMPgr1X; instagram.com/p/DTxrutXjNZD; instagram.com/mamagetzner; instagram.com/popular/bazin-boubou-styles-2026 | Profiles show 6–12 posts logged out; hashtag pages top 9; automated collection barred since Jan 2025 (accepted risk) |
| 5 | Snapchat (Senegal) | A parallel market: "Senegal Clothing" topic with millions of clips (May 2026), "Senegal Entrepreneurs", Dakar Business Corner (15.1k subscribers); Dakar boutiques put "SNAP 👻: handle" in Instagram captions; French press calls Snapchat "le nouveau marché numérique" | snapchat.com/topic/senegal-clothing; snapchat.com/@dakarbusiness1; bondyblog.fr Snapchat parallel market piece | Not crawlable; capture handles as a contact channel |
| 6 | YouTube | Tutorial and compilation channels: DT Couture (UCUnr9OffAJYbUWeT464IM1Q, "tutorials every 2 days"), Broderie Machine; playlists "Modeles BAZIN RICHE", "Robes en bazin de la couture sénégalaise"; seasonal compilations "100+ nouveaux styles bazin riche 2026", "+300 robes bazin riche et Getzner brodé 2023", "Mode korité 2024", "Tabaski 2025: Bazin riche, Getzner, Brocart… la folie des tissus envahit Dakar" | youtube.com/channel/UCUnr9OffAJYbUWeT464IM1Q; youtube.com/playlist?list=PLAXgczTm7zW1IQRG9iaUmUrewyn4J-Thj; youtube.com/watch?v=JoJe7KW78ss; youtube.com/watch?v=JD15wXKUMos | Official Data API (30-day statistics cap) |
| 7 | Pinterest | Large curated boards: "900+ idées de GETZNER" (pinterest.com/ndeyengone/getzner), "900+ idées de Bazin en 2026" (pinterest.com/amadoueliane/bazin), "720 boubou and bazin styles for women senegal" (pinterest.com/fasillah/boubou), "180 idées de Tailleur Sénégal"; ideas hubs for "bazin riche getzner", "model grand boubou homme bazin", "chemise bazin riche homme". Pins often link back to seller sites and Instagram | fr.pinterest.com/ideas/bazin-riche-getzner/940001492134 | Public and indexed; API review-gated; scraping barred (accepted risk) |
| 8 | Etsy | 574 "bazin riche" items, 722 "women bazin riche", 196 "getzner" (FR), 974 "getzner dress" (UK), 1,000+ "getzner bazin" (CA), 975 "men 3 pieces boubou"; grand boubous £17–£243, €15–€165, CA$145–954; titles keyword-stuff "Getzner" | etsy.com/es/market/bazin_riche; etsy.com/uk/market/getzner_dress; etsy.com/ca/market/getzner_bazin; etsy.com/market/grand_boubou | Official API (6-hour freshness, disclaimer) |
| 9 | Afrikrea (ex-ANKA) | 22,000+ sellers in 47 countries, dedicated "Rich Bazin" category (raw 4–5 m Mali bazin, women's boubous, couple sets, kids' bazin, men's 2-piece sets; sellers afrostyleparis, kaysol, maisonbeaurepaire); parent liquidated July 2025, acquired by Global Shop Group October 2025, relaunched as Afrikrea 27 Aug 2026 | marketplace.anka.africa/en/categories/bazin; techcabal.com 2025-10-22; techmoran.com 2026-08-27 | Crawlable category pages |
| 10 | Classifieds | CoinAfrique (SN, CI, BJ, ML, BF): Getzner 38,000 F/3 m, Super Magnum 12,000 F/m, "factory-direct Getzner" 13,000 F/m, SN bazin riche 5,000 F/m, Bauer Fulda 10,000 F/m; tailor and atelier ads. Expat-Dakar: "Super Magnum Gold" 4,500 F, Getzner thioup 3–6 m (Ouakam), tailor job ads, seasonal editorial. Jiji NG (Kano, Lagos guinea brocade; Lagos Island tailoring services) and Jiji SN (Tissus category: Rufisque, Dakar-Plateau, Mermoz) | sn.coinafrique.com/categorie/tissus-et-foulards; bj.coinafrique.com/annonce/tissus-et-foulards/bazin-getzner-vip-mali-1300350; expat-dakar.com/annonce/le-bazin-riche-6245345; jiji.ng/kano/clothing/original-guinea-cloth-…; jiji.sn/25-fabrics | Public listing pages (terms not yet checked) |
| 11 | Amazon, AliExpress, Alibaba | Generic-brand Chinese-made "bazin riche" boubous and 5 m "perfumed" brocade on Amazon; AliExpress "Bazin Riche Getzner" 5 yd US$28–45, US$9.88/m; Alibaba showrooms "getzner-bazin", "getzner-brocade-factory" from US$0.35/yd | amazon.com/African-Perfumed-Brocade-Jacquard-Material/dp/B0DPM7L5V4; aliexpress.com/i/33054140104.html; alibaba.com/showroom/getzner-bazin.html | Over-indexed counterfeit channel; useful only as a negative signal |
| 12 | Retailer and distributor sites | Mama Getzner (Paris, Harlem; mamagetzner.com), JLH Diffusions (wholesale, jlhdiffusions.com), Empire Textiles and Majestic London (UK), Jansen Holland (NL), Sy Getzner / SBG (Dakar, sbg-sn.com), dimancheabamako.com, monbazin.com, ikasougou.com/malibazin (Mali), senegalmarket.it (Italy), fabergegalore.com "Basin Riche Getzner", asatsuclothing.com, african-avenue.com, BoubouQueens, Maison Barry; Getzner's own shop getzner-official.at/en/shop | see column | First-party feeds |
| 13 | Directories and apps | Yombal.sn (Dakar made-to-measure marketplace, updated Feb 2026), Malicouture.com (Mali tailor showcase with WhatsApp), annuaire-couturiers.fr (volunteer directory of African tailors and fabric shops in France, lists Mama Getzner), Sokofa (diaspora made-to-measure, July 2026), Stitches Africa (Lagos), ArtisanOga (tailor hiring), LoveWeddingsNG and BellaNaija Weddings vendor programmes, senegal-mariage.com, monmariageamoi.com (Abidjan) | yombal.sn; malicouture.com; annuaire-couturiers.fr; disruptafrica.com 2026-07-06 | Crawlable; partnership candidates |
| 14 | Jumia | Eight markets (NG, GH, CI, SN, KE, UG, EG, MA), not Mali, Gambia or Benin; thin bazin in CI and NG ("Bazin riche rouge 3 m", "Guinea brocade" 5/10-yd cuts); nothing surfaced in SN | jumia.ci/mlp-k-bazin; jumia.com.ng/mlp-guinea-brocade | Not a source |
| 15 | X / Twitter | Minimal commercial signal: Kano per-yard price tweets (@MuhaAly), "GETZNER NIGERIA" @abadtextile (Kano and Abuja online store) | x.com/MuhaAly/status/1947305581393445284; x.com/abadtextile | Pay-per-use API; low value |
| 16 | Reddit | No commercial signal; useful only for demand questions ("where to buy bazin in NYC") | — | Free tier non-commercial |

What page one of web search shows today (web results only, no Maps pack):

- "where to buy authentic getzner bazin online": AliExpress, three Etsy pages, an Alibaba showroom, Empire Textiles, Asatsu Clothing. Getzner's own shop and every official partner absent.
- "bazin riche boubou tailor new york": a Photoville exhibition, eBay, a Facebook page, Etsy, two French e-shops, BoubouQueens, Maison Barry. Zero New York tailors; Yelp and TikTok appear only when rephrased "African tailor Harlem".
- "getzner bazin paris château rouge": one Facebook page (IBA château rouge), a TikTok discover page, four Mama Getzner results, then Wikipedia pages about people surnamed Bazin.
- "trouver un tailleur Dakar": Senekeur blog guide, CoutureSo and CouturArt (tailor SaaS), an expat blog, TikTok, annuaire-senegal.com, Yombal.

## 4. Where the vendors are

| Hub | Named places and sellers | Source | Conf. |
|---|---|---|---|
| Dakar | Marché HLM / HLM5 (Getzner and bazin riche vendors, e.g. Mansour Diaw; ≈12,000 F/m); Sandaga; Sy Getzner at Sea Plaza (opened April 2023 with Tobias König, Head of Getzner Business Unit Africa); Bass Getzner; Maison du Getzner; Ouakam thioup sellers | tiktok.com/discover/vente-bazin-riche-dakar; getzner.at story "Sy Getzner opens new boutique in Dakar"; sbg-sn.com | H |
| Bamako | Bathily Business Group, Baka Bathily's flagship at Marché ACI 2000 (since 2016; Getzner's decades-long Mali partner); Grand Marché resellers; online dimancheabamako.com, monbazin.com, ikasougou.com; "teinture artisanale"; Semaine du Boubou sponsored by Getzner | getzner-official.at story "Getzner Textil and Bathily Business Group" | H |
| Paris | Château Rouge / Goutte d'Or (18e): Mama Getzner 44-50 rue Polonceau and 31 rue Doudeauville (sells exclusively Getzner, wholesale from 300 m, tailoring); "fabric shops abound… tailors predominantly Senegalese"; Mazalay Couture; Vente Bazin Getzner in La Courneuve; JLH Diffusions (wholesale to Dakar, Bamako, Abidjan resellers) | mamagetzner.com/en/pages/shops; seneplus.com Château Rouge piece; lafropeen.com guide; littleafrica.fr | H |
| New York | Harlem "Le Petit Sénégal", W 116th St: Mama Getzner 253 W 116th (+1 212 866-3087), Kilimanjaro fabric and boubou tailoring 117 W 116th, tailors inside Malcolm Shabazz Harlem Market; Yelp "African Tailors" (Kebe's African Fashions, AG Fashion, Yara African Fabrics, Noni Styles, Moshood Creations, African Queen Boutique); Bronx embroidery shop at 2024 Webster Ave. Little Senegal is shrinking with gentrification | facebook.com/mamagetzner/posts/636322259737074; brickunderground.com Little Senegal; untappedcities.com Harlem Little Africa; yelp.com African Tailors Harlem | H |
| Lagos, Kano, Kaduna, Abuja | Balogun Market (Lagos: "imported Ankara, Atampa, lace, shadda, and brocade"); Kantin Kwari (Kano: per-yard Getzner sellers; Maitangaran Textiles, 4 Fagge Ta Kudu); "GETZNER NIGERIA" @abadtextile (Kano, Abuja, nationwide delivery); Clothing Alhaji (Kaduna tailoring); Oversabi Stitches (Lagos bespoke) | Wikipedia Balogun Market; maitangarantextiles.site123.me; x.com/abadtextile | M |
| Abidjan, Cotonou, Lomé, Niamey | Adjamé Roxy wholesale group (Abidjan); CoinAfrique Benin Getzner sellers (Dantokpa); "Vente de Bazins riche Getzner à Lomé"; Bazin Getzner Niamey page; GP couriers Cotonou–Dakar | facebook.com/100075924096910; tiktok.com/discover/bazin-riche-getzner-promo-en-cote-d-ivoire; facebook.com/bazingetznerniamey | M |
| Italy (Lombardy) | Bergamo about 9,350 Senegalese, Brescia 6,716, Milan 6,434; clusters Zingonia (BG), Pontevico and Bovezzo (BS); Kechic (Milan) Italian-Senegalese tailoring brand; senegalmarket.it online bazin seller | tuttitalia.it Bergamo foreign citizens; Wikipedia Senegalese people in Italy | M |
| Netherlands, Belgium | Jansen Holland (Getzner distributor selling EU-wide in euros); Brussels Matonge (not researched) | jansenholland.com/brand/getzner | H / — |
| UK | Empire Textiles (8 Getzner lines), Majestic London; Peckham Holdron's Arcade boutique "Love's" (kaftans, fabrics); retail is Nigerian and Ghanaian-led; Senegalese or Gambian-specific London shops not evidenced | empiretextiles.com/products/Brocade; southeast15.com Peckham shops | M |
| Other US cities, Lyon, Marseille, Spain, Germany | Population presence only (Philadelphia, DC, Atlanta, Chicago, Houston, Minneapolis for Senegalese and Malian communities); no shop-level evidence gathered | Wikipedia Senegalese Americans, Malian Americans | L |

## 5. The brand at the centre

Getzner Textil AG, Bludenz, Austria: about €490M group revenue in FY2023, roughly 1,600 staff, African clothing damasks reported as about 70% of production (medium confidence). Official consumer site getzner-official.at with an online shop and a Lustenau boutique; factory shop in Bludenz. Authenticity markers it publishes: rose scent, golden edge stamp, woven brand name, branded packaging; third-party resellers also describe a woven "Getzner Textil Austria" watermark and a hologram label. No dealer locator, no partner-store chain, no consumer app, no QR or serial verification found, while Chinese "Getzner" sells openly from US$0.35 per yard. Known partners: Bathily Business Group (Mali), Sy Getzner / SBG (Senegal), Mama Getzner (Paris, Harlem), JLH Diffusions (France wholesale), Empire Textiles and Majestic London (UK), Jansen Holland (NL); Nigeria distributors unverified. Sponsors Semaine du Boubou (Bamako), funded a maternity ward in Sikasso and a basketball court in Dakar.

## 6. Prices observed (for the price model)

| Item | Place | Price | Source |
|---|---|---|---|
| Getzner per metre | Bamako | 7,500–12,500 FCFA by line | radiojeunessesahel.com |
| Getzner per metre | Dakar HLM | about 12,000 FCFA; Tabaski promos 3 m 9,000 F, 4 m 12,000 F, 5 m 15,000 F | accio.com aggregator; TikTok HLM5 promo |
| Getzner per metre | Cotonou classifieds | 12,000–13,000 FCFA; 38,000 F per 3 m | CoinAfrique BJ |
| Madame Getzner per yard | Kano, 2025 | ₦15,000 | x.com/MuhaAly |
| Guinea brocade wholesale per yard | Nigeria | ₦10,500 | Facebook group post |
| Imitation "Getzner" | Alibaba / AliExpress | US$0.35–10 per yard; 5 yd US$28–45 | alibaba, aliexpress |
| Ready thioub outfit | Senegal TikTok seller | 75,000 FCFA | tiktok discover |
| Men's embroidered grand boubou | Dakar | 65,000–150,000 FCFA typical; premium fabric 80,000–280,000 plus embroidery 50,000–120,000; custom up to 600,000+ | seneweb, foireconnect, facebook 6pointneuf, maisondaavi, diodioglow |
| Bridal complete outfit | Dakar | 180,000–650,000 FCFA | diodioglow.com 2026 |
| Full traditional outfit | Nigeria | ₦100,000–300,000 | omirenstyles.com |
| Finished grand boubou | Etsy | £17–£243; CA$145–954 | etsy market pages |
| GP courier | Paris–Dakar | about €10/kg; formal carriers €25–45/kg | entrepreneur-en-afrique.com; colisvoyage.net |

## 7. Still unverified

Instagram and TikTok hashtag totals; Facebook group member counts; Afrikrea's 2026 commission and category size; Senegal Snapchat reach; Paris and New York per-piece Getzner prices; the imitation price differential in-market; Google Trends and keyword volumes (no published figures surfaced); Gambia (Serrekunda), Guinea (Conakry), Ghana, Cameroon and Burkina vocabulary; shop-level presence in US cities beyond New York and in Lyon, Marseille, Spain, Belgium, Germany; whether "Big/Small Sallah" is standard naming; Getzner's official line roster and whether the hologram label is Getzner's or a distributor's. All of it needs one day in a logged-in browser or a native-speaker reviewer.
