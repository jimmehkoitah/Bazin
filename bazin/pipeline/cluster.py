"""S8. Embeddings and clustering: one vector per business, HDBSCAN clusters, model-written labels, stable hues."""

from __future__ import annotations

import hashlib
import logging
import math
import re
import uuid
from dataclasses import dataclass

import numpy as np

from ..config import Settings, get_settings
from ..db import execute, fetch_all, fetch_one
from ..llm.client import LLM
from ..llm.prompts import CLUSTER_LABEL_SYSTEM
from ..models import ClusterLabel
from ..taxonomy import taxonomy

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- embedders


class HashEmbedder:
    """Deterministic bag-of-words embedding (no network). Good enough for tests and as an outage fallback."""

    dim = 256

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for tok in re.findall(r"[a-zà-ÿ0-9.]+", (t or "").lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % self.dim] += 1.0 if (h >> 8) % 2 else -1.0
            n = float(np.linalg.norm(v)) or 1.0
            out.append((v / n).tolist())
        return out


class VoyageEmbedder:
    """Voyage AI multimodal embeddings (text and images in one space)."""

    def __init__(self, settings: Settings):
        import voyageai

        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self.client = voyageai.Client(api_key=settings.voyage_api_key)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            chunk = texts[i : i + 64]
            if self.model.startswith("voyage-multimodal"):
                res = self.client.multimodal_embed(inputs=[[t] for t in chunk], model=self.model, input_type="document")
            else:
                res = self.client.embed(chunk, model=self.model, input_type="document")
            out.extend(res.embeddings)
        return out


