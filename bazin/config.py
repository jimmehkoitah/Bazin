"""Settings, loaded from the environment (and a local .env file when present)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_DIR = REPO_ROOT / "db"

# Model routing per stage. Opus where judgement matters, Haiku for high-volume classification.
# Override any entry with BAZIN_MODEL_<STAGE>=... in the environment.
DEFAULT_MODELS: dict[str, str] = {
    "relevance": "claude-haiku-4-5",        # S2: cheap gate, thousands of calls
    "identity": "claude-sonnet-5",          # S3: tie-breaks only
    "enrich": "claude-opus-5",              # S4: extraction quality drives everything downstream
    "classify": "claude-haiku-4-5",         # S5: tens of thousands of posts, vision included
    "cluster_label": "claude-opus-5",       # S8: a few dozen calls, needs taste
    "query_parse": "claude-sonnet-5",       # S9: latency-sensitive, moderate difficulty
    "reasons": "claude-haiku-4-5",          # S7: reasons and caveats from a feature snapshot
    "judge_a": "claude-sonnet-5",           # S11: first judge
    "judge_b": "claude-opus-5",             # S11: second judge, different prompt
    "query_expand": "claude-sonnet-5",      # S1: colloquial phrasings
}

# USD per million tokens (input, output). Batch API halves these.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BAZIN_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = Field(
        default="postgresql://postgres@127.0.0.1:54329/bazin_test",
        description="psycopg connection string",
    )

    # Third-party credentials. All optional so that the offline parts run without them.
    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None
    apify_token: str | None = None
    brave_api_key: str | None = None
    google_cse_key: str | None = None
    google_cse_cx: str | None = None
    youtube_api_key: str | None = None
    etsy_api_key: str | None = None
    yelp_api_key: str | None = None

    # LLM behaviour
    fake_llm: bool = Field(default=False, description="Use the deterministic fake LLM (tests, dry runs)")
    llm_budget_usd: float = Field(default=400.0, description="Hard stop for cumulative LLM spend")
    use_batches: bool = Field(default=True, description="Route bulk stages through the Message Batches API")
    model_relevance: str | None = None
    model_identity: str | None = None
    model_enrich: str | None = None
    model_classify: str | None = None
    model_cluster_label: str | None = None
    model_query_parse: str | None = None
    model_reasons: str | None = None
    model_judge_a: str | None = None
    model_judge_b: str | None = None
    model_query_expand: str | None = None

    # Embeddings
    embedding_model: str = "voyage-multimodal-3"
    embedding_dim: int = 1024

    # Crawl behaviour
    max_posts_per_profile: int = 30
    max_thumbnails_per_profile: int = 5
    raw_store_dir: Path = Field(default=REPO_ROOT / ".raw", description="Local raw payload store (dev)")

    def model_for(self, stage: str) -> str:
        override = getattr(self, f"model_{stage}", None)
        return override or DEFAULT_MODELS[stage]


@lru_cache
def get_settings() -> Settings:
    return Settings()
