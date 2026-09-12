"""FastAPI app: search, business detail, static pages, takedown form, query log."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import connection, execute, fetch_all, fetch_one, jsonb
from ..llm.client import get_llm
from ..pipeline.cluster import get_embedder
from .parse import parse_query
from .rank import SearchOptions, search

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Bazin discovery engine", version="0.1.0")
_llm = None
_embedder = None


def llm():
    global _llm
    if _llm is None:
        _llm = get_llm(get_settings())
    return _llm


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = get_embedder(get_settings())
    return _embedder


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/privacy")
def privacy() -> FileResponse:
    return FileResponse(STATIC / "privacy.html")


@app.get("/takedown")
def takedown_page() -> FileResponse:
    return FileResponse(STATIC / "takedown.html")


@app.get("/health")
def health() -> dict[str, Any]:
    with connection() as conn:
        n = fetch_one(conn, "select count(*) as c from businesses where status in ('active','dormant')")
    return {"ok": True, "businesses": n["c"]}


@app.get("/search")
def search_endpoint(
    request: Request,
    q: str = Query(default="", max_length=300),
    near: str | None = None,
    radius_km: float | None = Query(default=None, ge=1, le=500),
    ships_to: str | None = Query(default=None, max_length=2),
    type: str | None = None,
    max_usd: float | None = Query(default=None, ge=1),
    limit: int = Query(default=40, ge=1, le=100),
) -> JSONResponse:
    q = q.strip()
    parsed = parse_query(llm(), q) if q else parse_query(llm(), "bazin")
    query_vec = None
    try:
        query_vec = embedder().embed_texts([parsed.free_text or q])[0]
    except Exception as e:  # noqa: BLE001
        log.debug("query embedding failed: %s", e)
    opts = SearchOptions(
        near=near or None, radius_km=radius_km, ships_to=ships_to or None,
        business_types=[t for t in (type or "").split(",") if t and t != "any"], max_usd=max_usd, limit=limit,
    )
    with connection() as conn:
        out = search(conn, parsed, opts, query_vec)
        session = hashlib.sha256((request.client.host if request.client else "?").encode()).hexdigest()[:16]
        execute(
            conn,
            "insert into query_log (raw_query, parsed, user_region, result_count, session_hash) values (%s, %s, %s, %s, %s)",
            (q or "(empty)", jsonb(out["parsed"]), near or ships_to, len(out["results"]), session),
        )
    out["query"] = q
    return JSONResponse(out)


@app.get("/business/{business_id}")
def business(business_id: str) -> dict[str, Any]:
    with connection() as conn:
        b = fetch_one(conn, "select id, canonical_name, business_type, description, primary_country, quality_score, status, last_observed_active_at from businesses where id = %s and objection_at is null", (business_id,))
        if not b:
            raise HTTPException(404, "not found")
        return {
            "business": {k: (str(v) if k == "id" else v) for k, v in b.items()},
            "identities": fetch_all(conn, "select platform, url, handle, followers from identities where business_id = %s", (business_id,)),
            "locations": fetch_all(conn, "select kind, country, city, address from locations where business_id = %s", (business_id,)),
            "contact": fetch_all(conn, "select kind, value from contact_channels where business_id = %s and not do_not_contact", (business_id,)),
            "prices": fetch_all(conn, "select price_type, currency, amount_min, amount_max, unit, usd_equivalent, observed_at from prices where business_id = %s order by observed_at desc limit 20", (business_id,)),
            "evidence": fetch_all(conn, "select kind, polarity, extracted_claim, source_url, observed_at from evidence where business_id = %s order by observed_at desc limit 50", (business_id,)),
            "observations": fetch_all(conn, "select platform, kind, source_url, caption_excerpt, published_at from observations where business_id = %s order by published_at desc nulls last limit 30", (business_id,)),
            "score": fetch_one(conn, "select * from scores where business_id = %s order by computed_at desc limit 1", (business_id,)),
        }


class TakedownIn(BaseModel):
    requester: str = Field(max_length=200)
    business_name: str | None = Field(default=None, max_length=200)
    source_url: str = Field(max_length=500)
    reason: str = Field(max_length=200)
    details: str | None = Field(default=None, max_length=2000)


@app.post("/takedown")
def takedown(body: TakedownIn) -> dict[str, Any]:
    with connection() as conn:
        match = fetch_one(conn, "select business_id from identities where url = %s or url = %s limit 1", (body.source_url.rstrip("/"), body.source_url.rstrip("/") + "/"))
        bid = match["business_id"] if match else None
        execute(
            conn,
            "insert into takedown_requests (business_id, requester, reason, source_url) values (%s, %s, %s, %s)",
            (bid, body.requester[:200], f"{body.reason}: {body.details or ''}"[:2000], body.source_url),
        )
        if bid and body.reason.lower().startswith("i am the owner and want the listing removed"):
            # Objection takes effect immediately; a human confirms ownership before deletion.
            execute(conn, "update businesses set objection_at = now(), updated_at = now() where id = %s", (bid,))
    return {"received": True}


@app.post("/click")
def click(business_id: str, query_log_id: int | None = None) -> dict[str, Any]:
    with connection() as conn:
        if query_log_id:
            execute(conn, "update query_log set clicked_business_ids = array_append(coalesce(clicked_business_ids, '{}'), %s::uuid) where id = %s", (business_id, query_log_id))
    return {"ok": True}
