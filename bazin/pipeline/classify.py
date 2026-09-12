"""S5. Post classification: concepts, colours, prices, intent per observation; perceptual hash and palette per thumbnail."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import httpx

from ..db import execute, fetch_all, fetch_one, jsonb
from ..llm.client import LLM, BatchItem
from ..llm.prompts import CLASSIFY_SYSTEM_TEMPLATE, concept_catalogue
from ..models import PostClassification
from ..prices import to_usd
from ..taxonomy import taxonomy

log = logging.getLogger(__name__)

EXTRACTOR_VERSION = "classify-v1"

PALETTE = {
    "white": (245, 245, 240), "black": (20, 20, 20), "grey": (128, 128, 128), "beige": (222, 205, 170),
    "red": (200, 30, 40), "orange": (240, 130, 40), "yellow": (240, 210, 60), "green": (40, 140, 70),
    "turquoise": (40, 180, 180), "blue": (40, 80, 200), "purple": (130, 60, 170), "pink": (235, 120, 170),
    "brown": (120, 75, 40), "gold": (212, 175, 55),
}


@dataclass
class ClassifyStats:
    classified: int = 0
    failed: int = 0
    images: int = 0


def fetch_image(url: str, timeout: float = 15.0) -> bytes | None:
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (bazin-index)"})
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    except Exception as e:  # noqa: BLE001
        log.debug("image fetch failed %s: %s", url, e)
    return None


def image_features(data: bytes) -> tuple[str | None, list[dict], int | None, int | None, bytes | None]:
    """Perceptual hash, dominant colour palette, size, and a small JPEG for the model."""
    try:
        import imagehash
        from PIL import Image
    except ImportError:  # pragma: no cover
        return None, [], None, None, None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None, [], None, None, None
    w, h = img.size
    ph = str(imagehash.phash(img))
    small = img.copy()
    small.thumbnail((64, 64))
    counts: dict[str, int] = {}
    for px in small.getdata():
        name = min(PALETTE, key=lambda n: sum((a - b) ** 2 for a, b in zip(px, PALETTE[n])))
        counts[name] = counts.get(name, 0) + 1
    total = sum(counts.values()) or 1
    colors = [{"name": n, "share": round(c / total, 3)} for n, c in sorted(counts.items(), key=lambda kv: -kv[1])[:4] if c / total >= 0.08]
    model_img = img.copy()
    model_img.thumbnail((768, 768))
    buf = io.BytesIO()
    model_img.save(buf, format="JPEG", quality=80)
    return ph, colors, w, h, buf.getvalue()


def pending_observations(conn, limit: int = 2000, business_only: bool = True) -> list[dict]:
    return fetch_all(
        conn,
        """
        select o.id, o.business_id, o.caption_excerpt, o.hashtags, o.platform, o.kind,
               (select m.id from media_refs m where m.observation_id = o.id order by m.id limit 1) as media_id,
               (select coalesce(m.thumbnail_url, m.media_url) from media_refs m where m.observation_id = o.id order by m.id limit 1) as thumb
        from observations o
        where o.kind in ('post','reel','video','listing')
          and (not %s or o.business_id is not null)
          and not exists (select 1 from observation_concepts oc where oc.observation_id = o.id and oc.extractor_version = %s)
          and o.published_at > now() - interval '24 months'
        order by o.published_at desc nulls last limit %s
        """,
        (business_only, EXTRACTOR_VERSION, limit),
    )


def persist(conn, obs: dict, c: PostClassification) -> None:
    tax = taxonomy()
    for hit in c.concept_ids:
        if hit.id in tax.concepts:
            execute(
                conn,
                "insert into observation_concepts (observation_id, concept_id, confidence, extractor_version) values (%s, %s, %s, %s) on conflict (observation_id, concept_id) do update set confidence = excluded.confidence, extractor_version = excluded.extractor_version",
                (obs["id"], hit.id, hit.confidence, EXTRACTOR_VERSION),
            )
    for occ in c.occasion_ids:
        if occ in tax.concepts:
            execute(
                conn,
                "insert into observation_concepts (observation_id, concept_id, confidence, extractor_version) values (%s, %s, 0.7, %s) on conflict do nothing",
                (obs["id"], occ, EXTRACTOR_VERSION),
            )
    for col in c.colors:
        cid = f"color.{col.name}"
        if cid in tax.concepts:
            execute(
                conn,
                "insert into observation_concepts (observation_id, concept_id, confidence, extractor_version) values (%s, %s, %s, %s) on conflict do nothing",
                (obs["id"], cid, min(1.0, 0.4 + col.share), EXTRACTOR_VERSION),
            )
    # A sentinel row so re-runs skip this observation even when nothing matched.
    execute(
        conn,
        "insert into observation_concepts (observation_id, concept_id, confidence, extractor_version) select %s, 'fabric.bazin', 0.0, %s where not exists (select 1 from observation_concepts where observation_id = %s)",
        (obs["id"], EXTRACTOR_VERSION, obs["id"]),
    )
    execute(conn, "update observations set language = coalesce(language, nullif(%s, 'unknown')) where id = %s", (c.language, obs["id"]))
    if obs.get("media_id") is not None:
        execute(conn, "update media_refs set visual_tags = %s where id = %s", ([h.id for h in c.concept_ids][:12], obs["media_id"]))
    bid = obs.get("business_id")
    if bid and c.shows_price and c.shows_price.amount > 0:
        unit = c.shows_price.unit if c.shows_price.unit in ("metre", "yard", "piece", "3m", "4m", "5m", "5yd", "10yd", "outfit", "item", "kg") else "unknown"
        ptype = "fabric" if c.is_fabric_only or unit in ("metre", "yard", "piece", "3m", "4m", "5m", "5yd", "10yd") else "complete_outfit" if c.is_finished_garment else "other"
        execute(
            conn,
            "insert into prices (business_id, observation_id, price_type, currency, amount_min, amount_max, unit, usd_equivalent, evidence) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (bid, obs["id"], ptype, c.shows_price.currency.upper()[:3], c.shows_price.amount, c.shows_price.amount, unit, to_usd(c.shows_price.amount, c.shows_price.currency), (obs["caption_excerpt"] or "")[:200]),
        )
    if bid:
        for flag, kind in (("is_finished_garment", "finished_garment"), ("is_fitting_or_customer", "tagged_customer_post"), ("is_embroidery_closeup", "embroidery_closeup")):
            if getattr(c, flag):
                execute(
                    conn,
                    "insert into evidence (business_id, kind, polarity, observation_id, extracted_claim, confidence, collected_by) select %s, %s, 1, %s, %s, 0.7, 'classify' where not exists (select 1 from evidence where observation_id = %s and kind = %s)",
                    (bid, kind, obs["id"], (obs["caption_excerpt"] or kind)[:300], obs["id"], kind),
                )


def persist_image(conn, obs: dict, phash: str | None, colors: list[dict], w: int | None, h: int | None) -> None:
    if obs.get("media_id") is None:
        return
    execute(
        conn,
        "update media_refs set phash = coalesce(%s, phash), dominant_colors = coalesce(%s, dominant_colors), width = coalesce(%s, width), height = coalesce(%s, height) where id = %s",
        (phash, jsonb(colors) if colors else None, w, h, obs["media_id"]),
    )
    if phash and obs.get("business_id"):
        # The same image on another business's account undermines maker credibility for both.
        dupes = fetch_all(
            conn,
            """
            select distinct o.business_id from media_refs m join observations o on o.id = m.observation_id
            where m.phash = %s and o.business_id is not null and o.business_id <> %s
            """,
            (phash, obs["business_id"]),
        )
        for d in dupes:
            for a, b in ((obs["business_id"], d["business_id"]), (d["business_id"], obs["business_id"])):
                execute(
                    conn,
                    "insert into evidence (business_id, kind, polarity, extracted_claim, confidence, collected_by) select %s, 'duplicate_image', -1, %s, 0.8, 'classify' where not exists (select 1 from evidence where business_id = %s and kind = 'duplicate_image' and extracted_claim = %s)",
                    (a, f"image {phash} also posted by business {b}", a, f"image {phash} also posted by business {b}"),
                )


def classify(conn, llm: LLM, limit: int = 2000, use_images: bool = True, image_fetcher=fetch_image) -> ClassifyStats:
    stats = ClassifyStats()
    rows = pending_observations(conn, limit)
    if not rows:
        return stats
    system = CLASSIFY_SYSTEM_TEMPLATE.format(catalogue=concept_catalogue(taxonomy(), ("fabric", "garment", "technique", "occasion", "style")))
    items: list[BatchItem] = []
    by_id = {str(r["id"]): r for r in rows}
    for r in rows:
        tags = " ".join(f"#{h}" for h in (r["hashtags"] or [])[:15])
        text = f"Platform: {r['platform']} ({r['kind']})\nCaption: {r['caption_excerpt'] or ''}\nHashtags: {tags}"
        images: list[bytes | str] = []
        if use_images and r["thumb"]:
            data = image_fetcher(r["thumb"])
            if data:
                ph, colors, w, h, small = image_features(data)
                persist_image(conn, r, ph, colors, w, h)
                if small:
                    images.append(small)
                    stats.images += 1
        items.append(BatchItem(custom_id=str(r["id"]), user_text=text, images=images))
    results = llm.run_batch("classify", items, PostClassification, system=system, effort="low", max_tokens=800)
    for oid, res in results.items():
        if isinstance(res, Exception):
            log.warning("classify failed for %s: %s", oid, res)
            stats.failed += 1
            continue
        persist(conn, by_id[oid], res)
        stats.classified += 1
    return stats
