"""Controlled vocabulary: load, index, match text, and load into Postgres."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from unidecode import unidecode

from .config import DATA_DIR


def normalize(text: str) -> str:
    """Lowercase, strip accents, collapse punctuation to spaces. '#BazinRiche' -> 'bazinriche'."""
    t = unidecode(text or "").lower()
    t = re.sub(r"[^a-z0-9#@'\-\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def hashtag_form(label: str) -> str:
    """'bazin riche' -> 'bazinriche' (what people actually write as a hashtag)."""
    return re.sub(r"[^a-z0-9]", "", normalize(label))


@dataclass
class Label:
    label: str
    language: str
    market: str | None = None
    weight: float = 1.0


@dataclass
class Concept:
    id: str
    kind: str
    canonical_label: str
    parent_id: str | None = None
    notes: str | None = None
    labels: list[Label] = field(default_factory=list)


@dataclass
class Taxonomy:
    concepts: dict[str, Concept]
    relevance_anchors: set[str]
    _phrase_index: dict[str, set[str]] = field(default_factory=dict)  # normalized phrase -> concept ids
    _hashtag_index: dict[str, set[str]] = field(default_factory=dict)  # hashtag form -> concept ids

    def __post_init__(self) -> None:
        for c in self.concepts.values():
            for lab in c.labels:
                n = normalize(lab.label)
                if not n:
                    continue
                self._phrase_index.setdefault(n, set()).add(c.id)
                h = hashtag_form(lab.label)
                if len(h) >= 4:  # avoid matching tiny tokens like 'gp' as hashtags
                    self._hashtag_index.setdefault(h, set()).add(c.id)

    def by_kind(self, kind: str) -> list[Concept]:
        return [c for c in self.concepts.values() if c.kind == kind]

    def ancestors(self, concept_id: str) -> list[str]:
        out: list[str] = []
        cur = self.concepts.get(concept_id)
        while cur and cur.parent_id:
            out.append(cur.parent_id)
            cur = self.concepts.get(cur.parent_id)
        return out

    def match(self, text: str, hashtags: list[str] | None = None) -> Counter[str]:
        """Count concept mentions in free text and hashtags. Longest phrases win over their sub-phrases."""
        counts: Counter[str] = Counter()
        n = f" {normalize(text)} "
        if n.strip():
            # Try longer phrases first so 'bazin riche' is not double-counted as 'bazin'.
            consumed = n
            for phrase in sorted(self._phrase_index, key=len, reverse=True):
                pat = re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")
                hits = len(pat.findall(consumed))
                if hits:
                    for cid in self._phrase_index[phrase]:
                        counts[cid] += hits
                    consumed = pat.sub(" ", consumed)
        for tag in hashtags or []:
            h = hashtag_form(tag.lstrip("#"))
            for cid in self._hashtag_index.get(h, ()):
                counts[cid] += 1
        return counts

    def is_relevant_text(self, text: str, hashtags: list[str] | None = None) -> bool:
        hits = self.match(text, hashtags)
        return any(cid in self.relevance_anchors for cid in hits)

    def labels_for_market(self, concept_id: str, market: str | None, languages: list[str]) -> list[str]:
        """Labels suitable for a market: matching market or any, and matching languages, 'any' or misspellings."""
        c = self.concepts[concept_id]
        out: list[str] = []
        for lab in c.labels:
            if lab.market and market and lab.market != market and lab.market != "diaspora":
                continue
            if lab.language not in ("any", "misspelling") and lab.language not in languages:
                continue
            out.append(lab.label)
        return out


def load_taxonomy(path: Path | None = None) -> Taxonomy:
    path = path or DATA_DIR / "taxonomy.yaml"
    raw = yaml.safe_load(path.read_text())
    concepts: dict[str, Concept] = {}
    for item in raw["concepts"]:
        labels = [
            Label(label=str(l["label"]), language=str(l.get("lang", "any")), market=l.get("market"), weight=float(l.get("weight", 1.0)))
            for l in item.get("labels", [])
        ]
        # The canonical label is also a label.
        if not any(normalize(l.label) == normalize(item["label"]) for l in labels):
            labels.append(Label(label=item["label"], language="any"))
        concepts[item["id"]] = Concept(
            id=item["id"],
            kind=item["kind"],
            canonical_label=item["label"],
            parent_id=item.get("parent"),
            notes=item.get("notes"),
            labels=labels,
        )
    for c in concepts.values():
        if c.parent_id and c.parent_id not in concepts:
            raise ValueError(f"{c.id}: unknown parent {c.parent_id}")
    return Taxonomy(concepts=concepts, relevance_anchors=set(raw.get("relevance_anchor_concepts", [])))


@lru_cache
def taxonomy() -> Taxonomy:
    return load_taxonomy()


def load_into_db(conn, tax: Taxonomy | None = None) -> int:
    """Upsert concepts and labels. Returns number of concepts written."""
    tax = tax or taxonomy()
    with conn.cursor() as cur:
        # Parents first: sort so that a parent is inserted before its children.
        ordered = sorted(tax.concepts.values(), key=lambda c: len(tax.ancestors(c.id)))
        for c in ordered:
            cur.execute(
                """
                insert into concepts (id, kind, parent_id, canonical_label, notes)
                values (%s, %s, %s, %s, %s)
                on conflict (id) do update set kind = excluded.kind, parent_id = excluded.parent_id,
                  canonical_label = excluded.canonical_label, notes = excluded.notes
                """,
                (c.id, c.kind, c.parent_id, c.canonical_label, c.notes),
            )
            cur.execute("delete from concept_labels where concept_id = %s", (c.id,))
            seen: set[tuple[str, str]] = set()
            for lab in c.labels:
                key = (lab.label, lab.language)
                if key in seen:
                    continue
                seen.add(key)
                cur.execute(
                    "insert into concept_labels (concept_id, label, language, market, weight) values (%s, %s, %s, %s, %s)",
                    (c.id, lab.label, lab.language, lab.market, lab.weight),
                )
    return len(tax.concepts)
