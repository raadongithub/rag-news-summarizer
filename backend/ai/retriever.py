"""Contextual retrieval orchestration backed by Milvus chunk storage."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from sklearn.metrics.pairwise import cosine_similarity

from .chunking import ArticleChunker
from .embeddings import VoyageEmbeddingService
from .milvus_store import MilvusChunkStore
from .retrieval_config import EmbeddingConfig, RetrievalConfig
from .summary import DEFAULT_ANTHROPIC_MODEL

try:
    from langchain.retrievers.document_compressors import (
        EmbeddingsFilter,
        LLMChainExtractor,
    )
except ModuleNotFoundError:
    from langchain_classic.retrievers.document_compressors import (
        EmbeddingsFilter,
        LLMChainExtractor,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievalCandidate:
    """Intermediate retrieval candidate used before final ranking."""

    document: Document
    contextualized_text: str
    base_similarity: float


class ContextRetriever:
    """Retrieve relevant article chunks using Milvus and contextual compression."""

    def __init__(
        self,
        *,
        voyage_api_key: str,
        anthropic_api_key: Optional[str] = None,
        chunk_store: Optional[MilvusChunkStore] = None,
        embeddings: Optional[VoyageEmbeddingService] = None,
        retrieval_config: Optional[RetrievalConfig] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
    ) -> None:
        self.chunker = ArticleChunker()
        self.embeddings = embeddings or VoyageEmbeddingService(
            api_key=voyage_api_key,
            config=embedding_config,
        )
        self.chunk_store = chunk_store or MilvusChunkStore(self.embeddings)
        self.retrieval_config = retrieval_config or RetrievalConfig.from_env()
        self.extractor = None
        if anthropic_api_key and self.retrieval_config.llm_extraction_enabled:
            self.extractor = LLMChainExtractor.from_llm(
                ChatAnthropic(
                    model=DEFAULT_ANTHROPIC_MODEL,
                    temperature=0.0,
                    api_key=anthropic_api_key,
                )
            )

    def split_to_chunks(
        self,
        content: str,
        chunk_size: int = 5,
        chunk_overlap: int = 3,
    ) -> List[str]:
        """Split article content into overlapping sentence windows."""
        return self.chunker.split_to_chunks(content, chunk_size, chunk_overlap)

    async def ingest_article(
        self,
        article: Dict[str, Any],
        *,
        chunk_size: int,
        chunk_overlap: int,
    ) -> Dict[str, int]:
        """Ensure an article is persisted to Milvus."""
        chunk_records = self.chunker.build_chunk_records(
            article,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not chunk_records:
            return {"inserted": 0, "deleted": 0, "total": 0}
        return await self.chunk_store.upsert_article_chunks(chunk_records)

    async def retrieve_async(
        self,
        scraped_data: Dict[str, Any],
        query: str,
        k: int = 3,
        chunk_size: int = 3,
        chunk_overlap: int = 1,
    ) -> Dict[str, Any]:
        """Retrieve contextualized passages for a user query."""
        article_url = str(scraped_data.get("url", "")).strip()
        title = str(scraped_data.get("title", "")).strip()
        content = str(scraped_data.get("content", "")).strip()
        requested_k = max(1, k)

        if not content:
            return self._empty_response(
                query=query,
                article_url=article_url,
                title=title,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                requested_k=requested_k,
            )

        ingestion_stats = await self.ingest_article(
            scraped_data,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        candidate_k = max(
            requested_k,
            requested_k * self.retrieval_config.candidate_multiplier,
        )
        raw_hits = await self.chunk_store.search_article_chunks(
            article_url=article_url,
            query=query,
            k=candidate_k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not raw_hits:
            return self._empty_response(
                query=query,
                article_url=article_url,
                title=title,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                requested_k=requested_k,
            )

        candidates = await self._build_candidates(
            article_url=article_url,
            raw_hits=raw_hits,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        final_passages = await self._compress_and_rerank(
            query=query,
            candidates=candidates,
            k=requested_k,
        )
        total_chunks = await self.chunk_store.count_article_chunks(
            article_url=article_url,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        metadata = {
            "url": article_url,
            "title": title,
            "total_chunks": total_chunks,
            "retrieval_method": "milvus_contextual_retrieval",
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "requested_k": requested_k,
            "returned_k": len(final_passages),
            "candidate_k": candidate_k,
            "compression_enabled": self.retrieval_config.compression_enabled,
            "llm_extraction_enabled": bool(self.extractor),
            "ingested_chunks": ingestion_stats["total"],
            "inserted_chunks": ingestion_stats["inserted"],
        }
        return {
            "query": query,
            "retrieved_passages": final_passages,
            "metadata": metadata,
        }

    def retrieve(
        self,
        scraped_data: Dict[str, Any],
        query: str,
        k: int = 3,
        chunk_size: int = 3,
        chunk_overlap: int = 1,
    ) -> Dict[str, Any]:
        """Retrieve contextualized passages synchronously."""
        return asyncio.run(
            self.retrieve_async(
                scraped_data=scraped_data,
                query=query,
                k=k,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

    async def _build_candidates(
        self,
        *,
        article_url: str,
        raw_hits: Sequence[Dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[RetrievalCandidate]:
        """Expand Milvus hits with surrounding chunk context."""
        neighbor_indices = set()
        for hit in raw_hits:
            index = int(hit["chunk_index"])
            for delta in range(
                -self.retrieval_config.contextual_window,
                self.retrieval_config.contextual_window + 1,
            ):
                neighbor_index = index + delta
                if neighbor_index >= 0:
                    neighbor_indices.add(neighbor_index)

        neighbor_rows = await self.chunk_store.fetch_chunk_neighbors(
            article_url=article_url,
            neighbor_indices=neighbor_indices,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        neighbors_by_index = {
            int(row["chunk_index"]): row for row in neighbor_rows
        }

        candidates: List[RetrievalCandidate] = []
        for hit in raw_hits:
            chunk_index = int(hit["chunk_index"])
            expanded_parts = []
            for neighbor_index in range(
                chunk_index - self.retrieval_config.contextual_window,
                chunk_index + self.retrieval_config.contextual_window + 1,
            ):
                neighbor = neighbors_by_index.get(neighbor_index)
                if not neighbor:
                    continue
                expanded_parts.append(str(neighbor.get("chunk_text", "")).strip())

            combined_text = "\n".join(part for part in expanded_parts if part).strip()
            if not combined_text:
                combined_text = str(hit.get("chunk_text", "")).strip()

            metadata = dict(hit.get("metadata") or {})
            metadata.update(
                {
                    "chunk_id": hit.get("chunk_id"),
                    "article_url": hit.get("article_url"),
                    "title": hit.get("title"),
                    "chunk_index": chunk_index,
                    "base_similarity_score": float(hit.get("similarity_score", 0.0)),
                }
            )
            candidates.append(
                RetrievalCandidate(
                    document=Document(page_content=combined_text, metadata=metadata),
                    contextualized_text=str(hit.get("contextualized_text", combined_text)),
                    base_similarity=float(hit.get("similarity_score", 0.0)),
                )
            )

        return candidates

    async def _compress_and_rerank(
        self,
        *,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        k: int,
    ) -> List[Dict[str, Any]]:
        """Apply contextual compression and semantic reranking."""
        documents = [candidate.document for candidate in candidates]
        if not documents:
            return []

        if self.retrieval_config.compression_enabled:
            embeddings_filter = EmbeddingsFilter(
                embeddings=self.embeddings,
                similarity_threshold=self.retrieval_config.compression_similarity_threshold,
                k=k,
            )
            documents = await asyncio.to_thread(
                embeddings_filter.compress_documents,
                documents,
                query,
            )

        if self.extractor and documents:
            documents = await asyncio.to_thread(
                self.extractor.compress_documents,
                documents,
                query,
            )

        if not documents:
            return []

        candidates_by_chunk_id = {
            str(candidate.document.metadata.get("chunk_id")): candidate
            for candidate in candidates
        }
        query_vector = np.array(await self.embeddings.aembed_query(query))
        ranking_texts = []
        retained_documents = []
        seen_chunk_ids = set()
        for document in documents:
            chunk_id = str(document.metadata.get("chunk_id", ""))
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)
            source_candidate = candidates_by_chunk_id.get(chunk_id)
            ranking_texts.append(
                source_candidate.contextualized_text
                if source_candidate is not None
                else document.page_content
            )
            retained_documents.append(document)

        if not retained_documents:
            return []

        doc_vectors = await self.embeddings.aembed_documents(ranking_texts)

        reranked_results = []
        for document, doc_vector in zip(
            retained_documents,
            doc_vectors,
            strict=True,
        ):
            semantic_score = float(cosine_similarity([query_vector], [doc_vector])[0][0])

            reranked_results.append(
                {
                    "text": document.page_content,
                    "similarity_score": semantic_score,
                    "metadata": document.metadata,
                    "base_similarity_score": float(
                        document.metadata.get("base_similarity_score", 0.0)
                    ),
                }
            )

        reranked_results.sort(
            key=lambda item: item["similarity_score"],
            reverse=True,
        )
        top_results = reranked_results[:k]
        for rank, item in enumerate(top_results, start=1):
            item["rank"] = rank
        return top_results

    @staticmethod
    def _empty_response(
        *,
        query: str,
        article_url: str,
        title: str,
        chunk_size: int,
        chunk_overlap: int,
        requested_k: int,
    ) -> Dict[str, Any]:
        """Build an empty retrieval response payload."""
        return {
            "query": query,
            "retrieved_passages": [],
            "metadata": {
                "url": article_url,
                "title": title,
                "total_chunks": 0,
                "retrieval_method": "milvus_contextual_retrieval",
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "requested_k": requested_k,
                "returned_k": 0,
                "candidate_k": 0,
                "compression_enabled": False,
                "llm_extraction_enabled": False,
                "ingested_chunks": 0,
                "inserted_chunks": 0,
            },
        }
