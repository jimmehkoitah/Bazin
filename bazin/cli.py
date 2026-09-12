"""Command-line entry points: `bazin <command>`."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import typer
import yaml

from .config import DATA_DIR, get_settings

app = typer.Typer(no_args_is_help=True, help="Bazin discovery engine")
db_app = typer.Typer(help="Database")
ingest_app = typer.Typer(help="Discovery and ingestion")
app.add_typer(db_app, name="db")
app.add_typer(ingest_app, name="ingest")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _recorder_factory(conn):
    from .db import execute

    def record(row: dict) -> None:
        execute(
            conn,
            "insert into llm_calls (stage, model, batch_id, custom_id, input_tokens, output_tokens, cache_read_tokens, cost_usd) values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (row["stage"], row["model"], row.get("batch_id"), row.get("custom_id"), row["input_tokens"], row["output_tokens"], row["cache_read_tokens"], row["cost_usd"]),
        )

    return record


def _llm(conn):
    from .db import fetch_one
    from .llm.client import get_llm

    spent = fetch_one(conn, "select coalesce(sum(cost_usd), 0) as s from llm_calls")["s"]
    return get_llm(get_settings(), recorder=_recorder_factory(conn), spent_usd=float(spent))


def _adapters(fixture_dir: Optional[Path] = None):
    from .sources.base import RawStore
    from .sources.registry import build_adapters

    s = get_settings()
    return build_adapters(s, RawStore(s.raw_store_dir), fixture_dir)


# ---------------------------------------------------------------- db


@db_app.command("migrate")
def db_migrate() -> None:
    from .db import connection, migrate

    with connection() as conn:
        applied = migrate(conn)
    typer.echo(f"schema applied; migrations: {applied or 'none new'}")


@app.command("seed")
def seed() -> None:
    """Load taxonomy and source policies."""
    from .db import connection
    from .ingest import load_source_policies
    from .taxonomy import load_into_db

    with connection() as conn:
        n = load_into_db(conn)
        p = load_source_policies(conn, yaml.safe_load((DATA_DIR / "source_policies.yaml").read_text())["policies"])
    typer.echo(f"concepts: {n}, policies: {p}")


# ---------------------------------------------------------------- plan and ingest


@app.command("plan")
def plan_cmd(hub_priority: int = typer.Option(1, help="1 = sprint-1 hubs, 2 = next tier, 3 = all"), expand: bool = False, dry_run: bool = False) -> None:
    """S1: build the discovery query matrix."""
    from .db import connection
    from .discovery import planner
    from .hubs import hubs
    from .taxonomy import taxonomy

    tax = taxonomy()
    queries = planner.plan(tax, hub_priority)
    if expand:
        with connection() as conn:
            llm = _llm(conn)
            for hub in hubs(hub_priority):
                queries += planner.expand_with_llm(llm, tax, hub, ["garment.grand_boubou", "garment.taille_basse", "fabric.getzner"])
        queries = planner.dedupe(queries)
    typer.echo(json.dumps(planner.summary(queries)))
    if dry_run:
        for q in queries[:40]:
            typer.echo(f"  p{q.priority} {q.tool:18} {q.query}")
        return
    with connection() as conn:
        n = planner.save(conn, queries)
    typer.echo(f"saved {n} new queries")


@ingest_app.command("discover")
def ingest_discover(limit: int = 50, tools: Optional[str] = None, per_query: int = 50, fixtures: Optional[Path] = None) -> None:
    """Run pending discovery queries and store candidates."""
    from .db import connection
    from .ingest import Ingestor

    adapters = _adapters(fixtures)
    tool_list = [t for t in (tools or "").split(",") if t] or None
    with connection() as conn:
        ing = Ingestor(conn, adapters)
        for q in ing.pending_queries(limit, tool_list):
            n = ing.run_query(q, per_query)
            typer.echo(f"{q.tool:18} {q.query!r}: {n} new candidates")
        typer.echo(json.dumps(ing.stats.__dict__))


@ingest_app.command("prefilter")
def ingest_prefilter(limit: int = 5000) -> None:
    """Cheap rule-out of web results without category vocabulary."""
    from .db import connection
    from .pipeline.relevance import prefilter

    with connection() as conn:
        typer.echo(f"prefiltered out: {prefilter(conn, limit)}")


@ingest_app.command("profiles")
def ingest_profiles(limit: int = 100, platforms: Optional[str] = None, fixtures: Optional[Path] = None, all_candidates: bool = False) -> None:
    """Fetch profiles for candidates and store observations."""
    from .db import connection
    from .ingest import Ingestor

    adapters = _adapters(fixtures)
    plats = [p for p in (platforms or "").split(",") if p] or None
    with connection() as conn:
        ing = Ingestor(conn, adapters, max_posts=get_settings().max_posts_per_profile)
        rows = ing.pending_profiles(limit, only_relevant=None if all_candidates else None, platforms=plats)
        for r in rows:
            if r["relevant"] is False:
                continue
            iid = ing.fetch_and_store_profile(r)
            typer.echo(f"{r['platform']:12} {r['url']}: {'stored' if iid else 'skipped'}")
        typer.echo(json.dumps(ing.stats.__dict__))


# ---------------------------------------------------------------- pipeline stages


@app.command("gate")
def gate_cmd(limit: int = 500, images: bool = True) -> None:
    """S2: relevance gate on fetched profiles."""
    from .db import connection
    from .pipeline.relevance import gate, unjudged_identities

    with connection() as conn:
        unjudged_identities(conn)
        stats = gate(conn, _llm(conn), limit, images)
    typer.echo(json.dumps(stats.__dict__))


@app.command("resolve")
def resolve_cmd(limit: int = 1000, use_llm: bool = True) -> None:
    """S3: attach identities to businesses, merging duplicates."""
    from .db import connection, fetch_all
    from .pipeline.identity import resolve_identity

    with connection() as conn:
        llm = _llm(conn) if use_llm else None
        rows = fetch_all(
            conn,
            """
            select i.id from identities i join candidates c on c.identity_id = i.id
            where c.relevant = true and i.business_id is null limit %s
            """,
            (limit,),
        )
        merged = 0
        for r in rows:
            _, m = resolve_identity(conn, str(r["id"]), llm)
            merged += len(m)
    typer.echo(f"resolved {len(rows)} identities, merged {merged}")


@app.command("enrich")
def enrich_cmd(limit: int = 200, images: bool = True) -> None:
    """S4: profile enrichment."""
    from .db import connection
    from .pipeline.enrich import enrich

    with connection() as conn:
        stats = enrich(conn, _llm(conn), limit, images)
    typer.echo(json.dumps(stats.__dict__))


@app.command("classify")
def classify_cmd(limit: int = 2000, images: bool = True) -> None:
    """S5: post classification."""
    from .db import connection
    from .pipeline.classify import classify

    with connection() as conn:
        stats = classify(conn, _llm(conn), limit, images)
    typer.echo(json.dumps(stats.__dict__))


@app.command("evidence")
def evidence_cmd(limit: int = 500, complaints: bool = False, fixtures: Optional[Path] = None) -> None:
    """S6: evidence collection."""
    from .db import connection
    from .pipeline.evidence import collect

    search_adapter = None
    if complaints:
        adapters = _adapters(fixtures)
        search_adapter = adapters.get("brave") if adapters.get("brave") and adapters["brave"].is_configured() else adapters.get("google_cse")
    with connection() as conn:
        stats = collect(conn, limit, search_adapter)
    typer.echo(json.dumps(stats.__dict__))


@app.command("score")
def score_cmd(limit: int = 5000, narrative: bool = True) -> None:
    """S7: deterministic scoring plus reasons and caveats."""
    from .db import connection, fetch_all
    from .llm.prompts import REASONS_SYSTEM
    from .models import ScoreNarrative
    from .pipeline import score as sc

    with connection() as conn:
        llm = _llm(conn)
        rows = fetch_all(conn, "select id from businesses where status in ('active','dormant') limit %s", (limit,))
        for r in rows:
            f = sc.features_from_db(conn, str(r["id"]))
            s = sc.compute(f)
            reasons, caveats = [], []
            if narrative:
                try:
                    n: ScoreNarrative = llm.structured("reasons", system=REASONS_SYSTEM, user_text="Features: " + json.dumps(f.__dict__, default=str), schema=ScoreNarrative, effort="low", max_tokens=500)
                    reasons, caveats = n.reasons, n.caveats
                except Exception as e:  # noqa: BLE001
                    logging.warning("narrative failed: %s", e)
            sc.persist(conn, str(r["id"]), f, s, reasons, caveats)
    typer.echo(f"scored {len(rows)} businesses")


@app.command("cluster")
def cluster_cmd(min_cluster_size: Optional[int] = None) -> None:
    """S8: embeddings and clustering."""
    from .db import connection, fetch_one
    from .pipeline.cluster import ideal_min_cluster_size, run_clustering

    with connection() as conn:
        n = fetch_one(conn, "select count(*) as c from businesses where status in ('active','candidate') and description is not null")["c"]
        stats = run_clustering(conn, _llm(conn), min_cluster_size or ideal_min_cluster_size(n))
    typer.echo(json.dumps(stats.__dict__))


@app.command("qa")
def qa_cmd(n_random: int = 50, n_risk: int = 50) -> None:
    """S11: two-judge audit sampling."""
    from .db import connection
    from .pipeline.qa import judge, sample

    with connection() as conn:
        ids = sample(conn, n_random, n_risk)
        stats = judge(conn, _llm(conn), ids)
    typer.echo(json.dumps(stats.__dict__))


@app.command("search")
def search_cmd(q: str, near: Optional[str] = None, ships_to: Optional[str] = None, max_usd: Optional[float] = None, limit: int = 10) -> None:
    """Search from the command line."""
    from .db import connection
    from .search.parse import parse_query
    from .search.rank import SearchOptions, search

    with connection() as conn:
        llm = _llm(conn)
        parsed = parse_query(llm, q)
        out = search(conn, parsed, SearchOptions(near=near, ships_to=ships_to, max_usd=max_usd, limit=limit))
    typer.echo("filters: " + ", ".join(out["applied_filters"]))
    for n in out["notes"]:
        typer.echo("note: " + n)
    for r in out["results"]:
        typer.echo(f"{r['rank']:.2f} {r['score']:.2f} {r['geo_fit']:8} {r['business_type']:18} {r['name']} ({r['city'] or '?'}, {r['country'] or '?'})")


@app.command("serve")
def serve(host: str = "0.0.0.0", port: Optional[int] = None) -> None:
    import os

    import uvicorn

    uvicorn.run("bazin.search.api:app", host=host, port=port or int(os.environ.get("PORT", "8000")), reload=False)


@app.command("status")
def status() -> None:
    from .db import connection, fetch_all, fetch_one

    with connection() as conn:
        tables = ["discovery_queries", "candidates", "identities", "businesses", "observations", "media_refs", "observation_concepts", "evidence", "scores", "clusters", "query_log", "llm_calls"]
        for t in tables:
            n = fetch_one(conn, f"select count(*) as c from {t}")["c"]
            typer.echo(f"{t:22} {n}")
        spend = fetch_one(conn, "select coalesce(sum(cost_usd), 0) as s from llm_calls")["s"]
        typer.echo(f"llm spend USD          {float(spend):.4f}")
        for r in fetch_all(conn, "select status, count(*) as c from businesses group by status order by c desc"):
            typer.echo(f"  businesses.{r['status']:16} {r['c']}")


@app.command("run-all")
def run_all(fixtures: Optional[Path] = None, hub_priority: int = 1, limit_queries: Optional[int] = None, images: bool = False) -> None:
    """The whole sprint-1 pipeline in one go (fixtures for offline runs)."""
    db_migrate()
    seed()
    plan_cmd(hub_priority)
    # Fixture runs are free, so run every planned query; live runs default to a cautious batch.
    ingest_discover(limit_queries or (10000 if fixtures else 200), None, 50, fixtures)
    ingest_prefilter()
    ingest_profiles(1000, None, fixtures)
    gate_cmd(2000, images)
    resolve_cmd()
    enrich_cmd(500, images)
    classify_cmd(5000, images)
    evidence_cmd(1000, False, fixtures)
    score_cmd()
    cluster_cmd()
    status()


if __name__ == "__main__":
    app()
