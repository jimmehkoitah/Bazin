"""S2. Relevance gate: is this a Bazin vendor at all? Runs after the profile is fetched, on bio + captions + thumbnails."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..db import execute, fetch_all, fetch_one, jsonb
from ..llm.client import LLM, BatchItem
from ..llm.prompts import RELEVANCE_SYSTEM
from ..models import RelevanceVerdict
from ..taxonomy import taxonomy

log = logging.getLogger(__name__)


@dataclass
class GateStats:
    prefiltered_out: int = 0
    judged: int = 0
    relevant: int = 0


def profile_text(conn, identity_id: str, max_captions: int = 10) -> tuple[str, list[str]]:
    """Text block for the model plus up to 3 thumbnail URLs."""
    ident = fetch_one(conn, "select * from identities where id = %s", (identity_id,))
    obs = fetch_all(
        conn,
        """
        select o.caption_excerpt, o.hashtags, o.published_at, o.kind,
               (select thumbnail_url from media_refs m where m.observation_id = o.id limit 1) as thumb,
               (select media_url from media_refs m where m.observation_id = o.id limit 1) as media
        from observations o where o.identity_id = %s order by o.published_at desc nulls last limit %s
        """,
        (identity_id, max_captions),
    )
    lines = [
        f"Platform: {ident['platform']}",
        f"Handle: {ident['handle'] or ''}",
        f"Name: {ident['display_name'] or ''}",
        f"Bio: {ident['bio'] or ''}",
        f"Link: {ident['bio_link'] or ''}",
        f"Followers: {ident['followers'] or 'unknown'}",
        "Recent captions:",
    ]
    thumbs: list[str] = []
    for o in obs:
        date = o["published_at"].date().isoformat() if o["published_at"] else "undated"
        tags = " ".join(f"#{h}" for h in (o["hashtags"] or [])[:8])
        lines.append(f"- [{date}] {o['caption_excerpt'] or ''} {tags}".strip())
        t = o["thumb"] or o["media"]
        if t and len(thumbs) < 3:
            thumbs.append(t)
    return "\n".join(lines), thumbs


def prefilter(conn, limit: int = 1000) -> int:
    """Cheap rule before any profile fetch: web results with no category vocabulary anywhere are out."""
    tax = taxonomy()
    rows = fetch_all(
        conn,
        """
        select id, platform, url, handle, title, snippet from candidates
        where relevant is null and identity_id is null and platform in ('website','web','other')
        limit %s
        """,
        (limit,),
    )
    n = 0
    for r in rows:
        text = " ".join(filter(None, [r["title"], r["snippet"], r["handle"], r["url"]]))
        if not tax.match(text):
            execute(
                conn,
                "update candidates set relevant = false, relevance = %s where id = %s",
                (jsonb({"relevant": False, "confidence": 0.7, "reason": "prefilter: no category vocabulary in title, snippet or URL", "stage": "prefilter"}), r["id"]),
            )
            n += 1
    return n


def gate(conn, llm: LLM, limit: int = 500, use_images: bool = True) -> GateStats:
    """Judge every fetched identity whose candidate has no verdict yet."""
    stats = GateStats()
    rows = fetch_all(
        conn,
        """
        select c.id as candidate_id, c.identity_id from candidates c
        where c.identity_id is not null and c.relevant is null
        order by c.created_at limit %s
        """,
        (limit,),
    )
    items: list[BatchItem] = []
    for r in rows:
        text, thumbs = profile_text(conn, str(r["identity_id"]))
        items.append(BatchItem(custom_id=str(r["candidate_id"]), user_text=text, images=thumbs if use_images else []))
    results = llm.run_batch("relevance", items, RelevanceVerdict, system=RELEVANCE_SYSTEM, effort="low", max_tokens=400)
    for cid, res in results.items():
        if isinstance(res, Exception):
            log.warning("relevance failed for %s: %s", cid, res)
            continue
        v: RelevanceVerdict = res
        execute(
            conn,
            "update candidates set relevant = %s, relevance = %s where id = %s",
            (v.relevant, jsonb(v.model_dump() | {"stage": "gate"}), cid),
        )
        stats.judged += 1
        stats.relevant += int(v.relevant)
    return stats


def unjudged_identities(conn, limit: int = 500) -> list[str]:
    """Identities fetched outside the candidate flow (e.g. manual) that still need a verdict via a synthetic candidate."""
    rows = fetch_all(
        conn,
        """
        select i.id, i.platform, i.url, i.handle from identities i
        where not exists (select 1 from candidates c where c.identity_id = i.id) limit %s
        """,
        (limit,),
    )
    ids = []
    for r in rows:
        execute(
            conn,
            "insert into candidates (platform, url, handle, identity_id) values (%s, %s, %s, %s) on conflict (platform, url) do update set identity_id = excluded.identity_id",
            (r["platform"], r["url"], r["handle"], r["id"]),
        )
        ids.append(str(r["id"]))
    return ids
