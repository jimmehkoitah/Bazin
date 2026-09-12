"""End-to-end pipeline test against the local Postgres, with synthetic profile bundles and the heuristic LLM."""

from datetime import datetime, timedelta, timezone

import pytest

from bazin.ingest import Ingestor, load_source_policies
from bazin.llm.client import HeuristicLLM
from bazin.models import MediaIn, ObservationIn, ProfileBundle
from bazin.pipeline import score as sc
from bazin.pipeline.classify import classify
from bazin.pipeline.cluster import HashEmbedder, run_clustering
from bazin.pipeline.enrich import enrich
from bazin.pipeline.evidence import collect
from bazin.pipeline.identity import resolve_identity
from bazin.pipeline.qa import judge, sample
from bazin.pipeline.relevance import gate, unjudged_identities
from bazin.search.parse import parse_query
from bazin.search.rank import SearchOptions, search
from bazin.taxonomy import load_into_db
from bazin.db import fetch_all, fetch_one

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


def _post(platform, url, caption, days_ago, tags, thumb=None, kind="post"):
    return ObservationIn(
        platform=platform, source_url=url, kind=kind, published_at=NOW - timedelta(days=days_ago), caption_excerpt=caption,
        hashtags=tags, acquisition_method="third_party_scraper", media=[MediaIn(media_url=thumb)] if thumb else [],
    )


def bundles() -> list[ProfileBundle]:
    dakar_ig = ProfileBundle(
        platform="instagram", url="https://www.instagram.com/dakarcouture/", handle="dakarcouture", display_name="Dakar Couture",
        bio="Tailleur sur mesure à Dakar (HLM). Bazin riche Getzner brodé. Livraison Paris et USA par GP. WhatsApp +221 77 123 45 67",
        bio_link="https://wa.me/221771234567", followers=12400,
        observations=[
            _post("instagram", "https://www.instagram.com/p/A1/", "Grand boubou brodé disponible sur commande 150 000 FCFA. Prêt en 3 semaines.", 20, ["bazinriche", "tabaski2026", "grandboubou"], "https://cdn.example/a1.jpg"),
            _post("instagram", "https://www.instagram.com/p/A2/", "Taille basse thioub blanc et bleu pour la Korité, 75 000 F. DM pour commander", 60, ["bazin", "tailebasse", "korite"], "https://cdn.example/a2.jpg"),
            _post("instagram", "https://www.instagram.com/p/A3/", "Merci à notre cliente pour la confiance, essayage réussi de son boubou de mariage", 90, ["mariage", "bazin"]),
            _post("instagram", "https://www.instagram.com/p/A4/", "Broderie main sur bazin getzner, détail du col", 120, ["broderie", "getzner"]),
            _post("instagram", "https://www.instagram.com/p/A5/", "Kaftan homme bazin riche, disponible en plusieurs couleurs, 95 000 FCFA", 150, ["kaftan", "bazinhomme"]),
        ],
    )
    dakar_tt = ProfileBundle(
        platform="tiktok", url="https://www.tiktok.com/@dakar.couture", handle="dakar.couture", display_name="Dakar Couture",
        bio="Couture bazin Dakar. Commandes wa.me/221771234567", followers=30000,
        observations=[_post("tiktok", "https://www.tiktok.com/@dakar.couture/video/1", "Modèle Tabaski 2026 grand boubou getzner brodé #bazin", 15, ["bazin", "tabaski2026"], kind="video")],
    )
    paris_shop = ProfileBundle(
        platform="instagram", url="https://www.instagram.com/mamagetzner/", handle="mamagetzner", display_name="Mama Getzner Paris",
        bio="Boutique Getzner à Château Rouge Paris. Vente en gros et détail. Livraison partout en Europe. +33 6 05 79 70 21", bio_link="https://mamagetzner.com", followers=85000,
        observations=[
            _post("instagram", "https://www.instagram.com/p/B1/", "Super Magnum Gold disponible, 35€ le mètre. Livraison Europe.", 5, ["getzner", "bazinriche", "paris"], "https://cdn.example/b1.jpg"),
            _post("instagram", "https://www.instagram.com/p/B2/", "Madame Getzner nouvelle collection, promo 30€/m ce week-end", 12, ["getzner", "chateaurouge"]),
            _post("instagram", "https://www.instagram.com/p/B3/", "Phantom XL et Wifi Brocade en stock", 40, ["getzner", "bazin"]),
        ],
    )
    lagos_rtw = ProfileBundle(
        platform="instagram", url="https://www.instagram.com/lagosbrocade/", handle="lagosbrocade", display_name="Lagos Brocade Hub",
        bio="Guinea brocade & shadda, Balogun Lagos. Agbada and senator ready to wear. Nationwide delivery. WhatsApp 0803 123 4567", followers=5000,
        observations=[
            _post("instagram", "https://www.instagram.com/p/C1/", "Madame Getzner shadda ₦15,000 per yard, nationwide delivery", 8, ["shadda", "guineabrocade", "lagos"]),
            _post("instagram", "https://www.instagram.com/p/C2/", "Agbada set ready to wear for Sallah, ₦120,000", 30, ["agbada", "sallah"]),
        ],
    )
    style_page = ProfileBundle(
        platform="instagram", url="https://www.instagram.com/bazinstylesinspo/", handle="bazinstylesinspo", display_name="Bazin Styles Inspo",
        bio="Daily inspiration. Not a seller. DM for credit.", followers=200000,
        observations=[_post("instagram", "https://www.instagram.com/p/D1/", "Look of the day", 3, ["bazinriche", "bazin", "grandboubou"])],
    )
    sneakers = ProfileBundle(
        platform="instagram", url="https://www.instagram.com/sneakerdakar/", handle="sneakerdakar", display_name="Sneaker Dakar",
        bio="Baskets et sneakers à Dakar. Livraison. WhatsApp 77 000 00 00", followers=900,
        observations=[_post("instagram", "https://www.instagram.com/p/E1/", "Nike Air promo 45 000 FCFA", 3, ["sneakers", "dakar"])],
    )
    return [dakar_ig, dakar_tt, paris_shop, lagos_rtw, style_page, sneakers]


