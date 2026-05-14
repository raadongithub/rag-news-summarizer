"""CLI entrypoint for the article question-answering pipeline."""

from __future__ import annotations

import json
import logging

from backend.core.config import get_settings
from backend.services import ArticleService, ChatService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SETTINGS = get_settings()
ARTICLE_SERVICE = ArticleService(SETTINGS)
CHAT_SERVICE = ChatService(SETTINGS)

if not SETTINGS.anthropic_api_key:
    logger.error("ANTHROPIC_API_KEY environment variable not found.")
    raise ValueError("ANTHROPIC_API_KEY is required.")
if not SETTINGS.voyage_api_key:
    logger.error("VOYAGE_API_KEY environment variable not found.")
    raise ValueError("VOYAGE_API_KEY is required for retrieval embeddings.")


def run_pipeline(url: str, query: str) -> None:
    """Execute the end-to-end CLI summarization flow.

    Parameters
    ----------
    url : str
        Article URL to scrape.
    query : str
        User question to answer from the article.
    """
    try:
        logger.info("Initiated scraping for URL: %s", url)
        scraped_article = ARTICLE_SERVICE.scrape_article(url)
        scraped_data_dict = json.loads(scraped_article.model_dump_json())
        logger.info("Scraping completed")
        print(f"\n--- Scraped Article Title ---\n{scraped_article.title}\n")
    except Exception as error:
        logger.error("Pipeline crashed during scraping: %s", error)
        return

    try:
        pipeline = CHAT_SERVICE.create_pipeline()
        pipeline_result = pipeline.answer_question(
            article=scraped_data_dict,
            query=query,
            k=SETTINGS.default_top_k,
            chunk_size=SETTINGS.default_chunk_size,
            chunk_overlap=SETTINGS.default_chunk_overlap,
        )
        retrieved_passages = [
            passage.model_dump() for passage in pipeline_result.retrieved_passages
        ]

        if pipeline_result.used_fallback_answer:
            logger.warning("No relevant passages were found for the query.")
            print(f"\n--- Final Output ---\n{pipeline_result.answer}\n")
            return

        logger.info(
            "Passage retrieval completed in %.1fms with %d/%d chunks returned.",
            pipeline_result.retrieval.elapsed_ms,
            pipeline_result.retrieval.returned_k,
            pipeline_result.retrieval.total_chunks,
        )
        print("\n\n\n--- Retrieved Passages for Context ---")
        for index, passage in enumerate(retrieved_passages, start=1):
            print(
                f"{index}. {passage['text']} (Score: {passage['similarity_score']:.2f})"
            )
        print("-" * 40)
    except Exception as error:
        logger.error("Pipeline stopped: failed to retrieve passages. Error: %s", error)
        return

    try:
        generated_summary = pipeline_result.answer
        logger.info("Summary generation complete.")
        print(f"\n\n\n--- Generated Summary ---\n{generated_summary}\n" + "-" * 27)
    except Exception as error:
        logger.error("Pipeline stopped: failed to generate summary. Error: %s", error)
        return

    try:
        logger.info("Performing critique evaluation")
        full_context = "\n---\n".join(
            passage.get("text", "") for passage in retrieved_passages
        )
        critique_output = CHAT_SERVICE.evaluate_answer(
            query=query,
            context=full_context,
            summary=generated_summary,
        )
        logger.info("Self-critique evaluation complete.")
    except Exception as error:
        logger.error("Pipeline stopped due to error: %s", error)
        return

    logger.info("Combining results in JSON")
    final_output = {
        "summary": generated_summary,
        "self_critique": critique_output.model_dump(),
        "metadata": {
            "source_url": url,
            "user_query": query,
            "latency_ms": {
                "total": pipeline_result.total_elapsed_ms,
                "retrieval": pipeline_result.retrieval.elapsed_ms,
                "generation": pipeline_result.generation.elapsed_ms
                if pipeline_result.generation
                else None,
            },
        },
    }

    print("\n\n\n--- Final Output---")
    print(json.dumps(final_output, indent=2, ensure_ascii=False))
    print("----------------------------------\n")


def main() -> None:
    """Run the interactive CLI for the summarization pipeline."""
    while True:
        article_url = input("Please enter the news URL (or type 'exit' to quit): ").strip()
        if article_url.lower() == "exit":
            print("Exiting the program...")
            break

        if not article_url:
            print("URL cannot be empty")
            continue

        print(f"\nURL set to: {article_url}\n")

        while True:
            user_query = input(
                "Ask question about article (type 'new' for new URL, 'exit' to quit): "
            ).strip()

            if user_query.lower() == "exit":
                print("\n\nExiting the program.")
                return

            if user_query.lower() == "new":
                print("\nOverwriting URL...")
                break

            if not user_query:
                print("Query cannot be empty. Please ask a question.")
                continue

            try:
                run_pipeline(article_url, user_query)
            except Exception as error:
                logger.critical(
                    "A critical error occurred in the pipeline execution: %s",
                    error,
                )


if __name__ == "__main__":
    main()
