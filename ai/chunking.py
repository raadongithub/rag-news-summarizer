"""Chunking utilities for article ingestion and contextual retrieval."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class ChunkRecord:
    """Normalized article chunk prepared for storage and retrieval.

    Parameters
    ----------
    chunk_id : str
        Deterministic identifier for the chunk.
    article_url : str
        Source article URL.
    title : str
        Source article title.
    chunk_index : int
        Zero-based chunk position.
    chunk_text : str
        Raw chunk content returned to downstream consumers.
    contextualized_text : str
        Enriched chunk text used for embedding and retrieval.
    metadata : dict of str to Any
        Chunk metadata persisted alongside the vector.
    """

    chunk_id: str
    article_url: str
    title: str
    chunk_index: int
    chunk_text: str
    contextualized_text: str
    metadata: Dict[str, Any]


class ArticleChunker:
    """Split article text into deterministic overlapping chunks."""

    SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")

    def split_to_chunks(
        self,
        content: str,
        chunk_size: int = 5,
        chunk_overlap: int = 3,
    ) -> List[str]:
        """Split article content into overlapping sentence windows.

        Parameters
        ----------
        content : str
            Full article text.
        chunk_size : int, optional
            Number of sentences per chunk.
        chunk_overlap : int, optional
            Number of overlapping sentences between adjacent chunks.

        Returns
        -------
        list of str
            Ordered chunk texts.

        Raises
        ------
        ValueError
            Raised when `chunk_size` is invalid or overlap is too large.
        """
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be zero or greater")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        sentences = self.SENTENCE_SPLIT_PATTERN.split(content.strip())
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        if not sentences:
            return []

        chunks: List[str] = []
        step = chunk_size - chunk_overlap
        for index in range(0, len(sentences), step):
            chunk_text = " ".join(sentences[index : index + chunk_size]).strip()
            if chunk_text:
                chunks.append(chunk_text)
        return chunks

    def build_chunk_records(
        self,
        article: Dict[str, Any],
        *,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[ChunkRecord]:
        """Build storage-ready chunk records for an article.

        Parameters
        ----------
        article : dict of str to Any
            Serialized article payload.
        chunk_size : int
            Number of sentences per chunk.
        chunk_overlap : int
            Number of overlapping sentences between adjacent chunks.

        Returns
        -------
        list of ChunkRecord
            Ordered records containing raw and contextualized chunk text.
        """
        content = str(article.get("content", "")).strip()
        chunks = self.split_to_chunks(
            content=content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not chunks:
            return []

        article_url = str(article.get("url", "")).strip()
        title = str(article.get("title", "")).strip()
        source_domain = str(article.get("source_domain", "")).strip()
        publish_date = article.get("publish_date")
        authors = article.get("authors") or []

        records: List[ChunkRecord] = []
        for chunk_index, chunk_text in enumerate(chunks):
            previous_chunk = chunks[chunk_index - 1] if chunk_index > 0 else ""
            next_chunk = chunks[chunk_index + 1] if chunk_index + 1 < len(chunks) else ""
            contextualized_text = self._build_contextualized_text(
                title=title,
                source_domain=source_domain,
                publish_date=publish_date,
                authors=authors,
                previous_chunk=previous_chunk,
                chunk_text=chunk_text,
                next_chunk=next_chunk,
            )
            metadata = {
                "article_url": article_url,
                "title": title,
                "source_domain": source_domain,
                "publish_date": publish_date,
                "authors": authors,
                "chunk_index": chunk_index,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "total_chunks": len(chunks),
            }
            records.append(
                ChunkRecord(
                    chunk_id=self._build_chunk_id(
                        article_url=article_url,
                        chunk_index=chunk_index,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        chunk_text=chunk_text,
                    ),
                    article_url=article_url,
                    title=title,
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    contextualized_text=contextualized_text,
                    metadata=metadata,
                )
            )
        return records

    @staticmethod
    def _build_contextualized_text(
        *,
        title: str,
        source_domain: str,
        publish_date: Any,
        authors: List[str],
        previous_chunk: str,
        chunk_text: str,
        next_chunk: str,
    ) -> str:
        """Build a retrieval-oriented contextual representation of a chunk.

        Parameters
        ----------
        title : str
            Article title.
        source_domain : str
            Article source domain.
        publish_date : Any
            Article publication timestamp.
        authors : list of str
            Article authors.
        previous_chunk : str
            Neighboring chunk before the current chunk.
        chunk_text : str
            Raw current chunk text.
        next_chunk : str
            Neighboring chunk after the current chunk.

        Returns
        -------
        str
            Enriched text optimized for semantic retrieval.
        """
        header_parts = [part for part in [title, source_domain] if part]
        if publish_date:
            header_parts.append(f"Published: {publish_date}")
        if authors:
            header_parts.append(f"Authors: {', '.join(authors)}")

        sections = []
        if header_parts:
            sections.append(" | ".join(header_parts))
        if previous_chunk:
            sections.append(f"Previous context: {previous_chunk}")
        sections.append(f"Current chunk: {chunk_text}")
        if next_chunk:
            sections.append(f"Next context: {next_chunk}")
        return "\n".join(sections)

    @staticmethod
    def _build_chunk_id(
        *,
        article_url: str,
        chunk_index: int,
        chunk_size: int,
        chunk_overlap: int,
        chunk_text: str,
    ) -> str:
        """Build a deterministic chunk identifier.

        Parameters
        ----------
        article_url : str
            Source article URL.
        chunk_index : int
            Zero-based chunk position.
        chunk_size : int
            Number of sentences per chunk.
        chunk_overlap : int
            Number of overlapping sentences between chunks.
        chunk_text : str
            Raw chunk text.

        Returns
        -------
        str
            Stable SHA-256-based chunk identifier.
        """
        digest = hashlib.sha256(
            "||".join(
                [
                    article_url,
                    str(chunk_index),
                    str(chunk_size),
                    str(chunk_overlap),
                    chunk_text,
                ]
            ).encode("utf-8")
        ).hexdigest()
        return digest