@pytest.fixture(scope="module")
def pipeline_db(db):
    from bazin.db import connection
    import yaml
    from bazin.config import DATA_DIR

    with connection() as conn:
        load_into_db(conn)
        load_source_policies(conn, yaml.safe_load((DATA_DIR / "source_policies.yaml").read_text())["policies"])
        ing = Ingestor(conn, adapters={})
        for b in bundles():
            ing.store_bundle(b)
        assert ing.stats.observations_new == 13 and ing.stats.media_new == 3
        unjudged_identities(conn)
        llm = HeuristicLLM()
        gs = gate(conn, llm, use_images=False)
        assert gs.judged == 6
        rel = {r["handle"]: r["relevant"] for r in fetch_all(conn, "select c.handle, c.relevant from candidates c")}
        assert rel["dakarcouture"] and rel["mamagetzner"] and rel["lagosbrocade"] and rel["dakar.couture"]
        assert rel["sneakerdakar"] is False
        for r in fetch_all(conn, "select i.id from identities i join candidates c on c.identity_id = i.id where c.relevant order by i.followers"):
            resolve_identity(conn, str(r["id"]), llm=None)
        es = enrich(conn, llm, use_images=False)
        assert es.enriched >= 3
        cs = classify(conn, llm, use_images=False)
        assert cs.classified >= 10
        collect(conn)
        for r in fetch_all(conn, "select id from businesses where status = 'active'"):
            f = sc.features_from_db(conn, str(r["id"]), now=NOW)
            s = sc.compute(f)
            sc.persist(conn, str(r["id"]), f, s, ["r"], ["c"])
        run_clustering(conn, llm, min_cluster_size=2, embedder=HashEmbedder())
    yield


