"""S11. QA sampler: two independent judgements per sampled record; disagreements go to the audit queue."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from ..db import execute, fetch_all, fetch_one, jsonb
from ..llm.client import LLM
from ..llm.prompts import JUDGE_A_SYSTEM, JUDGE_B_SYSTEM
from ..models import JudgeVerdict

log = logging.getLogger(__name__)


@dataclass
class QAStats:
    sampled: int = 0
    queued: int = 0
    accepted: int = 0


def record_for(conn, business_id: str) -> dict:
    b = fetch_one(conn, "select id, canonical_name, business_type, business_type_confidence, description, primary_country, quality_score, status from businesses where id = %s", (business_id,))
    return {
        "business": {k: (str(v) if k == "id" else v) for k, v in b.items()},
        "score": b["quality_score"],
        "identities": fetch_all(conn, "select platform, url, handle, bio from identities where business_id = %s", (business_id,)),
        "locations": fetch_all(conn, "select kind, country, city, address, confidence from locations where business_id = %s", (business_id,)),
        "contact_channels": fetch_all(conn, "select kind, value from contact_channels where business_id = %s", (business_id,)),
        "prices": fetch_all(conn, "select price_type, currency, amount_min, unit, evidence from prices where business_id = %s limit 8", (business_id,)),
        "evidence": fetch_all(conn, "select kind, polarity, extracted_claim, source_url from evidence where business_id = %s limit 20", (business_id,)),
        "evidence_count": (fetch_one(conn, "select count(*) as c from evidence where business_id = %s", (business_id,)) or {}).get("c", 0),
        "captions": [r["caption_excerpt"] for r in fetch_all(conn, "select caption_excerpt from observations where business_id = %s and caption_excerpt is not null order by published_at desc nulls last limit 8", (business_id,))],
    }


def sample(conn, n_random: int = 50, n_risk: int = 50) -> list[str]:
    rnd = fetch_all(conn, "select id from businesses where status = 'active' order by random() limit %s", (n_random,))
    risk = fetch_all(
        conn,
        """
        select b.id from businesses b
        left join (select business_id, count(*) as ev from evidence group by business_id) e on e.business_id = b.id
        where b.status = 'active' and (
            (b.quality_score >= 0.6 and coalesce(e.ev, 0) < 3)
            or exists (select 1 from identities i where i.business_id = b.id and i.match_confidence is not null and i.match_confidence < 0.9)
            or exists (select 1 from prices p where p.business_id = b.id and p.usd_equivalent > 5000)
        )
        order by b.updated_at desc limit %s
        """,
        (n_risk,),
    )
    ids = [str(r["id"]) for r in rnd] + [str(r["id"]) for r in risk]
    return list(dict.fromkeys(ids))


def judge(conn, llm: LLM, business_ids: list[str]) -> QAStats:
    stats = QAStats()
    for bid in business_ids:
        rec = record_for(conn, bid)
        text = "Record:\n" + json.dumps(rec, default=str, ensure_ascii=False)
        try:
            a: JudgeVerdict = llm.structured("judge_a", system=JUDGE_A_SYSTEM, user_text=text, schema=JudgeVerdict, effort="low", max_tokens=600)
            b: JudgeVerdict = llm.structured("judge_b", system=JUDGE_B_SYSTEM, user_text=text, schema=JudgeVerdict, effort="medium", max_tokens=600)
        except Exception as e:  # noqa: BLE001
            log.warning("judge failed for %s: %s", bid, e)
            continue
        stats.sampled += 1
        agreed = a.overall == b.overall
        if agreed and a.overall == "accept":
            stats.accepted += 1
            continue
        reason = "disagreement" if not agreed else f"both say {a.overall}"
        execute(
            conn,
            "insert into audit_queue (business_id, reason, judge_a, judge_b, agreed) values (%s, %s, %s, %s, %s)",
            (bid, reason, jsonb(a.model_dump()), jsonb(b.model_dump()), agreed),
        )
        stats.queued += 1
        if agreed and a.overall == "reject":
            execute(conn, "update businesses set status = 'suspected_scam' where id = %s and status = 'active' and %s", (bid, any("scam" in i.lower() for i in a.issues + b.issues)))
    return stats
