import os
import json
import logging
from dotenv import load_dotenv


from scraper import NewsArticleScraper
from retriever import ContextRetriever
from summary import SummaryGenerator, SelfCritique, ArticleSummarizer


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logging.error("OPENAI_API_KEY environment variable not found.")
    raise ValueError("OPENAI_API_KEY is required.")

def run_pipeline(url: str, query: str):
    """Executes the full pipeline"""


    # Scraping Article
    try:
        logging.info(f"Initiated scraping for URL: {url}")
        scraper = NewsArticleScraper()
        scraped_article = scraper.scrape_article(url)
        scraped_data_dict = json.loads(scraped_article.model_dump_json())
        logging.info("Scraping completed")
        print(f"\n--- Scraped Article Title ---\n{scraped_article.title}\n")

    except Exception as e:
        logging.error(f" Pipeline crashed:Encountered an Error: {e}")
        return

    '''
    # Generate and print the full article summary first
    try:
        logging.info("Generating full article summary...")
        full_summary_generator = ArticleSummarizer()
        full_summary = full_summary_generator.generate(scraped_article.content)
        
        full_summary_output = {"full_article_summary": full_summary}
        
        logging.info("Full article summary generation complete.")
        print("\n--- Full Article Summary ---")
        print(json.dumps(full_summary_output, indent=2, ensure_ascii=False))
        print("------------------------------\n")

    except Exception as e:
        logging.warning(f"Could not generate full article summary. Error: {e}")'''


    # Retreiving passage
    try:
        logging.info(f" Retreiving passages for query: '{query}'")
        retriever = ContextRetriever (openai_api_key=openai_api_key)
        retrieval_results = retriever.retrieve(scraped_data=scraped_data_dict, query=query, k=3)
        retrieved_passages = retrieval_results.get("retrieved_passages", [])

        if not retrieved_passages:
            logging.warning("No relevant passages were found for the query.")
            print("\n--- Final Output ---\nCould not generate a summary as no relevant text was found.\n")
            return
            
        logging.info("Passage retrieval completed.")
        print("\n\n\n--- Retrieved Passages for Context ---")
        for i, passage in enumerate(retrieved_passages):
            print(f"{i+1}. {passage['text']} (Score: {passage['similarity_score']:.2f})")
        print("-" * 40)
        
    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to retreive passages. Error: {e}")
        return

    #Generating summary
    try:
        logging.info("Generating initial summary...")
        summary_generator = SummaryGenerator()
        generated_summary = summary_generator.generate(query, retrieved_passages)
        logging.info("Summary generation complete.")
        print(f"\n\n\n--- Generated Summary ---\n{generated_summary}\n" + "-" * 27)

    except Exception as e:
        logging.error(f"Pipeline stopped: Failed to generate summary. Error: {e}")
        return

    #Performing critique on generated summary
    try:
        logging.info("Performing critique evaluation")
        full_context = "\n---\n".join([p.get("text", "") for p in retrieved_passages])
        critique_evaluator = SelfCritique(openai_api_key=openai_api_key)
        critique_output = critique_evaluator.evaluate(
            query=query,
            context=full_context,
            summary=generated_summary
        )
        logging.info("Self-critique evaluation complete.")

    except Exception as e:
        logging.error(f"Pipeline stopped due to Error: {e}")
        return
    
    logging.info("Combining results in JSON")
    final_output = {
        "summary": generated_summary, 
        "self_critique": critique_output.model_dump(),  
        "metadata": {"source_url": url,"user_query": query}}

    print("\n\n\n--- Final Output---")
    print(json.dumps(final_output, indent=2, ensure_ascii=False))
    print("----------------------------------\n")

    

def main():
    """
    An interactive CLI to run the news summarization pipeline.
    """
    while True:
        # Prompt user for the initial URL
        article_url = input("Please enter the news URL (or type 'exit' to quit): ").strip()

        if article_url.lower() == 'exit':
            print("Exiting the program...")
            break

        if not article_url:
            print("URL cannot be empty")
            continue

        print(f"\nURL set to: {article_url}\n")

        # Loop for asking questions about the current URL
        while True:
            user_query = input("Ask question about article (type 'new' for new URL, 'exit' to quit): ").strip()

            if user_query.lower() == 'exit':
                print("\n\nExiting the program.")
                return  

            if user_query.lower() == 'new':
                print("\nOverwriting URL...")
                break  # Break the inner loop 

            if not user_query:
                print("Query cannot be empty. Please ask a question.")
                continue

            try:
                # Execute the pipeline 
                run_pipeline(article_url, user_query)
            except Exception as e:
                logging.critical(f"A critical error occurred in the pipeline execution: {e}")

if __name__ == "__main__":
    main()