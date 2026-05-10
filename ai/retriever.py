import re
from typing import Dict, List

import numpy as np
from langchain_voyageai import VoyageAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity


class ContextRetriever:
    """Retrieve the most relevant article chunks for a user query.

    Parameters
    ----------
    voyage_api_key:
        API key used for Voyage embedding requests.
    """

    def __init__(self, voyage_api_key: str):
        self.embeddings = VoyageAIEmbeddings(
            model="voyage-4",
            voyage_api_key=voyage_api_key,
            batch_size=32,
        )

    def split_to_chunks(
        self,
        content: str,
        chunk_size: int = 5,
        chunk_overlap: int = 3,
    ) -> List[str]:
        """Split article content into overlapping sentence windows.

        Parameters
        ----------
        content:
            Full article text.
        chunk_size:
            Number of sentences per chunk.
        chunk_overlap:
            Number of overlapping sentences between adjacent chunks.

        Returns
        -------
        list of str
            Overlapping sentence chunks.

        Raises
        ------
        ValueError
            If ``chunk_overlap`` is greater than or equal to ``chunk_size``.
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        sentences = re.split(r"(?<=[.!?])\s+", content.strip())
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

        if not sentences:
            return []

        chunks = []
        step = chunk_size - chunk_overlap
        for index in range(0, len(sentences), step):
            chunk = " ".join(sentences[index : index + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def retrieve(
        self,
        scraped_data: Dict,
        query: str,
        k: int = 3,
        chunk_size: int = 3,
        chunk_overlap: int = 1,
    ) -> Dict:
        """Embed chunks and return the top-k most similar passages.

        Parameters
        ----------
        scraped_data:
            Serialized article payload containing at least ``content``.
        query:
            User question to match against article chunks.
        k:
            Maximum number of passages to return.
        chunk_size:
            Number of sentences per chunk.
        chunk_overlap:
            Number of overlapping sentences between adjacent chunks.

        Returns
        -------
        dict
            Retrieval payload with ranked passages and metadata.
        """
        content = scraped_data.get("content", "")

        if not content.strip():
            return {
                "query": query,
                "retrieved_passages": [],
                "metadata": {
                    "url": scraped_data.get("url", ""),
                    "title": scraped_data.get("title", ""),
                    "total_chunks": 0,
                    "retrieval_method": "VoyageAIEmbeddings",
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "requested_k": k,
                    "returned_k": 0,
                },
            }

        chunks = self.split_to_chunks(content, chunk_size, chunk_overlap)
        if not chunks:
            return {
                "query": query,
                "retrieved_passages": [],
                "metadata": {
                    "url": scraped_data.get("url", ""),
                    "title": scraped_data.get("title", ""),
                    "total_chunks": 0,
                    "retrieval_method": "VoyageAIEmbeddings",
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "requested_k": k,
                    "returned_k": 0,
                },
            }

        query_embedding = np.array(self.embeddings.embed_query(query))
        passage_embeddings = np.array(self.embeddings.embed_documents(chunks))
        similarities = cosine_similarity([query_embedding], passage_embeddings)[0]
        top_indices = np.argsort(similarities)[-k:][::-1]

        top_passages = [
            (chunks[index], float(similarities[index])) for index in top_indices
        ]

        return {
            "query": query,
            "retrieved_passages": [
                {"text": passage, "similarity_score": score, "rank": index + 1}
                for index, (passage, score) in enumerate(top_passages)
            ],
            "metadata": {
                "url": scraped_data.get("url", ""),
                "title": scraped_data.get("title", ""),
                "total_chunks": len(chunks),
                "retrieval_method": "VoyageAIEmbeddings",
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "requested_k": k,
                "returned_k": len(top_passages),
            },
        }
