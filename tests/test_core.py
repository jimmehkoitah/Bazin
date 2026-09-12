"""Unit tests that need no database: taxonomy, planner, prices, identity rules, scoring, heuristic LLM."""

from datetime import datetime, timedelta, timezone

from bazin.discovery import planner
from bazin.llm.client import HeuristicLLM, detect_language
from bazin.models import Enrichment, ParsedQuery, PostClassification, RelevanceVerdict
from bazin.pipeline import score
from bazin.pipeline.identity import IdentityFacts, decide, extract_phones, website_host
from bazin.prices import parse_prices, to_usd
from bazin.sources.urls import is_profile_url, resolve_platform
from bazin.taxonomy import hashtag_form, normalize, taxonomy


def test_taxonomy_loads_and_matches():
    tax = taxonomy()
    assert "fabric.getzner" in tax.concepts
    assert tax.concepts["fabric.getzner"].parent_id == "fabric.bazin.riche"
    hits = tax.match("Grand Boubou Getzner brodé disponible sur commande 150 000 FCFA", ["#bazinriche", "#tabaski2026"])
    assert hits["garment.grand_boubou"] == 1
    assert hits["fabric.getzner"] == 1
    assert hits["fabric.bazin.riche"] == 1  # from the hashtag
    assert hits["signal.availability"] >= 1
    assert "fabric.bazin" not in hits  # longest phrase wins, no double counting
    assert tax.is_relevant_text("Quality Guinea brocade Supreme bazin Shadda 10500 per yard")
    assert not tax.is_relevant_text("Nike sneakers promo Lagos")


def test_normalize_and_hashtags():
    assert normalize("Bazin Riché!") == "bazin riche"
    assert hashtag_form("Bazin riche") == "bazinriche"


def test_planner_builds_prioritised_matrix():
    qs = planner.plan(max_priority_hubs=1)
    s = planner.summary(qs)
    assert s["total"] > 300
    assert s["brave"] > 100 and s["apify_instagram"] > 20 and s["overture"] == 5 and s["shopify"] == 7
    first = qs[0]
    assert first.priority == 1
    assert any(q.query == "#bazindakar" for q in qs)
    assert any("Lagos" in q.query and "agbada" in q.query.lower() for q in qs)
    assert len({(q.platform, normalize(q.query), q.market or "") for q in qs}) == len(qs)


def test_prices_parse_common_forms():
    got = parse_prices("Bazin getzner 12 000 FCFA le mètre, boubou complet 150.000f, €45/m, $120, ₦15,000 per yard, 75 000 F")
    by_cur = {(p.currency, p.amount): p for p in got}
    assert ("XOF", 12000.0) in by_cur and by_cur[("XOF", 12000.0)].unit == "metre"
    assert ("XOF", 150000.0) in by_cur
    assert ("EUR", 45.0) in by_cur and by_cur[("EUR", 45.0)].unit == "metre"
    assert ("USD", 120.0) in by_cur
    assert ("NGN", 15000.0) in by_cur and by_cur[("NGN", 15000.0)].unit == "yard"
    assert ("XOF", 75000.0) in by_cur
    assert not parse_prices("call 77 123 45 67")  # phone numbers are not prices
    assert parse_prices("prix 45 000 sur commande", "XOF")[0].currency_inferred
    assert abs(to_usd(655.957, "XOF") - 1.08) < 0.01


def test_phone_extraction_and_hosts():
    assert extract_phones("WhatsApp +221 77 123 45 67 ou wa.me/33774139802") == ["+33774139802", "+221771234567"] or set(extract_phones("WhatsApp +221 77 123 45 67 ou wa.me/33774139802")) == {"+33774139802", "+221771234567"}
    assert extract_phones("Appelez le 77 123 45 67", "SN") == ["+221771234567"]
    assert extract_phones("- [2026-08-01] Grand boubou 150 000 FCFA\n- [2026-07-20] taille basse 75 000 F, tabaski 2026", "ML") == []
    assert website_host("https://linktr.ee/x") is None
    assert website_host("www.mamagetzner.com/pages/shops") == "mamagetzner.com"
    assert website_host("Followers: 30000") is None
    from bazin.llm.client import field_value

    assert field_value("Handle: a\nLink: \nFollowers: 30000\nLink: https://x.com/", "Link") == "https://x.com/"
    assert field_value("Link: \nFollowers: 30000", "Link") == ""


