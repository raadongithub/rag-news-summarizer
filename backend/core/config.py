"""Centralized application configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


def load_environment() -> None:
    """Load environment variables from the repository `.env` file.

    Returns
    -------
    None
        This function mutates process environment variables in place.
    """

    load_dotenv(ENV_FILE, override=False)


@dataclass(frozen=True)
class EmbeddingConfig:
    """Settings for the Voyage embedding service."""

    model: str = "voyage-4"
    output_dimension: int | None = None
    batch_size: int = 32
    truncation: bool = True

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """Build embedding settings from environment variables.

        Returns
        -------
        EmbeddingConfig
            Parsed embedding configuration.
        """

        raw_dim = os.getenv("VOYAGE_EMBEDDING_DIMENSION", "").strip()
        return cls(
            model=os.getenv("VOYAGE_EMBEDDING_MODEL", "voyage-4"),
            output_dimension=int(raw_dim) if raw_dim else None,
            batch_size=int(os.getenv("VOYAGE_EMBEDDING_BATCH_SIZE", "32")),
            truncation=os.getenv("VOYAGE_EMBEDDING_TRUNCATION", "true").lower()
            in {"1", "true", "yes", "on"},
        )


@dataclass(frozen=True)
class MilvusConfig:
    """Settings for Milvus vector storage."""

    uri: str = "http://milvus-standalone:19530"
    token: str | None = None
    collection_name: str = "news_article_chunks"
    consistency_level: str = "Session"
    metric_type: str = "COSINE"
    index_type: str = "HNSW"
    index_params: dict[str, Any] = field(
        default_factory=lambda: {"M": 16, "efConstruction": 200}
    )
    search_params: dict[str, Any] = field(default_factory=lambda: {"ef": 64})
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.5
    auto_create_collection: bool = True

    @classmethod
    def from_env(cls) -> "MilvusConfig":
        """Build Milvus settings from environment variables.

        Returns
        -------
        MilvusConfig
            Parsed Milvus configuration.
        """

        def _json(name: str, default: dict[str, Any]) -> dict[str, Any]:
            raw = os.getenv(name, "").strip()
            return json.loads(raw) if raw else default

        return cls(
            uri=os.getenv("MILVUS_URI", "http://milvus-standalone:19530"),
            token=os.getenv("MILVUS_TOKEN") or None,
            collection_name=os.getenv("MILVUS_COLLECTION_NAME", "news_article_chunks"),
            consistency_level=os.getenv("MILVUS_CONSISTENCY_LEVEL", "Session"),
            metric_type=os.getenv("MILVUS_METRIC_TYPE", "COSINE"),
            index_type=os.getenv("MILVUS_INDEX_TYPE", "HNSW"),
            index_params=_json("MILVUS_INDEX_PARAMS", {"M": 16, "efConstruction": 200}),
            search_params=_json("MILVUS_SEARCH_PARAMS", {"ef": 64}),
            retry_attempts=int(os.getenv("MILVUS_RETRY_ATTEMPTS", "3")),
            retry_backoff_seconds=float(os.getenv("MILVUS_RETRY_BACKOFF_SECONDS", "0.5")),
            auto_create_collection=os.getenv("MILVUS_AUTO_CREATE_COLLECTION", "true").lower()
            in {"1", "true", "yes", "on"},
        )


@dataclass(frozen=True)
class RetrievalConfig:
    """Settings for the RAG retrieval pipeline."""

    default_top_k: int = 3
    candidate_multiplier: int = 4
    contextual_window: int = 1
    compression_enabled: bool = False
    compression_similarity_threshold: float = 0.2
    llm_extraction_enabled: bool = False

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        """Build retrieval settings from environment variables.

        Returns
        -------
        RetrievalConfig
            Parsed retrieval configuration.
        """

        return cls(
            default_top_k=int(os.getenv("RAG_TOP_K", "3")),
            candidate_multiplier=int(os.getenv("RAG_CANDIDATE_MULTIPLIER", "4")),
            contextual_window=int(os.getenv("RAG_CONTEXTUAL_WINDOW", "1")),
            compression_enabled=os.getenv(
                "RAG_CONTEXTUAL_COMPRESSION_ENABLED", "false"
            ).lower() in {"1", "true", "yes", "on"},
            compression_similarity_threshold=float(
                os.getenv("RAG_COMPRESSION_SIMILARITY_THRESHOLD", "0.2")
            ),
            llm_extraction_enabled=os.getenv(
                "RAG_LLM_EXTRACTION_ENABLED", "false"
            ).lower() in {"1", "true", "yes", "on"},
        )


@dataclass(frozen=True)
class AppConfig:
    """Top-level settings shared across the backend application."""

    project_root: Path
    env_file: Path
    app_name: str
    app_version: str
    anthropic_api_key: str | None
    voyage_api_key: str | None
    anthropic_model: str
    answer_temperature: float
    article_summary_temperature: float
    critique_temperature: float
    default_top_k: int
    default_chunk_size: int
    default_chunk_overlap: int
    database_url: str
    cors_origins: tuple[str, ...]
    next_public_api_url: str
    access_token_secret: str
    access_token_expire_minutes: int
    auth_token_issuer: str
    min_password_length: int
    frontend_url: str
    embedding: EmbeddingConfig
    milvus: MilvusConfig
    retrieval: RetrievalConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Build the application configuration from environment variables.

        Returns
        -------
        AppConfig
            Parsed application configuration.
        """

        load_environment()

        raw_origins = os.getenv("CORS_ORIGINS", "").strip()
        cors_origins = (
            tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
            if raw_origins
            else ("http://localhost:3000",)
        )

        return cls(
            project_root=REPO_ROOT,
            env_file=ENV_FILE,
            app_name=os.getenv("APP_NAME", "News Summarizer API"),
            app_version=os.getenv("APP_VERSION", "1.0.0"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            voyage_api_key=os.getenv("VOYAGE_API_KEY") or None,
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            answer_temperature=float(os.getenv("SUMMARY_GENERATION_TEMPERATURE", "0.0")),
            article_summary_temperature=float(os.getenv("ARTICLE_SUMMARY_TEMPERATURE", "0.7")),
            critique_temperature=float(os.getenv("CRITIQUE_TEMPERATURE", "0.0")),
            default_top_k=int(os.getenv("DEFAULT_TOP_K", "3")),
            default_chunk_size=int(os.getenv("DEFAULT_CHUNK_SIZE", "3")),
            default_chunk_overlap=int(os.getenv("DEFAULT_CHUNK_OVERLAP", "1")),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost:5432/news_summarizer",
            ),
            cors_origins=cors_origins,
            next_public_api_url=os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000"),
            access_token_secret=os.getenv(
                "ACCESS_TOKEN_SECRET",
                # Default is long enough to pass the 32-char check in dev.
                # ALWAYS override this in production via .env or environment variable.
                "dev-only-insecure-secret-change-this-in-production-immediately",
            ),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")),
            auth_token_issuer=os.getenv("AUTH_TOKEN_ISSUER", "news-summarizer"),
            min_password_length=int(os.getenv("MIN_PASSWORD_LENGTH", "8")),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
            embedding=EmbeddingConfig.from_env(),
            milvus=MilvusConfig.from_env(),
            retrieval=RetrievalConfig.from_env(),
        )


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    """Return cached application settings.

    Returns
    -------
    AppConfig
        Singleton settings object for the current process.
    """

    return AppConfig.from_env()


load_environment()
