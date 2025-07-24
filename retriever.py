import json
import re
from typing import Dict, List

import numpy as np
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity


# using Dense Passage Retriever for retrieving relevant data by embedding context/query then implementing Cosine Similarity 
class ContextRetriever:

    def __init__(self, openai_api_key: str):

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", openai_api_key=openai_api_key
        )

    # Dividing content to smaller chunks
    def split_to_chunks(
        self, content: str, chunk_size: int=5, chunk_overlap: int=3
    ) -> List[str]:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        # Split content into sentences, preserving punctuation signs
        sentences = re.split(r"(?<=[.!?])\s+", content.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return []

        chunks = []
        step = chunk_size - chunk_overlap
        for i in range(0, len(sentences), step):
            chunk = " ".join(sentences[i : i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    # Retrieves 3 sentences for each passage
    def retrieve(self,scraped_data:Dict, query:str, k:int=3, chunk_size:int=3, chunk_overlap: int = 1,) -> Dict:
       
        content = scraped_data.get("content", "")

        # Handle cases with no content
        if not content.strip():
            return {
                "query": query,
                "retrieved_passages": [],
                "metadata": {
                    "url": scraped_data.get("url", ""),
                    "title": scraped_data.get("title", ""),
                    "total_chunks": 0,
                    "retrieval_method": "DPR",
                },
            }

        # Chunks the document
        chunks = self.split_to_chunks(content, chunk_size, chunk_overlap)

        if not chunks:
             return {
                "query": query,
                "retrieved_passages": [],
                "metadata": {
                    "url": scraped_data.get("url", ""),
                    "title": scraped_data.get("title", ""),
                    "total_chunks": 0,
                    "retrieval_method": "DPR",
                },
            }

        # Embeds query and passages 
        query_embedding = np.array(self.embeddings.embed_query(query))
        passage_embeddings = np.array(self.embeddings.embed_documents(chunks))

        #Calculate similarity score and find top 3 passages
        similarities = cosine_similarity([query_embedding], passage_embeddings)[0]
        top_indices = np.argsort(similarities)[-k:][::-1]

        top_passages = [
            (chunks[idx], float(similarities[idx])) for idx in top_indices
        ]

        # Formating final result
        return {
            "query": query,
            "retrieved_passages": [
                {"text": passage, "similarity_score": score, "rank": idx + 1}
                for idx, (passage, score) in enumerate(top_passages)
            ],
            "metadata": {
                "url": scraped_data.get("url", ""),
                "title": scraped_data.get("title", ""),
                "total_chunks": len(chunks),
                "retrieval_method": "DPR",
            },
        }

