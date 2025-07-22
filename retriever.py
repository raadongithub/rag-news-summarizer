import json
import re
from typing import Dict, List, Tuple

import numpy as np
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity


class DensePassageRetriever:

    def __init__(self, openai_api_key: str):

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", openai_api_key=openai_api_key
        )

    def _chunk_content(
        self, content: str, chunk_size: int=50, chunk_overlap: int=10
    ) -> List[str]:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        # Split content into sentences, preserving punctuation
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

        # 1. Chunk the document
        chunks = self._chunk_content(content, chunk_size, chunk_overlap)

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

        # 2. Embed query and passages directly
        query_embedding = np.array(self.embeddings.embed_query(query))
        passage_embeddings = np.array(self.embeddings.embed_documents(chunks))

        # 3. Calculate similarity and find top-k passages
        similarities = cosine_similarity([query_embedding], passage_embeddings)[0]
        top_indices = np.argsort(similarities)[-k:][::-1]

        top_passages = [
            (chunks[idx], float(similarities[idx])) for idx in top_indices
        ]

        # 4. Format and return the final result
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


def main():
    import os

    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Initialize the retriever
    retriever = DensePassageRetriever(openai_api_key)

    # Sample data
    sample_scraped_data = {
        "url": "https://edition.cnn.com/2025/07/21/travel/barcelona-cruise-terminal-closures-scli-intl",
        "title": "Barcelona is shutting two of its cruise-ship terminals to cut tourist numbers",
        "content": "CNN — Barcelona's cruise-ship port is to close two of its terminals, as part of efforts to fight the city's overtourism problem. The closure, which will bring the number of operational terminals down to to five when it takes effect next year, is part of an agreement with Barcelona's city council, announced in a statement from the council Friday. The agreement also provides funding for a study to evaluate how cruise-ship passengers move around the city, which the council says is a first step in developing sustainable mobility plan. That move followed a 2018 agreement between the port authorities and the city council to 'move cruise activity away from urban areas… making them more sustainable,' the port authorities said in a statement at the time.",
        "authors": ["Jack Guy"],
        "publish_date": "2025-07-21T00:00:00",
        "summary": "",
        "source_domain": "edition.cnn.com",
        "word_count": 420,
        "extraction_method": "newspaper3k",
    }

    query = "What is Barcelona doing about overtourism?"

    # Call the main retrieve method with custom chunking parameters
    result = retriever.retrieve(
        sample_scraped_data,
        query,
        k=2,  # Get top 2 results
        chunk_size=2,  # 2 sentences per chunk
        chunk_overlap=1,  # 1 sentence overlap
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()