def test_identity_rules():
    a = IdentityFacts(id="1", platform="instagram", handle="dakarcouture", url="u1", display_name="Dakar Couture", bio="+221771234567", bio_link=None, phones={"+221771234567"})
    b = IdentityFacts(id="2", platform="tiktok", handle="dakar.couture", url="u2", display_name="Dakar Couture", bio="wa.me/221771234567", bio_link=None, phones={"+221771234567"})
    assert decide(a, b)[0] == "same"
    c = IdentityFacts(id="3", platform="facebook", handle="dakarcouture", url="u3", display_name="Dakar Couture", bio="+221709999999", bio_link=None, phones={"+221709999999"})
    assert decide(a, c)[0] == "different"  # different phones, no cross-link
    d = IdentityFacts(id="4", platform="facebook", handle="x", url="u4", display_name="Dakar Couture", bio="follow us on instagram @dakarcouture", bio_link=None)
    assert decide(a, d)[0] == "same"  # cross-link
    e = IdentityFacts(id="5", platform="instagram", handle="y", url="u5", display_name="Dakar Couture", bio=None, bio_link=None, country="FR")
    a.country = "SN"
    assert decide(a, e)[0] == "different"


def test_scoring_weights():
    f = score.Features(business_type="tailor", n12_relevant_observations=12, n12_observations=15, price_anchor=True, order_channel=True,
                       shipping_info=True, city_resolved=True, product_observations=12, finished_garments=5, fittings_or_tagged=2,
                       closeups_or_before_after=1, distinct_customers=3, review_count=4, review_rating_norm=0.9, platforms=2,
                       phone_consistency=True, physical_address=True, website=True, account_age_months=24, days_since_last_active=10)
    s = score.compute(f)
    assert 0.85 <= s.total <= 1.0
    assert s.commercial_clarity == 1.0
    f2 = score.Features(business_type="tailor", n12_relevant_observations=1, n12_observations=30, duplicate_images=3, scam_reports=1, days_since_last_active=400)
    s2 = score.compute(f2)
    assert s2.total < 0.15 and s2.trust == 0.0
    r = score.Features(business_type="fabric_retailer", distinct_lines=4, authenticity_evidence=2, brand_partner_listing=True)
    assert score.maker_credibility(r) == 0.85


def test_url_resolution():
    assert resolve_platform("https://www.instagram.com/mamagetzner/?igsh=abc") == ("instagram", "https://www.instagram.com/mamagetzner/", "mamagetzner")
    assert resolve_platform("https://www.tiktok.com/@bazin_riche_getzner/video/7393")[0:1] == ("tiktok",)
    assert resolve_platform("https://mamagetzner.com/en/pages/shops?utm_source=x") == ("website", "https://mamagetzner.com/en/pages/shops", None)
    assert is_profile_url("instagram", "https://www.instagram.com/p/DXshAMPgr1X/") is False
    assert is_profile_url("etsy", "https://www.etsy.com/shop/FabergeGalore")


def test_heuristic_llm_end_to_end():
    llm = HeuristicLLM()
    q = llm.structured("query_parse", system=None, user_text="luxury white grand boubou maker for a Senegalese wedding in NYC under $300", schema=ParsedQuery)
    assert "garment.grand_boubou" in q.garment_concept_ids and q.colors == ["white"] and q.budget.currency == "USD" and q.budget.max == 300
    assert q.location.near and "tailor" in q.business_types and q.luxury_tier
    q2 = llm.structured("query_parse", system=None, user_text="bazin riche femme moins de 200 euros livraison France", schema=ParsedQuery)
    assert q2.budget.currency == "EUR" and q2.budget.max == 200 and q2.location.ships_to == "FR" and q2.gender == "women"
    text = (
        "Identity 1: instagram https://www.instagram.com/dakarcouture/\nHandle: dakarcouture\nName: Dakar Couture\n"
        "Bio: Tailleur sur mesure à Dakar, bazin riche getzner, livraison Paris et USA par GP. WhatsApp +221 77 123 45 67\n"
        "Link: https://wa.me/221771234567\nRecent content:\n- [2026-08-01] Grand boubou brodé disponible sur commande 150 000 FCFA #bazinriche #tabaski2026\n"
        "- [2026-07-20] Taille basse thioub pour la Korité, 75 000 F"
    )
    e: Enrichment = llm.structured("enrich", system=None, user_text=text, schema=Enrichment)
    assert e.business_type == "tailor" and e.locations[0].city == "Dakar" and e.locations[0].country == "SN"
    assert any(c.kind == "whatsapp" and c.value == "+221771234567" for c in e.contact_channels)
    assert set(e.ships_to) >= {"FR", "US"}
    assert any(p.amount_min == 150000 and p.currency == "XOF" for p in e.prices)
    v: RelevanceVerdict = llm.structured("relevance", system=None, user_text=text, schema=RelevanceVerdict)
    assert v.relevant and v.confidence >= 0.7
    c: PostClassification = llm.structured("classify", system=None, user_text="Caption: Taille basse thioub blanc et bleu pour la Korité 75 000 F\nHashtags: #bazin", schema=PostClassification)
    assert {h.id for h in c.concept_ids} >= {"garment.taille_basse", "technique.dyeing", "occasion.korite"}
    assert {col.name for col in c.colors} == {"white", "blue"} and c.gender == "women" and c.shows_price.amount == 75000
    assert detect_language("livraison disponible partout avec le prix pour vous") == "fr"
