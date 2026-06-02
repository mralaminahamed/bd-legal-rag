"""Application configuration.

Single source of truth for every runtime tunable in the service. Values are
read from the environment (prefix ``BDRAG_``) and an optional ``.env`` file,
validated once on load by Pydantic, and consumed everywhere via
:func:`get_settings`.

No behavioural constant may be hard-coded elsewhere in the codebase (NFR-MN-4);
providers, prompt resolution, chunking, retrieval weights, cache TTLs, the cost
ceiling, and rate-limit windows all originate here.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root .env — four parents up from apps/api/app/config.py in local dev.
# Falls back to ".env" in Docker (shallower path; env vars injected by compose).
try:
    _ENV_FILE: str = str(Path(__file__).parents[3] / ".env")
except IndexError:
    _ENV_FILE = ".env"

ProviderName = Literal["anthropic", "openai", "ollama"]
"""Generation providers the factory can resolve (architecture §2.5)."""

Environment = Literal["development", "staging", "production"]
"""Deployment environment used to gate environment-specific behaviour."""


class Settings(BaseSettings):
    """Validated, environment-driven application settings.

    Every field maps to a configuration key named in ``docs/02-Architecture.md``
    §4.1. Defaults reflect the documented defaults; secrets carry no default and
    must be supplied by the environment. Validation runs on instantiation so a
    misconfigured deployment fails fast at startup rather than at first use.

    Attributes:
        app_name: Human-readable service name surfaced in logs and ``/health``.
        environment: Active deployment environment.
        log_level: Root log level for the structured logger.
        database_dsn: Async SQLAlchemy DSN for PostgreSQL + pgvector.
        redis_dsn: Redis DSN for the response cache, Celery broker, and rate limiter.
        cohere_api_key: Cohere credential for embeddings and mandatory reranking.
        anthropic_api_key: Claude provider credential (optional if unused).
        openai_api_key: OpenAI credential for the OpenAI generation provider.
        ollama_base_url: Base URL of a local Ollama server.
        default_provider: Provider the factory resolves when none is requested.
        anthropic_model: Claude model id used for generation.
        openai_model: OpenAI model id used for generation.
        ollama_model: Ollama model id used for generation.
        ollama_embed_model: Ollama embedding model id (fallback when Cohere absent).
        llm_timeout_seconds: Per-call timeout for generation providers.
        llm_max_retries: Bounded retry count for transient provider failures.
        llm_max_output_tokens: Max completion tokens requested per generation.
        cost_per_1k_input_usd: Input token price for the cost circuit breaker.
        cost_per_1k_output_usd: Output token price for the cost circuit breaker.
        cost_ceiling_usd_per_request: Per-request projected-cost ceiling (FR-GN-5).
        embed_model: Cohere embedding model (embed-multilingual-v3.0) or Ollama fallback.
        embed_dimensions: Embedding vector width (1024 Cohere; 2560 qwen3-embedding:4b).
        embed_batch_size: Maximum texts per Cohere embedding call.
        rerank_model: Cohere reranker model (rerank-multilingual-v3.0, ADR-003).
        bdlaws_base_url: Base URL of the bdlaws statutory portal.
        bdlaws_rate_limit_rps: Maximum requests per second to bdlaws.
        http_timeout_seconds: Per-request timeout for outbound bdlaws HTTP calls.
        http_max_retries: Bounded retry count for transient bdlaws failures.
        http_user_agent: User-Agent sent on all bdlaws ingestion requests.
        chunk_target_tokens: Soft per-chunk token target.
        chunk_max_tokens: Hard per-chunk token cap before a forced split.
        chunk_overlap_tokens: Token overlap carried across paragraph splits.
        rrf_k: Reciprocal Rank Fusion constant (architecture §2.4, default 60).
        retrieval_top_n: Per-list candidate depth before fusion.
        retrieval_top_k: Final number of chunks passed to generation.
        ef_search: HNSW query-time search breadth (recall/latency trade-off).
        vector_weight: Relative weight of the vector list during fusion.
        lexical_weight: Relative weight of the lexical list during fusion.
        similarity_threshold: Minimum cosine similarity for vector-only chunks.
        cross_lingual_floor: RRF top-score floor triggering cross-lingual fallback.
        confidence_t_high: Rerank top-score threshold for HIGH confidence.
        confidence_t_medium: Rerank top-score threshold for MEDIUM confidence.
        confidence_t_keep: Minimum score for a chunk to count toward the tier.
        decline_recall_floor: Minimum retrieval recall before forcing a decline.
        decline_advice_confidence_floor: Minimum classifier confidence to decline.
        decline_gate_enabled: Master switch; when ``False`` the decline gate is
            bypassed entirely (overridden per-intent by the intent router).
        active_disclaimer_version: Version string of the active disclaimer text.
        active_decline_version: Version string of the active decline text.
        response_cache_ttl_seconds: Default TTL for cached answers.
        rate_limit_max_requests: Allowed public requests per window per hashed IP.
        rate_limit_window_seconds: Length of the rate-limit window.
        admin_bearer_token: Bearer token guarding admin endpoints (NFR-SC-2).
        cors_origins: Origins permitted to call the public query API.
    """

    model_config = SettingsConfigDict(
        env_prefix="BDRAG_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Service ---
    app_name: str = "bd-legal-rag"
    environment: Environment = "development"
    log_level: str = "INFO"

    # --- Datastores (architecture §1.1, §4.1) ---
    database_dsn: str = "postgresql+asyncpg://bdrag:bdrag@localhost:5432/bdrag"
    redis_dsn: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))

    # --- Provider credentials and selection (§2.5) ---
    cohere_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"
    default_provider: ProviderName = "anthropic"

    # --- Generation (§2.5) ---
    anthropic_model: str = "claude-sonnet-4-6"
    openai_model: str = "gpt-4o-mini"
    ollama_model: str = "gemma4:e2b"
    ollama_embed_model: str = "qwen3-embedding:4b"
    llm_timeout_seconds: float = Field(default=60.0, gt=0.0)
    llm_max_retries: int = Field(default=3, ge=0)
    llm_max_output_tokens: int = Field(default=2048, ge=1)
    cost_per_1k_input_usd: float = Field(default=0.003, ge=0.0)
    cost_per_1k_output_usd: float = Field(default=0.015, ge=0.0)
    cost_ceiling_usd_per_request: float = Field(default=0.10, gt=0.0)

    # --- Embedding (§2.3, ADR-002) ---
    # Cohere embed-multilingual-v3.0 at 1024 dims with input_type asymmetry.
    # The input_type discriminator (search_document vs search_query) is enforced
    # at the type level in the embedder; this setting names the model only.
    embed_model: str = "embed-multilingual-v3.0"
    embed_dimensions: int = Field(default=2560, ge=1, le=4096)
    embed_batch_size: int = Field(default=96, ge=1, le=96)

    # --- Reranking (§2.4, ADR-003) ---
    # Mandatory stage. When unreachable, degrade to LOW confidence (NFR-RL-2).
    rerank_model: str = "rerank-multilingual-v3.0"
    rerank_top_n: int = Field(default=50, ge=1)

    # --- Ingestion (§2.2, FR-IN-*) ---
    bdlaws_base_url: str = "https://bdlaws.minlaw.gov.bd"
    bdlaws_rate_limit_rps: float = Field(default=1.0, gt=0.0)
    http_timeout_seconds: float = Field(default=30.0, gt=0.0)
    http_max_retries: int = Field(default=4, ge=0)
    http_user_agent: str = "bd-legal-rag/0.1 (+https://github.com/mralaminahamed)"

    # --- Chunking (§2.3) ---
    chunk_target_tokens: int = Field(default=512, ge=1)
    chunk_max_tokens: int = Field(default=768, ge=1)
    chunk_overlap_tokens: int = Field(default=64, ge=0)

    # --- Retrieval (§2.4, ADR-006, ADR-007) ---
    rrf_k: int = Field(default=60, ge=1)
    retrieval_top_n: int = Field(default=40, ge=1)
    retrieval_top_k: int = Field(default=8, ge=1)
    ef_search: int = Field(default=80, ge=1)
    vector_weight: float = Field(default=1.0, ge=0.0)
    lexical_weight: float = Field(default=0.5, ge=0.0)
    similarity_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    cross_lingual_floor: float = Field(default=0.20, ge=0.0, le=1.0)

    # --- Confidence tiering (§2.5) ---
    confidence_t_high: float = Field(default=0.85, ge=0.0, le=1.0)
    confidence_t_medium: float = Field(default=0.60, ge=0.0, le=1.0)
    confidence_t_keep: float = Field(default=0.40, ge=0.0, le=1.0)

    # --- Decline gate (§2.5, NFR-LS-3) ---
    decline_recall_floor: float = Field(default=0.10, ge=0.0, le=1.0)
    decline_advice_confidence_floor: float = Field(default=0.70, ge=0.0, le=1.0)
    decline_gate_enabled: bool = True

    # --- Safety versioning (§2.5, ADR-004) ---
    # These name the active version of the disclaimer and decline text.
    # Changing them is a behavioural change and requires the eval harness to pass.
    active_disclaimer_version: str = "v1"
    active_decline_version: str = "v1"
    active_prompt_version: str = "v2"

    # --- Caching (§2.5) ---
    response_cache_ttl_seconds: int = Field(default=86_400, ge=0)

    # --- HTML snapshot cache (fast re-ingest without re-crawling) ---
    html_snapshot_dir: Path = Field(
        default=Path("data/raw"),
        description="Directory for raw bdlaws HTML snapshots. Relative to repo root.",
    )
    act_structure_cache_ttl: int = Field(default=3600, ge=0)
    provision_cache_ttl: int = Field(default=21_600, ge=0)

    # --- Rate limiting (NFR-SC-2) ---
    rate_limit_max_requests: int = Field(default=20, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    # --- Security ---
    admin_bearer_token: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @model_validator(mode="after")
    def _validate_relationships(self) -> Settings:
        """Enforce cross-field invariants the individual constraints cannot express.

        Returns:
            Settings: The validated instance.

        Raises:
            ValueError: If chunk sizing, retrieval depth, fusion weights, or
                confidence thresholds are internally inconsistent.
        """
        if self.chunk_max_tokens < self.chunk_target_tokens:
            raise ValueError("chunk_max_tokens must be >= chunk_target_tokens")
        if self.chunk_overlap_tokens >= self.chunk_target_tokens:
            raise ValueError("chunk_overlap_tokens must be < chunk_target_tokens")
        if self.retrieval_top_k > self.retrieval_top_n:
            raise ValueError("retrieval_top_k must be <= retrieval_top_n")
        if self.vector_weight == 0.0 and self.lexical_weight == 0.0:
            raise ValueError("at least one of vector_weight or lexical_weight must be > 0")
        if self.confidence_t_medium > self.confidence_t_high:
            raise ValueError("confidence_t_medium must be <= confidence_t_high")
        if self.confidence_t_keep > self.confidence_t_medium:
            raise ValueError("confidence_t_keep must be <= confidence_t_medium")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide, cached settings instance.

    The instance is built once and memoised so configuration is validated a
    single time per process and shared across the API, workers, and Celery beat.

    Returns:
        Settings: The validated settings for this process.
    """
    return Settings()
