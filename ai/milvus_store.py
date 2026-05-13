"""Milvus-backed persistent storage for article chunks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Sequence

from pymilvus import AsyncMilvusClient, DataType, MilvusClient

from .chunking import ChunkRecord
from .embeddings import VoyageEmbeddingService
from .retrieval_config import MilvusConfig

logger = logging.getLogger(__name__)

VECTOR_FIELD = "vector"
PRIMARY_KEY_FIELD = "chunk_id"


class MilvusChunkStore:
    """Persistent chunk storage and search service backed by Milvus.

    Parameters
    ----------
    embeddings : VoyageEmbeddingService
        Shared embedding service used for ingestion and query embedding.
    config : MilvusConfig or None, optional
        Milvus storage configuration.
    """

    def __init__(
        self,
        embeddings: VoyageEmbeddingService,
        config: MilvusConfig | None = None,
    ) -> None:
        self.embeddings = embeddings
        self.config = config or MilvusConfig.from_env()
        self._sync_client = MilvusClient(
            uri=self.config.uri,
            token=self.config.token,
        )
        self._async_client = AsyncMilvusClient(
            uri=self.config.uri,
            token=self.config.token,
        )
        self._collection_ready = False
        self._embedding_dimension: int | None = self.embeddings.config.output_dimension

    async def initialize(self) -> None:
        """Connect to Milvus and ensure the collection is ready.

        Returns
        -------
        None
        """
        if self._collection_ready:
            return
        await self._ensure_collection()
        self._collection_ready = True

    async def close(self) -> None:
        """Close the underlying Milvus connections.

        Returns
        -------
        None
        """
        await self._async_client.close()
        if hasattr(self._sync_client, "close"):
            self._sync_client.close()

    async def upsert_article_chunks(
        self,
        chunk_records: Sequence[ChunkRecord],
    ) -> Dict[str, int]:
        """Insert or update a set of deterministic chunk records.

        Parameters
        ----------
        chunk_records : sequence of ChunkRecord
            Chunk records to persist.

        Returns
        -------
        dict of str to int
            Ingestion statistics including inserted and deleted chunk counts.
        """
        await self.initialize()
        if not chunk_records:
            return {"inserted": 0, "deleted": 0, "total": 0}

        article_url = chunk_records[0].article_url
        chunk_size = int(chunk_records[0].metadata["chunk_size"])
        chunk_overlap = int(chunk_records[0].metadata["chunk_overlap"])
        existing_rows = await self._query_rows(
            filter_=self._article_filter(
                article_url=article_url,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ),
            output_fields=[PRIMARY_KEY_FIELD],
        )
        existing_ids = {str(row[PRIMARY_KEY_FIELD]) for row in existing_rows}
        target_ids = {record.chunk_id for record in chunk_records}

        stale_ids = sorted(existing_ids - target_ids)
        if stale_ids:
            await self._delete_by_ids(stale_ids)

        missing_records = [
            record for record in chunk_records if record.chunk_id not in existing_ids
        ]
        if not missing_records:
            logger.info(
                "Milvus ingestion skipped for %s; %d chunks already present",
                article_url,
                len(chunk_records),
            )
            return {"inserted": 0, "deleted": len(stale_ids), "total": len(chunk_records)}

        vectors = await self.embeddings.aembed_documents(
            [record.contextualized_text for record in missing_records]
        )
        await self._ensure_embedding_dimension(vectors[0])

        payload = [
            {
                PRIMARY_KEY_FIELD: record.chunk_id,
                "article_url": record.article_url,
                "title": record.title,
                "chunk_index": record.chunk_index,
                "chunk_text": record.chunk_text,
                "contextualized_text": record.contextualized_text,
                "chunk_size": int(record.metadata["chunk_size"]),
                "chunk_overlap": int(record.metadata["chunk_overlap"]),
                "embedding_model": self.embeddings.config.model,
                "embedding_dim": len(vector),
                "metadata": record.metadata,
                VECTOR_FIELD: vector,
            }
            for record, vector in zip(missing_records, vectors, strict=True)
        ]

        await self._run_with_retry(
            "upsert_article_chunks",
            self._async_client.upsert,
            collection_name=self.config.collection_name,
            data=payload,
        )
        logger.info(
            "Milvus ingestion complete for %s; inserted=%d deleted=%d total=%d",
            article_url,
            len(missing_records),
            len(stale_ids),
            len(chunk_records),
        )
        return {
            "inserted": len(missing_records),
            "deleted": len(stale_ids),
            "total": len(chunk_records),
        }

    async def search_article_chunks(
        self,
        *,
        article_url: str,
        query: str,
        k: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[Dict[str, Any]]:
        """Search article chunks using a query embedding.

        Parameters
        ----------
        article_url : str
            Source article URL to filter on.
        query : str
            User query.
        k : int
            Maximum number of chunks to return.
        chunk_size : int
            Configured chunk size.
        chunk_overlap : int
            Configured chunk overlap.

        Returns
        -------
        list of dict of str to Any
            Raw Milvus search hits normalized for downstream retrieval logic.
        """
        await self.initialize()
        query_vector = await self.embeddings.aembed_query(query)
        await self._ensure_embedding_dimension(query_vector)

        search_results = await self._run_with_retry(
            "search_article_chunks",
            self._async_client.search,
            collection_name=self.config.collection_name,
            data=[query_vector],
            filter=self._article_filter(
                article_url=article_url,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ),
            limit=k,
            output_fields=[
                PRIMARY_KEY_FIELD,
                "article_url",
                "title",
                "chunk_index",
                "chunk_text",
                "contextualized_text",
                "chunk_size",
                "chunk_overlap",
                "embedding_model",
                "embedding_dim",
                "metadata",
            ],
            search_params={
                "metric_type": self.config.metric_type,
                "params": self.config.search_params,
            },
        )
        return self._normalize_search_results(search_results)

    async def fetch_chunk_neighbors(
        self,
        *,
        article_url: str,
        neighbor_indices: Iterable[int],
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[Dict[str, Any]]:
        """Fetch chunk rows by article and chunk index.

        Parameters
        ----------
        article_url : str
            Source article URL.
        neighbor_indices : iterable of int
            Chunk indices to load.
        chunk_size : int
            Configured chunk size.
        chunk_overlap : int
            Configured chunk overlap.

        Returns
        -------
        list of dict of str to Any
            Matching chunk rows.
        """
        indices = sorted(set(neighbor_indices))
        if not indices:
            return []

        index_clause = ", ".join(str(index) for index in indices)
        filter_ = (
            f"{self._article_filter(article_url=article_url, chunk_size=chunk_size, chunk_overlap=chunk_overlap)} "
            f"and chunk_index in [{index_clause}]"
        )
        return await self._query_rows(
            filter_=filter_,
            output_fields=[
                PRIMARY_KEY_FIELD,
                "article_url",
                "title",
                "chunk_index",
                "chunk_text",
                "contextualized_text",
                "chunk_size",
                "chunk_overlap",
                "embedding_model",
                "embedding_dim",
                "metadata",
            ],
        )

    async def count_article_chunks(
        self,
        *,
        article_url: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> int:
        """Count indexed chunks for a specific article configuration.

        Parameters
        ----------
        article_url : str
            Source article URL.
        chunk_size : int
            Configured chunk size.
        chunk_overlap : int
            Configured chunk overlap.

        Returns
        -------
        int
            Number of matching chunks.
        """
        rows = await self._query_rows(
            filter_=self._article_filter(
                article_url=article_url,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ),
            output_fields=["count(*)"],
        )
        if not rows:
            return 0
        return int(rows[0].get("count(*)", 0))

    async def _ensure_collection(self) -> None:
        """Create and load the Milvus collection when missing.

        Returns
        -------
        None
        """
        collection_exists = await asyncio.to_thread(
            self._sync_client.has_collection,
            self.config.collection_name,
        )
        if collection_exists:
            await self._run_with_retry(
                "load_collection",
                self._async_client.load_collection,
                collection_name=self.config.collection_name,
            )
            return

        if not self.config.auto_create_collection:
            raise RuntimeError(
                f"Milvus collection '{self.config.collection_name}' does not exist"
            )

        if self._embedding_dimension is None:
            probe_vector = await self.embeddings.aembed_query("dimension probe")
            await self._ensure_embedding_dimension(probe_vector)

        if self._embedding_dimension is None:
            raise RuntimeError("Embedding dimension could not be resolved")

        logger.info(
            "Creating Milvus collection %s with dimension=%d index=%s",
            self.config.collection_name,
            self._embedding_dimension,
            self.config.index_type,
        )
        schema = self._sync_client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name=PRIMARY_KEY_FIELD,
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=128,
        )
        schema.add_field(field_name="article_url", datatype=DataType.VARCHAR, max_length=2048)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="chunk_text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(
            field_name="contextualized_text",
            datatype=DataType.VARCHAR,
            max_length=65535,
        )
        schema.add_field(field_name="chunk_size", datatype=DataType.INT64)
        schema.add_field(field_name="chunk_overlap", datatype=DataType.INT64)
        schema.add_field(
            field_name="embedding_model",
            datatype=DataType.VARCHAR,
            max_length=128,
        )
        schema.add_field(field_name="embedding_dim", datatype=DataType.INT64)
        schema.add_field(field_name="metadata", datatype=DataType.JSON)
        schema.add_field(
            field_name=VECTOR_FIELD,
            datatype=DataType.FLOAT_VECTOR,
            dim=self._embedding_dimension,
        )

        await self._run_with_retry(
            "create_collection",
            self._async_client.create_collection,
            collection_name=self.config.collection_name,
            schema=schema,
            consistency_level=self.config.consistency_level,
        )

        index_params = self._sync_client.prepare_index_params()
        index_params.add_index(
            field_name=VECTOR_FIELD,
            index_type=self.config.index_type,
            metric_type=self.config.metric_type,
            params=self.config.index_params,
        )
        await self._run_with_retry(
            "create_index",
            self._async_client.create_index,
            collection_name=self.config.collection_name,
            index_params=index_params,
        )
        await self._run_with_retry(
            "load_collection",
            self._async_client.load_collection,
            collection_name=self.config.collection_name,
        )

    async def _query_rows(
        self,
        *,
        filter_: str,
        output_fields: List[str],
    ) -> List[Dict[str, Any]]:
        """Query rows from Milvus with retry handling.

        Parameters
        ----------
        filter_ : str
            Milvus filter expression.
        output_fields : list of str
            Fields to return.

        Returns
        -------
        list of dict of str to Any
            Query rows.
        """
        rows = await self._run_with_retry(
            "query_rows",
            self._async_client.query,
            collection_name=self.config.collection_name,
            filter=filter_,
            output_fields=output_fields,
        )
        return [dict(row) for row in rows]

    async def _delete_by_ids(self, chunk_ids: Sequence[str]) -> None:
        """Delete chunk rows by primary key.

        Parameters
        ----------
        chunk_ids : sequence of str
            Primary keys to delete.

        Returns
        -------
        None
        """
        if not chunk_ids:
            return
        quoted_ids = ", ".join(self._quote(value) for value in chunk_ids)
        await self._run_with_retry(
            "delete_by_ids",
            self._async_client.delete,
            collection_name=self.config.collection_name,
            filter=f"{PRIMARY_KEY_FIELD} in [{quoted_ids}]",
        )

    async def _ensure_embedding_dimension(self, vector: Sequence[float]) -> None:
        """Record and validate the active embedding dimension.

        Parameters
        ----------
        vector : sequence of float
            Example embedding vector.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            Raised when the runtime embedding dimension changes unexpectedly.
        """
        vector_dimension = len(vector)
        if self._embedding_dimension is None:
            self._embedding_dimension = vector_dimension
            return
        if self._embedding_dimension != vector_dimension:
            raise ValueError(
                "Embedding dimension mismatch. "
                f"Expected {self._embedding_dimension}, received {vector_dimension}."
            )

    async def _run_with_retry(self, operation_name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a Milvus operation with bounded retries.

        Parameters
        ----------
        operation_name : str
            Human-readable operation name used in logs.
        func : Any
            Awaitable Milvus client method.
        *args : Any
            Positional arguments passed to the method.
        **kwargs : Any
            Keyword arguments passed to the method.

        Returns
        -------
        Any
            Operation result.

        Raises
        ------
        Exception
            Re-raises the last operation error after all retries fail.
        """
        last_error: Exception | None = None
        for attempt in range(1, self.config.retry_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - exercised in runtime environments
                last_error = exc
                logger.warning(
                    "Milvus operation %s failed on attempt %d/%d: %s",
                    operation_name,
                    attempt,
                    self.config.retry_attempts,
                    exc,
                )
                if attempt == self.config.retry_attempts:
                    break
                await asyncio.sleep(self.config.retry_backoff_seconds * attempt)

        raise RuntimeError(
            f"Milvus operation '{operation_name}' failed after "
            f"{self.config.retry_attempts} attempts"
        ) from last_error

    @staticmethod
    def _quote(value: str) -> str:
        """Escape a string for use in a Milvus filter expression.

        Parameters
        ----------
        value : str
            Raw string value.

        Returns
        -------
        str
            Quoted and escaped value.
        """
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _article_filter(
        self,
        *,
        article_url: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> str:
        """Build a deterministic Milvus filter for an article chunk set.

        Parameters
        ----------
        article_url : str
            Source article URL.
        chunk_size : int
            Configured chunk size.
        chunk_overlap : int
            Configured chunk overlap.

        Returns
        -------
        str
            Milvus filter expression.
        """
        return (
            f'article_url == {self._quote(article_url)} '
            f"and chunk_size == {chunk_size} "
            f"and chunk_overlap == {chunk_overlap}"
        )

    @staticmethod
    def _normalize_search_results(results: Any) -> List[Dict[str, Any]]:
        """Normalize heterogeneous Milvus search responses.

        Parameters
        ----------
        results : Any
            Raw response returned by `AsyncMilvusClient.search`.

        Returns
        -------
        list of dict of str to Any
            Flat list of normalized hits.
        """
        if not results:
            return []

        first_level = results[0] if isinstance(results, list) else results
        if isinstance(first_level, dict):
            hits = results
        else:
            hits = list(first_level)

        normalized_hits: List[Dict[str, Any]] = []
        for hit in hits:
            entity = dict(hit.get("entity", {})) if isinstance(hit, dict) else dict(hit)
            score = hit.get("distance") if isinstance(hit, dict) else None
            if score is None and isinstance(hit, dict):
                score = hit.get("score")
            entity["similarity_score"] = float(score) if score is not None else 0.0
            normalized_hits.append(entity)
        return normalized_hits