def get_embedder(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.fake_llm or not settings.voyage_api_key:
        return HashEmbedder()
    return VoyageEmbedder(settings)


# ---------------------------------------------------------------- business text


def business_doc(conn, business_id: str) -> str:
    b = fetch_one(conn, "select canonical_name, business_type, description, primary_country from businesses where id = %s", (business_id,))
    concepts = fetch_all(conn, "select concept_id, evidence_count from business_concepts where business_id = %s order by evidence_count desc limit 20", (business_id,))
    tax = taxonomy()
    labels = [tax.concepts[c["concept_id"]].canonical_label for c in concepts if c["concept_id"] in tax.concepts]
    locs = fetch_all(conn, "select city, country from locations where business_id = %s and kind <> 'ships_to'", (business_id,))
    where = ", ".join(f"{l['city'] or ''} {l['country'] or ''}".strip() for l in locs)
    return f"{b['canonical_name']}. {b['business_type'].replace('_', ' ')}. {where}. {b['description'] or ''} Concepts: {', '.join(labels)}"


def embed_businesses(conn, embedder=None, limit: int = 5000) -> int:
    embedder = embedder or get_embedder()
    rows = fetch_all(
        conn,
        "select id from businesses where status in ('active','candidate') and description is not null and text_embedding is null limit %s",
        (limit,),
    )
    if not rows:
        return 0
    docs = [business_doc(conn, str(r["id"])) for r in rows]
    vecs = embedder.embed_texts(docs)
    for r, v in zip(rows, vecs):
        execute(conn, "update businesses set text_embedding = %s where id = %s", (list(map(float, v)), r["id"]))
    return len(rows)


# ---------------------------------------------------------------- clustering


@dataclass
class ClusterStats:
    run_id: str = ""
    businesses: int = 0
    clusters: int = 0
    noise: int = 0


def _reduce(X: np.ndarray, dim: int = 64) -> np.ndarray:
    if X.shape[0] <= dim or X.shape[1] <= dim:
        return X
    from sklearn.decomposition import PCA

    return PCA(n_components=min(dim, X.shape[0] - 1), random_state=0).fit_transform(X)


def _cluster(X: np.ndarray, min_cluster_size: int) -> tuple[np.ndarray, np.ndarray]:
    from sklearn.cluster import HDBSCAN

    if X.shape[0] < max(4, min_cluster_size):
        return np.zeros(X.shape[0], dtype=int), np.ones(X.shape[0])
    model = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=max(2, min_cluster_size // 3), copy=True)
    labels = model.fit_predict(X)
    probs = getattr(model, "probabilities_", np.ones(len(labels)))
    if (labels >= 0).sum() == 0:
        return np.zeros(X.shape[0], dtype=int), np.ones(X.shape[0])
    # Noise points join the nearest cluster centroid with low membership.
    centroids = {c: X[labels == c].mean(axis=0) for c in set(labels) if c >= 0}
    for i in np.where(labels < 0)[0]:
        best = min(centroids, key=lambda c: float(np.linalg.norm(X[i] - centroids[c])))
        labels[i] = best
        probs[i] = 0.2
    return labels, probs


def _stable_hues(centroids: dict[int, np.ndarray], previous: list[dict]) -> dict[int, int]:
    """Carry hues from the previous run by centroid similarity; new clusters get the most distant free hue."""
    hues: dict[int, int] = {}
    used: set[int] = set()
    prev = [(np.array(p["centroid"], dtype=np.float32), int(p["hue"])) for p in previous if p.get("centroid") and p.get("hue") is not None]
    for c, vec in centroids.items():
        best, best_sim = None, 0.85
        for pv, ph in prev:
            if pv.shape != vec.shape or ph in used:
                continue
            sim = float(np.dot(pv, vec) / ((np.linalg.norm(pv) * np.linalg.norm(vec)) or 1.0))
            if sim > best_sim:
                best, best_sim = ph, sim
        if best is not None:
            hues[c] = best
            used.add(best)
    n = len(centroids)
    palette = [int(round(i * 360 / max(1, n))) for i in range(n)]
    free = [h for h in palette if all(abs(h - u) > 12 for u in used)]
    for c in centroids:
        if c not in hues:
            hues[c] = free.pop(0) if free else (hash(c) % 360)
            used.add(hues[c])
    return hues


def run_clustering(conn, llm: LLM, min_cluster_size: int = 15, embedder=None) -> ClusterStats:
    embed_businesses(conn, embedder)
    rows = fetch_all(conn, "select id, text_embedding from businesses where status in ('active','candidate') and text_embedding is not null")
    stats = ClusterStats(run_id=f"run-{uuid.uuid4().hex[:8]}", businesses=len(rows))
    if not rows:
        return stats
    X = np.array([r["text_embedding"] for r in rows], dtype=np.float32)
    Xr = _reduce(X)
    labels, probs = _cluster(Xr, min_cluster_size)
    previous = fetch_all(conn, "select centroid, hue from clusters where run_id = (select run_id from clusters order by created_at desc limit 1)")
    centroids = {int(c): Xr[labels == c].mean(axis=0) for c in set(labels.tolist())}
    hues = _stable_hues(centroids, previous)
    tax = taxonomy()
    cluster_ids: dict[int, str] = {}
    for c, vec in centroids.items():
        members = [str(rows[i]["id"]) for i in np.where(labels == c)[0]]
        top = fetch_all(
            conn,
            "select concept_id, sum(evidence_count) as n from business_concepts where business_id = any(%s::uuid[]) group by concept_id order by n desc limit 8",
            (members,),
        )
        samples = fetch_all(conn, "select canonical_name, description, primary_country from businesses where id = any(%s::uuid[]) limit 20", (members,))
        top_ids = [t["concept_id"] for t in top if t["concept_id"] in tax.concepts and not t["concept_id"].startswith("signal.")]
        user_text = (
            "Top concepts: " + ", ".join(f"{cid} ({tax.concepts[cid].canonical_label})" for cid in top_ids) + "\n"
            + "Markets: " + ", ".join(sorted({s["primary_country"] or "?" for s in samples})) + "\n"
            + "Samples:\n" + "\n".join(f"- {s['canonical_name']}: {(s['description'] or '')[:200]}" for s in samples)
        )
        try:
            label: ClusterLabel = llm.structured("cluster_label", system=CLUSTER_LABEL_SYSTEM, user_text=user_text, schema=ClusterLabel, effort="medium", max_tokens=600)
        except Exception as e:  # noqa: BLE001
            log.warning("cluster label failed: %s", e)
            label = ClusterLabel(label=", ".join(tax.concepts[i].canonical_label for i in top_ids[:2]) or "Bazin vendors", description="", primary_concepts=top_ids[:3])
        row = fetch_one(
            conn,
            "insert into clusters (run_id, label, description, hue, centroid, size, primary_concepts) values (%s, %s, %s, %s, %s, %s, %s) returning id",
            (stats.run_id, label.label, label.description, hues[c], [float(x) for x in vec.tolist()], len(members), label.primary_concepts[:6]),
        )
        cluster_ids[c] = str(row["id"])
    for i, r in enumerate(rows):
        execute(
            conn,
            "insert into business_clusters (business_id, cluster_id, run_id, membership_prob) values (%s, %s, %s, %s) on conflict (business_id, run_id) do nothing",
            (r["id"], cluster_ids[int(labels[i])], stats.run_id, float(probs[i])),
        )
    stats.clusters = len(centroids)
    stats.noise = int((probs <= 0.2).sum())
    return stats


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    d = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(np.dot(va, vb) / d) if d else 0.0


def latest_run_id(conn) -> str | None:
    r = fetch_one(conn, "select run_id from clusters order by created_at desc limit 1")
    return r["run_id"] if r else None


def hue_to_css(hue: int) -> str:
    return f"hsl({hue}, 45%, 50%)"


def ideal_min_cluster_size(n: int) -> int:
    return max(3, min(15, int(math.sqrt(n)) if n else 3))
