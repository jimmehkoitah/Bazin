import os
from pathlib import Path

import pytest

os.environ.setdefault("BAZIN_FAKE_LLM", "true")
os.environ.setdefault("BAZIN_DATABASE_URL", "postgresql://postgres@127.0.0.1:54329/bazin_test")

FIXTURES = Path(__file__).parent / "fixtures"


def _db_available() -> bool:
    try:
        import psycopg

        with psycopg.connect(os.environ["BAZIN_DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="session")
def db():
    """Fresh schema in the test database (all tables truncated) for the session."""
    if not _db_available():
        pytest.skip("test database not reachable")
    from bazin.db import close_pool, connection, migrate

    with connection() as conn:
        migrate(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                truncate candidates, discovery_queries, identities, businesses, observations, media_refs, observation_concepts,
                  business_concepts, offers, prices, evidence, scores, clusters, business_clusters, search_terms, query_log,
                  claims, takedown_requests, llm_calls, audit_queue, ingest_runs restart identity cascade
                """
            )
    yield
    close_pool()


@pytest.fixture
def conn(db):
    from bazin.db import connection

    with connection() as c:
        yield c