def test_identity_merge_and_enrichment(pipeline_db, conn):
    dakar = fetch_one(conn, "select b.* from businesses b join identities i on i.business_id = b.id where i.handle = 'dakarcouture'")
    assert dakar["status"] == "active" and dakar["business_type"] == "tailor" and dakar["primary_country"] == "SN"
    handles = {r["handle"] for r in fetch_all(conn, "select handle from identities where business_id = %s", (dakar["id"],))}
    assert handles == {"dakarcouture", "dakar.couture"}  # merged on the shared WhatsApp number
    contacts = fetch_all(conn, "select kind, normalized_value from contact_channels where business_id = %s", (dakar["id"],))
    assert any(c["kind"] == "whatsapp" and c["normalized_value"] == "+221771234567" for c in contacts)
    ships = {r["country"] for r in fetch_all(conn, "select country from locations where business_id = %s and kind = 'ships_to'", (dakar["id"],))}
    assert {"FR", "US"} <= ships
    prices = fetch_all(conn, "select currency, amount_min, usd_equivalent from prices where business_id = %s", (dakar["id"],))
    assert any(p["currency"] == "XOF" and float(p["amount_min"]) == 150000 and p["usd_equivalent"] is not None for p in prices)
    loc = fetch_one(conn, "select city, lat, h3_r7 from locations where business_id = %s and kind = 'atelier'", (dakar["id"],))
    assert loc["city"] == "Dakar" and loc["lat"] is not None and loc["h3_r7"]


def test_classification_evidence_and_scores(pipeline_db, conn):
    dakar = fetch_one(conn, "select b.id, b.quality_score from businesses b join identities i on i.business_id = b.id where i.handle = 'dakarcouture'")
    concepts = {r["concept_id"] for r in fetch_all(conn, "select concept_id from business_concepts where business_id = %s", (dakar["id"],))}
    assert {"garment.grand_boubou", "garment.taille_basse", "technique.embroidery", "occasion.korite"} <= concepts
    kinds = {r["kind"] for r in fetch_all(conn, "select kind from evidence where business_id = %s", (dakar["id"],))}
    assert {"phone_number", "pricing_clarity", "finished_garment", "tagged_customer_post", "cross_platform_identity"} <= kinds
    s = fetch_one(conn, "select * from scores where business_id = %s order by computed_at desc limit 1", (dakar["id"],))
    assert s["total"] > 0.45 and s["commercial_clarity"] >= 0.75 and s["category_relevance"] > 0.5
    paris = fetch_one(conn, "select b.business_type, b.quality_score from businesses b join identities i on i.business_id = b.id where i.handle = 'mamagetzner'")
    assert paris["business_type"] in ("fabric_wholesaler", "fabric_retailer")
    assert fetch_one(conn, "select count(*) as c from clusters")["c"] >= 1


def test_search_ranks_local_maker_first(pipeline_db, conn):
    llm = HeuristicLLM()
    parsed = parse_query(llm, "grand boubou brodé tailleur à Dakar")
    out = search(conn, parsed, SearchOptions(limit=10))
    assert out["results"], out
    assert out["results"][0]["name"] == "Dakar Couture" and out["results"][0]["geo_fit"] == "local"
    assert any(c["kind"] == "whatsapp" and c["href"].startswith("https://wa.me/221") for c in out["results"][0]["contact"])
    parsed2 = parse_query(llm, "getzner fabric shop in Paris")
    out2 = search(conn, parsed2, SearchOptions(limit=10))
    assert out2["results"][0]["name"] == "Mama Getzner Paris"
    parsed3 = parse_query(llm, "bazin tailor in New York")
    out3 = search(conn, parsed3, SearchOptions(limit=10))
    assert out3["notes"] and any(r["geo_fit"] in ("ships_to", "corridor") for r in out3["results"])
    assert not any(r["name"] == "Sneaker Dakar" for r in out["results"] + out2["results"] + out3["results"])


def test_qa_sampling_runs(pipeline_db, conn):
    ids = sample(conn, 5, 5)
    stats = judge(conn, HeuristicLLM(), ids)
    assert stats.sampled == len(ids) and stats.sampled >= 3
