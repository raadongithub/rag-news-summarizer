import streamlit as st
import logging
import os
import json
from dotenv import load_dotenv

from scraper import NewsArticleScraper
from retriever import ContextRetriever
from summary import SummaryGenerator, SelfCritique, ArticleSummarizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    try:
        openai_api_key = st.secrets["OPENAI_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("OPENAI_API_KEY not found. Please set it in your environment or Streamlit secrets.")
        st.stop()

def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #FFFFFF; }
        [data-testid="stSidebar"] { background-color: #F0F2F6; }
        .summary-box {
            background-color: #FFFFFF;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            border: 1px solid #E5E7EB;
            margin-top: 1rem;
        }
        .critique-box {
            padding: 0.25rem 0.5rem;
            border-radius: 0.375rem;
            border: 1px solid transparent;
            font-weight: 500;
            text-align: center;
        }
        .true-box {
            background-color: #D1FAE5;
            color: #065F46;
            border-color: #6EE7B7;
        }
        .false-box {
            background-color: #FEE2E2;
            color: #991B1B;
            border-color: #FCA5A5;
        }
    </style>
    """, unsafe_allow_html=True)

def initialize_session():
    defaults = {
        "messages": [],
        "scraped_article": None,
        "article_summary": None,
        "current_url": "",
        "article_cache": {}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


#Reset chat when new URL is pasetd
def reset_chat_state():
    st.session_state.messages = []
    st.session_state.article_summary = None

def get_or_scrape_article(url: str):
    """
    Scrapes article from a URL or retrieves it from cache if already scraped
    """
    if url in st.session_state.article_cache:
        logging.info(f"Using cached article for URL: {url}")
        return st.session_state.article_cache[url]

    logging.info(f"Initiated scraping for URL: {url}")
    scraper = NewsArticleScraper()
    scraped_article = scraper.scrape_article(url)
    st.session_state.article_cache[url] = scraped_article
    logging.info("Scraping completed.")
    print(f"\n--- Scraped Article Title ---\n{scraped_article.title}\n")
    return scraped_article

st.set_page_config(page_title="News Summarizer", layout="wide", initial_sidebar_state="auto")
inject_custom_css()
initialize_session()

with st.sidebar:
    st.markdown("## News Summarizer")
    st.markdown("Enter an article URL to load it for querying.")

    url_input = st.text_input("Enter Article URL", placeholder="https://example.com/news/article")

    if st.button("Load Article"):
        if url_input:
            if url_input != st.session_state.current_url:
                reset_chat_state()
                st.session_state.current_url = url_input
                st.session_state.scraped_article = None

            try:
                with st.spinner("Processing article..."):
                    st.session_state.scraped_article = get_or_scrape_article(url_input)
                st.rerun()
            except Exception as e:
                logging.error(f"Pipeline crashed during scraping: {e}")
                st.error(f"An error occurred while loading the article: {e}")
                st.session_state.scraped_article = None
        else:
            st.warning("Please enter a URL.")

    if st.session_state.scraped_article:
        st.markdown("---")
        st.success(f"Article Loaded: **{st.session_state.scraped_article.title}**")
        if st.button("Generate Full Article Summary"):
            try:
                logging.info("Generating full article summary")
                with st.spinner("Generating summary, please wait...."):
                    summarizer = ArticleSummarizer()
                    summary_text = summarizer.generate(st.session_state.scraped_article.content)
                    st.session_state.article_summary = summary_text
                    logging.info("Full article summary generation complete.")
                    print("\n\n\n--- Full Article Summary ---")
                    print(json.dumps({"full_article_summary": summary_text}, indent=2))
                    print("------------------------------\n")
            except Exception as e:
                logging.error(f"Could not generate full article summary. Error: {e}")
                st.error("Failed to generate summary.")

    if st.session_state.article_summary:
        st.markdown(f"""
        <div class="summary-box">
            <h3>Article Summary</h3>
            <p>{st.session_state.article_summary}</p>
        </div>
        """, unsafe_allow_html=True)

st.title("Chat with the Article")

if not st.session_state.scraped_article:
    st.info("Load an article using the sidebar to begin the chat.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "critique" in message and message["critique"]:
            critique = message["critique"]
            cols = st.columns(2)
            
            relevance_class = "true-box" if critique.is_relevant else "false-box"
            cols[0].markdown(f'<div class="{relevance_class}">Relevance: {critique.is_relevant}</div>', unsafe_allow_html=True)

            faithfulness_class = "true-box" if critique.is_faithful else "false-box"
            cols[1].markdown(f'<div class="{faithfulness_class}">Faithfulness: {critique.is_faithful}</div>', unsafe_allow_html=True)
            
            with st.expander("See Details and Retrieved Context"):
                st.markdown(f"**Relevance Justification:** {critique.relevance_explanation}")
                st.markdown(f"**Faithfulness Justification:** {critique.faithfulness_explanation}")
                if "passages" in message and message["passages"]:
                    st.markdown("---")
                    st.markdown("**Passages Used as Context:**")
                    for i, passage in enumerate(message["passages"]):
                        st.info(f"**{i+1}.** {passage['text']} (Score: {passage.get('similarity_score', 'N/A'):.2f})")


if prompt := st.chat_input("Ask a question about the article..."):
    if not st.session_state.scraped_article:
        st.warning("Please load an article using the sidebar first.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        try:
            article_dict = json.loads(st.session_state.scraped_article.model_dump_json())
            
            logging.info(f"Retrieving passages for query: '{prompt}'")
            retriever = ContextRetriever(openai_api_key=openai_api_key)
            retrieval_results = retriever.retrieve(scraped_data=article_dict, query=prompt, k=3)
            passages = retrieval_results.get("retrieved_passages", [])

            if not passages:
                logging.warning("No relevant passages were found for query.")
                answer = "I could not find relevant information in the article to answer your question."
                critique_result = None
            else:
                logging.info("Passage retrieval completed.")
                print("\n\n\n--- Retrieved Passages for Context ---")
                for i, p in enumerate(passages):
                    print(f"{i+1}. {p['text']} (Score: {p.get('similarity_score', 'N/A'):.2f})\n\n")
                print("-" * 40)

                logging.info("Generating initial summary...")
                summary_gen = SummaryGenerator()
                answer = summary_gen.generate(prompt, passages)
                logging.info("Summary generation complete.")
                print(f"\n--- Generated Summary ---\n{answer}\n" + "-" * 27)

                logging.info("Performing critiquw evaluation...")
                critique_gen = SelfCritique(openai_api_key=openai_api_key)
                context_for_critique = "\n---\n".join([p["text"] for p in passages])
                critique_result = critique_gen.evaluate(prompt, context_for_critique, answer)
                logging.info("Critique evaluation complete.")
            
            assistant_message = {
                "role": "assistant",
                "content": answer,
                "critique": critique_result,
                "passages": passages 
            }
            st.session_state.messages.append(assistant_message)
            
            logging.info("Combining results in JSON")
            final_output = {
                "summary": answer, 
                "self_critique": critique_result.model_dump() if critique_result else None,  
                "metadata": {"source_url": st.session_state.current_url, "user_query": prompt}
            }
            print("\n--- Final Output---")
            print(json.dumps(final_output, indent=2))
            print("----------------------------------\n")
            
            st.rerun()

        except Exception as e:
            logging.error(f"Query processing failed due to error: {e}")
            st.error(f"Failed to process your query. Error: {e}")