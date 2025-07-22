import os
import json
import logging
from dotenv import load_dotenv

# Import the necessary components from your project files
from scraper import NewsArticleScraper
from retriever import DensePassageRetriever
# Updated to import the new classes from summary.py
from summary import SummaryGenerator, SelfCritique

# Configure basic logging to see the pipeline's progress
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_pipeline(url: str, query: str):
    """
    Executes the full pipeline: scrape, retrieve, generate, and critique.

    Args:
        url (str): The URL of the article to process.
        query (str): The user query for focused summarization.
    """
    # 1. Load Environment Variables for API Keys
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logging.error("OPENAI_API_KEY environment variable not found. Please create a .env file.")
        raise ValueError("OPENAI_API_KEY is required.")

    # --- Step 1: Scrape the Article ---
    try:
        logging.info(f"Starting scraping for URL: {url}")
        scraper = NewsArticleScraper()
        scraped_article = scraper.scrape_article(url)
        scraped_data_dict = json.loads(scraped_article.model_dump_json())
        logging.info("Scraping completed successfully.")
        print(f"\n--- Scraped Article Title ---\n{scraped_article.title}\n")

    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to scrape the article. Error: {e}")
        return

    # --- Step 2: Retrieve Relevant Passages ---
    try:
        logging.info(f"Retrieving passages for query: '{query}'")
        retriever = DensePassageRetriever(openai_api_key=openai_api_key)
        retrieval_results = retriever.retrieve(scraped_data=scraped_data_dict, query=query, k=3)
        retrieved_passages = retrieval_results.get("retrieved_passages", [])

        if not retrieved_passages:
            logging.warning("No relevant passages were found for the query.")
            print("\n--- Final Output ---\nCould not generate a summary as no relevant text was found.\n")
            return
            
        logging.info("Passage retrieval completed.")
        print("\n--- Retrieved Passages for Context ---")
        for i, passage in enumerate(retrieved_passages):
            print(f"{i+1}. {passage['text']} (Score: {passage['similarity_score']:.2f})")
        print("-" * 36)
        
    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to retrieve passages. Error: {e}")
        return

    # --- Step 3: Generate the Initial Summary ---
    try:
        logging.info("Generating initial summary...")
        summary_generator = SummaryGenerator()
        generated_summary = summary_generator.generate(query, retrieved_passages)
        logging.info("Summary generation complete.")
        print(f"\n--- Generated Summary ---\n{generated_summary}\n" + "-" * 27)

    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to generate summary. Error: {e}")
        return

    # --- Step 4: Perform Self-Critique Evaluation ---
    try:
        logging.info("Performing self-critique evaluation...")
        full_context = "\n---\n".join([p.get("text", "") for p in retrieved_passages])
        critique_evaluator = SelfCritique(openai_api_key=openai_api_key)
        critique_output = critique_evaluator.evaluate(
            query=query,
            context=full_context,
            summary=generated_summary
        )
        logging.info("Self-critique evaluation complete.")

    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to evaluate summary. Error: {e}")
        return
    
    # --- Step 5: Combine and Print Final JSON Output ---
    logging.info("Combining results into final JSON output.")
    final_output = {
        "summary": generated_summary,
        "self_critique": critique_output.model_dump(),  # Convert Pydantic model to dict
        "metadata": {
            "source_url": url,
            "user_query": query
        }
    }

    print("\n--- Final Combined JSON Output ---")
    print(json.dumps(final_output, indent=2))
    print("----------------------------------\n")


def main():
    """
    Main function to define inputs and run the pipeline.
    """
    # Example inputs
    # You can change these to test different articles and queries.
    article_url = "https://www.dawn.com/news/1925419/pak-india-cricket-veteran-match-cancelled-after-indian-players-pull-out-of-game"
    user_query = "Where the tournament is being held?"

    try:
        run_pipeline(article_url, user_query)
    except Exception as e:
        logging.critical(f"A critical error occurred in the main pipeline execution: {e}")

if __name__ == "__main__":
    main()