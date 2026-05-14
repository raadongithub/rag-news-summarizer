"""Embedding services used by ingestion and retrieval."""

from __future__ import annotations

import asyncio
from typing import List

import voyageai
from langchain_core.embeddings import Embeddings

from .retrieval_config import EmbeddingConfig


class VoyageEmbeddingService(Embeddings):
    """Shared Voyage embedding service with async-safe helpers.

    Parameters
    ----------
    api_key : str
        Voyage API key.
    config : EmbeddingConfig or None, optional
        Embedding configuration. Defaults to environment-derived settings.
    """

    def __init__(
        self,
        api_key: str,
        config: EmbeddingConfig | None = None,
    ) -> None:
        self.config = config or EmbeddingConfig.from_env()
        self.client = voyageai.Client(api_key=api_key)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed document texts synchronously.

        Parameters
        ----------
        texts : list of str
            Document texts to embed.

        Returns
        -------
        list of list of float
            Dense document embeddings.
        """
        if not texts:
            return []
        all_embeddings: List[List[float]] = []
        for start_index in range(0, len(texts), self.config.batch_size):
            batch = texts[start_index : start_index + self.config.batch_size]
            response = self.client.embed(
                texts=batch,
                model=self.config.model,
                input_type="document",
                truncation=self.config.truncation,
                output_dimension=self.config.output_dimension,
            )
            all_embeddings.extend(list(vector) for vector in response.embeddings)
        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a query synchronously.

        Parameters
        ----------
        text : str
            Query text to embed.

        Returns
        -------
        list of float
            Dense query embedding.
        """
        response = self.client.embed(
            texts=[text],
            model=self.config.model,
            input_type="query",
            truncation=self.config.truncation,
            output_dimension=self.config.output_dimension,
        )
        return list(response.embeddings[0])

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed document texts without blocking the event loop.

        Parameters
        ----------
        texts : list of str
            Document texts to embed.

        Returns
        -------
        list of list of float
            Dense document embeddings.
        """
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> List[float]:
        """Embed a query without blocking the event loop.

        Parameters
        ----------
        text : str
            Query text to embed.

        Returns
        -------
        list of float
            Dense query embedding.
        """
        return await asyncio.to_thread(self.embed_query, text)
