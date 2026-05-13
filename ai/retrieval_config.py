"""Configuration models for chunking, embeddings, retrieval, and Milvus."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def _read_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : bool
        Value returned when the variable is unset.

    Returns
    -------
    bool
        Parsed boolean value.
    """
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    """Read an integer environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : int
        Value returned when the variable is unset.

    Returns
    -------
    int
        Parsed integer value.
    """
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    return int(raw_value)


def _read_float(name: str, default: float) -> float:
    """Read a floating-point environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : float
        Value returned when the variable is unset.

    Returns
    -------
    float
        Parsed floating-point value.
    """
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    return float(raw_value)


def _read_json_dict(name: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """Read a JSON object environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : dict of str to Any
        Value returned when the variable is unset.

    Returns
    -------
    dict of str to Any
        Parsed JSON object.

    Raises
    ------
    ValueError
        Raised when the variable does not contain a JSON object.
    """
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return dict(default)

    parsed = json.loads(raw_value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must be a JSON object")
    return parsed


@dataclass(frozen=True)
class EmbeddingConfig:
    """Runtime configuration for the embedding service.

    Parameters
    ----------
    model : str
        Voyage embedding model name.
    output_dimension : int or None
        Optional output dimension override.
    batch_size : int
        Maximum number of texts to embed per provider request.
    truncation : bool
        Whether the provider may truncate overly long inputs.
    """

    model: str = "voyage-4"
    output_dimension: Optional[int] = None
    batch_size: int = 32
    truncation: bool = True

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """Build an embedding configuration from environment variables.

        Returns
        -------
        EmbeddingConfig
            Parsed embedding configuration.
        """
        raw_dimension = os.getenv("VOYAGE_EMBEDDING_DIMENSION", "").strip()
        return cls(
            model=os.getenv("VOYAGE_EMBEDDING_MODEL", "voyage-4"),
            output_dimension=int(raw_dimension) if raw_dimension else None,
            batch_size=_read_int("VOYAGE_EMBEDDING_BATCH_SIZE", 32),
            truncation=_read_bool("VOYAGE_EMBEDDING_TRUNCATION", True),
        )


@dataclass(frozen=True)
class MilvusConfig:
    """Runtime configuration for Milvus storage and search.

    Parameters
    ----------
    uri : str
        Milvus server URI.
    token : str or None
        Optional authentication token.
    collection_name : str
        Target collection for article chunks.
    consistency_level : str
        Milvus consistency level used for reads and writes.
    metric_type : str
        Vector similarity metric.
    index_type : str
        Index algorithm used for the dense vector field.
    index_params : dict of str to Any
        Extra index construction parameters.
    search_params : dict of str to Any
        Extra search-time parameters.
    retry_attempts : int
        Retry attempts for Milvus operations.
    retry_backoff_seconds : float
        Base backoff used between retries.
    auto_create_collection : bool
        Whether collection creation is allowed on startup.
    """

    uri: str = "http://milvus-standalone:19530"
    token: Optional[str] = None
    collection_name: str = "news_article_chunks"
    consistency_level: str = "Session"
    metric_type: str = "COSINE"
    index_type: str = "HNSW"
    index_params: Dict[str, Any] = field(
        default_factory=lambda: {"M": 16, "efConstruction": 200}
    )
    search_params: Dict[str, Any] = field(default_factory=lambda: {"ef": 64})
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.5
    auto_create_collection: bool = True

    @classmethod
    def from_env(cls) -> "MilvusConfig":
        """Build a Milvus configuration from environment variables.

        Returns
        -------
        MilvusConfig
            Parsed Milvus configuration.
        """
        return cls(
            uri=os.getenv("MILVUS_URI", "http://milvus-standalone:19530"),
            token=os.getenv("MILVUS_TOKEN") or None,
            collection_name=os.getenv("MILVUS_COLLECTION_NAME", "news_article_chunks"),
            consistency_level=os.getenv("MILVUS_CONSISTENCY_LEVEL", "Session"),
            metric_type=os.getenv("MILVUS_METRIC_TYPE", "COSINE"),
            index_type=os.getenv("MILVUS_INDEX_TYPE", "HNSW"),
            index_params=_read_json_dict(
                "MILVUS_INDEX_PARAMS",
                {"M": 16, "efConstruction": 200},
            ),
            search_params=_read_json_dict(
                "MILVUS_SEARCH_PARAMS",
                {"ef": 64},
            ),
            retry_attempts=_read_int("MILVUS_RETRY_ATTEMPTS", 3),
            retry_backoff_seconds=_read_float("MILVUS_RETRY_BACKOFF_SECONDS", 0.5),
            auto_create_collection=_read_bool("MILVUS_AUTO_CREATE_COLLECTION", True),
        )


@dataclass(frozen=True)
class RetrievalConfig:
    """Runtime configuration for contextual retrieval orchestration.

    Parameters
    ----------
    default_top_k : int
        Default number of final passages returned to callers.
    candidate_multiplier : int
        Factor used to expand the Milvus candidate pool before compression.
    contextual_window : int
        Number of neighboring chunks to attach on each side of a candidate.
    compression_enabled : bool
        Whether contextual compression should run after vector search.
    compression_similarity_threshold : float
        Minimum semantic similarity retained by the embeddings filter.
    llm_extraction_enabled : bool
        Whether LLM-based contextual extraction should run after filtering.
    """

    default_top_k: int = 3
    candidate_multiplier: int = 4
    contextual_window: int = 1
    compression_enabled: bool = True
    compression_similarity_threshold: float = 0.2
    llm_extraction_enabled: bool = False

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        """Build a retrieval configuration from environment variables.

        Returns
        -------
        RetrievalConfig
            Parsed retrieval configuration.
        """
        return cls(
            default_top_k=_read_int("RAG_TOP_K", 3),
            candidate_multiplier=_read_int("RAG_CANDIDATE_MULTIPLIER", 4),
            contextual_window=_read_int("RAG_CONTEXTUAL_WINDOW", 1),
            compression_enabled=_read_bool("RAG_CONTEXTUAL_COMPRESSION_ENABLED", True),
            compression_similarity_threshold=_read_float(
                "RAG_COMPRESSION_SIMILARITY_THRESHOLD",
                0.2,
            ),
            llm_extraction_enabled=_read_bool("RAG_LLM_EXTRACTION_ENABLED", False),
        )
