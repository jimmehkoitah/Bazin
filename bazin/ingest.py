"""Ingestion: run discovery queries, store candidates, fetch profiles, store observations and media.

Everything here is idempotent: candidates are keyed by (platform, url), observations by
(platform, source_url), media by (observation_id, media_url). Re-running a query only adds what is new.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .db import execute, fetch_all, fetch_one, jsonb
from .discovery.planner import mark
from .models import Candidate, ProfileBundle
from .sources.base import DiscoveryQuery, SourceAdapter, dedupe_candidates
from .sources.urls import is_profile_url, resolve_platform

log = logging.getLogger(__name__)


@dataclass
class IngestStats:
    queries: int = 0
    candidates_new: int = 0
    profiles_fetched: int = 0
    observations_new: int = 0
    media_new: int = 0
    errors: int = 0


class Ingestor:
    def __init__(self, conn, adapters: dict[str, SourceAdapter], max_posts: int = 30):
        self.conn = conn
        self.adapters = adapters
        self.max_posts = max_posts
        self._policy_cache: dict[tuple[str, str], int | None] = {}
        self.stats = IngestStats()

    # ------------------------------------------------------------ discovery

    def pending_queries(self, limit: int = 100, tools: list[str] | None = None) -> list[DiscoveryQuery]:
        rows = fetch_all(
            self.conn,
            """
            select id, query, platform, tool, market, language, priority from discovery_queries
            where status = 'pending' and (%s::text[] is null or tool = any(%s::text[]))
            order by priority, created_at limit %s
            """,
            (tools, tools, limit),
        )
        return [DiscoveryQuery(str(r["id"]), r["query"], r["platform"], r["tool"], r["market"], r["language"], r["priority"]) for r in rows]

    def run_query(self, q: DiscoveryQuery, limit: int = 50) -> int:
        adapter = self.adapters.get(q.tool)
        if adapter is None or not adapter.is_configured():
            if q.id:
                mark(self.conn, q.id, "skipped", 0)
            return 0
        if q.id:
            mark(self.conn, q.id, "running")
        try:
            cands = dedupe_candidates(adapter.discover(q, limit=limit))
        except Exception as e:  # noqa: BLE001 - a failing source must not stop the run
            log.warning("query %r on %s failed: %s", q.query, q.tool, e)
            self.stats.errors += 1
            if q.id:
                mark(self.conn, q.id, "failed", 0)
            return 0
        n = 0
        for c in cands:
            if self.store_candidate(c, q.id):
                n += 1
        if q.id:
            mark(self.conn, q.id, "done", len(cands))
        self.stats.queries += 1
        self.stats.candidates_new += n
        return n

    def store_candidate(self, c: Candidate, query_id: str | None = None) -> bool:
        """Insert a candidate; returns True when it was new."""
        platform, url, handle = c.platform, c.url, c.handle
        if platform in ("web", "website"):
            platform, url, handle = resolve_platform(c.url)
            handle = handle or c.handle
        row = fetch_one(
            self.conn,
            """
            insert into candidates (discovery_query_id, platform, url, handle, external_id, title, snippet, thumbnail_url, source_json)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (platform, url) do update set
              title = coalesce(candidates.title, excluded.title),
              snippet = coalesce(candidates.snippet, excluded.snippet),
              thumbnail_url = coalesce(candidates.thumbnail_url, excluded.thumbnail_url)
            returning (xmax = 0) as inserted
            """,
            (query_id, platform, url, handle, c.external_id, c.title, (c.snippet or "")[:300] or None, c.thumbnail_url, jsonb(c.source_json)),
        )
        return bool(row and row["inserted"])

    # ------------------------------------------------------------ profiles

    def pending_profiles(self, limit: int = 100, only_relevant: bool | None = True, platforms: list[str] | None = None) -> list[dict]:
        return fetch_all(
            self.conn,
            """
            select * from candidates
            where identity_id is null
              and (%s::boolean is null or relevant = %s)
              and (%s::text[] is null or platform::text = any(%s::text[]))
            order by created_at limit %s
            """,
            (only_relevant, only_relevant, platforms, platforms, limit),
        )

    def adapter_for_platform(self, platform: str) -> SourceAdapter | None:
        for a in self.adapters.values():
            if a.platform == platform and a.supports_profiles() and a.is_configured():
                return a
        return None

    def fetch_and_store_profile(self, cand: dict) -> str | None:
        """Fetch the profile behind a candidate row and store it. Returns the identity id."""
        platform = cand["platform"]
        url = cand["url"]
        if not is_profile_url(platform, url):
            # A single post: derive the profile URL when we can, otherwise store the post as an observation later.
            platform, url, handle = resolve_platform(url)
            if not is_profile_url(platform, url):
                return None
        adapter = self.adapter_for_platform(platform)
        if adapter is None:
            return None
        c = Candidate(platform=platform, url=url, handle=cand.get("handle"), external_id=cand.get("external_id"), title=cand.get("title"))
        try:
            bundle = adapter.fetch_profile(c, max_posts=self.max_posts)
        except Exception as e:  # noqa: BLE001
            log.warning("profile fetch failed for %s: %s", url, e)
            self.stats.errors += 1
            return None
        if bundle is None:
            return None
        identity_id = self.store_bundle(bundle)
        execute(self.conn, "update candidates set identity_id = %s where id = %s", (identity_id, cand["id"]))
        self.stats.profiles_fetched += 1
        return identity_id

    def store_bundle(self, b: ProfileBundle) -> str:
        row = fetch_one(
            self.conn,
            """
            insert into identities (platform, handle, url, external_id, display_name, bio, bio_link, followers, last_crawled_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (platform, url) do update set
              handle = coalesce(excluded.handle, identities.handle),
              external_id = coalesce(excluded.external_id, identities.external_id),
              display_name = coalesce(excluded.display_name, identities.display_name),
              bio = coalesce(excluded.bio, identities.bio),
              bio_link = coalesce(excluded.bio_link, identities.bio_link),
              followers = coalesce(excluded.followers, identities.followers),
              last_crawled_at = now()
            returning id, business_id
            """,
            (b.platform, b.handle, b.url, b.external_id, b.display_name, (b.bio or "")[:600] or None, b.bio_link, b.followers),
        )
        identity_id = str(row["id"])
        business_id = row["business_id"]
        latest: datetime | None = None
        for o in b.observations:
            policy_id = self.policy_id(o.platform, o.acquisition_method)
            content_hash = hashlib.sha1(f"{o.caption_excerpt}|{o.published_at}".encode()).hexdigest()
            orow = fetch_one(
                self.conn,
                """
                insert into observations (identity_id, business_id, platform, source_url, external_id, kind, published_at,
                                          caption_excerpt, hashtags, mentions, language, engagement, raw_ref,
                                          acquisition_method, source_policy_id, extractor_version, content_hash)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (platform, source_url) do update set
                  engagement = coalesce(excluded.engagement, observations.engagement),
                  identity_id = coalesce(observations.identity_id, excluded.identity_id)
                returning id, (xmax = 0) as inserted
                """,
                (
                    identity_id, business_id, o.platform, o.source_url, o.external_id, o.kind, o.published_at,
                    o.caption_excerpt, o.hashtags, o.mentions, o.language, jsonb(o.engagement) if o.engagement else None,
                    o.raw_ref or b.raw_ref, o.acquisition_method, policy_id, "ingest-v1", content_hash,
                ),
            )
            if orow["inserted"]:
                self.stats.observations_new += 1
            if o.published_at and (latest is None or o.published_at > latest):
                latest = o.published_at
            for m in o.media:
                mrow = fetch_one(
                    self.conn,
                    """
                    insert into media_refs (observation_id, media_url, thumbnail_url, oembed_url, width, height)
                    values (%s, %s, %s, %s, %s, %s)
                    on conflict (observation_id, media_url) do nothing
                    returning id
                    """,
                    (orow["id"], m.media_url, m.thumbnail_url, m.oembed_url, m.width, m.height),
                )
                if mrow:
                    self.stats.media_new += 1
        if business_id and latest:
            execute(
                self.conn,
                "update businesses set last_observed_active_at = greatest(coalesce(last_observed_active_at, %s), %s) where id = %s",
                (latest, latest, business_id),
            )
        return identity_id

    def policy_id(self, platform: str, method: str) -> int | None:
        key = (platform, method)
        if key not in self._policy_cache:
            row = fetch_one(self.conn, "select id from source_policies where platform = %s and method = %s", key)
            self._policy_cache[key] = row["id"] if row else None
        return self._policy_cache[key]


def load_source_policies(conn, policies: list[dict]) -> int:
    n = 0
    for p in policies:
        execute(
            conn,
            """
            insert into source_policies (platform, method, terms_status, retention_days, store_media, notes)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (platform, method) do update set terms_status = excluded.terms_status,
              retention_days = excluded.retention_days, store_media = excluded.store_media, notes = excluded.notes
            """,
            (p["platform"], p["method"], p["terms_status"], p.get("retention_days"), bool(p.get("store_media", False)), p.get("notes")),
        )
        n += 1
    return n


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
