"""Source adapter interface.

Every adapter turns a discovery query into candidates, and (where the platform has profiles)
turns a candidate into a ProfileBundle of observations. Adapters never store anything; the
ingest module does. Adapters must work in two modes:

- live: real HTTP calls using credentials from Settings;
- fixture: `fixture_dir` set, in which case the adapter reads recorded JSON payloads from
  `fixture_dir/<adapter_name>/<slug>.json` and never touches the network. Tests use this mode,
  and so does this sandbox, where the vendor APIs are unreachable.

Raw payloads are handed to `RawStore.put()` which returns a `raw_ref` string; adapters put the
reference on every observation they emit so the database never holds full captions or media.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..config import Settings
from ..models import Candidate, ProfileBundle


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:80] or "q"


def excerpt(text: str | None, limit: int = 300) -> str | None:
    """Trim a caption to the stored excerpt length, at a word boundary."""
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= limit:
        return t
    cut = t[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"


HASHTAG_RE = re.compile(r"#([\wÀ-ɏ]+)")
MENTION_RE = re.compile(r"@([\w.]+)")


def hashtags_in(text: str | None) -> list[str]:
    return [h.lower() for h in HASHTAG_RE.findall(text or "")]


def mentions_in(text: str | None) -> list[str]:
    return [m.lower().rstrip(".") for m in MENTION_RE.findall(text or "")]


class RawStore:
    """Where full payloads live. Dev: JSON files under settings.raw_store_dir. Production can swap in a bucket."""

    def __init__(self, root: Path):
        self.root = root

    def put(self, adapter: str, key: str, payload: Any) -> str:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
        path = self.root / adapter / f"{slugify(key)}-{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(json.dumps(payload, ensure_ascii=False, default=str))
        return f"file:{path.relative_to(self.root)}"


@dataclass
class DiscoveryQuery:
    id: str | None
    query: str
    platform: str
    tool: str
    market: str | None = None
    language: str | None = None
    priority: int = 5


class SourceAdapter(ABC):
    """Base class. Subclasses set `name` (matches discovery_queries.tool) and `platform`."""

    name: str = "base"
    platform: str = "other"
    acquisition_method: str = "third_party_scraper"

    def __init__(self, settings: Settings, raw_store: RawStore, fixture_dir: Path | None = None):
        self.settings = settings
        self.raw = raw_store
        self.fixture_dir = fixture_dir

    # ------------------------------------------------------------ fixture helpers

    def _fixture_path(self, slug: str) -> Path:
        assert self.fixture_dir is not None
        return self.fixture_dir / self.name / f"{slugify(slug)}.json"

    def load_fixture(self, slug: str) -> Any | None:
        if self.fixture_dir is None:
            return None
        p = self._fixture_path(slug)
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def has_fixture(self, slug: str) -> bool:
        return self.fixture_dir is not None and self._fixture_path(slug).exists()

    # ------------------------------------------------------------ interface

    @abstractmethod
    def discover(self, query: DiscoveryQuery, limit: int = 50) -> list[Candidate]:
        """Run one discovery query and return candidates (profiles, pages, listings or posts)."""

    def fetch_profile(self, candidate: Candidate, max_posts: int = 30) -> ProfileBundle | None:
        """Return the profile and recent content for a candidate, or None when the platform has no profiles."""
        return None

    def supports_profiles(self) -> bool:
        return type(self).fetch_profile is not SourceAdapter.fetch_profile

    def is_configured(self) -> bool:
        """True when credentials for live mode are present or a fixture dir is set."""
        return self.fixture_dir is not None


def dedupe_candidates(cands: Iterable[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, str]] = set()
    out: list[Candidate] = []
    for c in cands:
        key = (c.platform, c.url.rstrip("/").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out
