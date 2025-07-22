import os
import json
import logging
from dotenv import load_dotenv

# Import the necessary components from your project files
from scraper import NewsArticleScraper
from retriever import DensePassageRetriever
from summary import generate_summary # Assuming the new function is in 'summary.py'

# Configure basic logging to see the pipeline's progress
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_pipeline(url: str, query: str):
    """
    Executes the full pipeline: scrape, retrieve, and summarize.

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
        
        # Convert Pydantic model to dictionary for the retriever
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
        
        # Retrieve the top 3 most relevant passages
        retrieval_results = retriever.retrieve(
            scraped_data=scraped_data_dict,
            query=query,
            k=3 
        )
        
        retrieved_passages = retrieval_results.get("retrieved_passages", [])
        if not retrieved_passages:
            logging.warning("No relevant passages were found for the query.")
            print("\n--- Final Summary ---\nCould not generate a summary as no relevant text was found for the query.\n")
            return
            
        logging.info("Passage retrieval completed.")
        print("\n--- Retrieved Passages for Context ---")
        for i, passage in enumerate(retrieved_passages):
            print(f"{i+1}. {passage['text']} (Score: {passage['similarity_score']:.2f})")
        print("-" * 35)
        
    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to retrieve passages. Error: {e}")
        return

    # --- Step 3: Generate the Final Summary ---
    try:
        logging.info("Generating final query-focused summary...")
        final_summary = generate_summary(
            query=query,
            retrieved_passages=retrieved_passages
        )
        logging.info("Summary generation completed.")

        # 4. Print the final answer
        print("\n--- Final Summary ---")
        print(final_summary)
        print("-" * 23 + "\n")

    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to generate summary. Error: {e}")
        return


def main():
    """
    Main function to define inputs and run the pipeline.
    """
    # Inputs as specified in the request
    article_url = "https://edition.cnn.com/2025/07/21/travel/barcelona-cruise-terminal-closures-scli-intl"
    user_query = "In which year Barcelona closed its northern port terminal?"

    try:
        run_pipeline(article_url, user_query)
    except Exception as e:
        logging.critical(f"A critical error occurred in the pipeline: {e}")

if __name__ == "__main__":
    main()