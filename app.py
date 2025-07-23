import streamlit as st
import logging
import os
import json
from dotenv import load_dotenv

from scraper import NewsArticleScraper
from retriever import ContextRetriever
from summary import SummaryGenerator, SelfCritique, ArticleSummarizer, Critique

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
        .stApp {
            background-color: #FFFFFF;
        }
        [data-testid="stSidebar"] {
            background-color: #F0F2F6;
        }
        .summary-box {
            background-color: #FFFFFF;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            border: 1px solid #E5E7EB;
            margin-top: 1rem;
        }
        .summary-box h3 {
            font-size: 1.25rem;
            color: #111827;
            margin-bottom: 0.5rem;
        }
        .summary-box p {
            font-size: 0.95rem;
            color: #4B5563;
            line-height: 1.6;
        }
        .stPopover {
            z-index: 9999 !important;
        }
    </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
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

def reset_chat_state():
    st.session_state.messages = []

def get_or_scrape_article(url: str):
    if url in st.session_state.article_cache:
        logging.info(f"Using cached article for URL: {url}")
        return st.session_state.article_cache[url]

    logging.info(f"Initiating scraping for URL: {url}")
    scraper = NewsArticleScraper()
    scraped_article = scraper.scrape_article(url)
    st.session_state.article_cache[url] = scraped_article
    logging.info("Scraping completed.")
    return scraped_article

st.set_page_config(page_title="InsightBot", layout="wide", initial_sidebar_state="auto")
inject_custom_css()
initialize_session_state()

with st.sidebar:
    st.markdown("## InsightBot")
    st.markdown("Your intelligent article summarizer and query assistant.")

    url_input = st.text_input(
        "Enter Article URL",
        placeholder="https://example.com/news/article",
        key="url_input_field"
    )

    if st.button("Generate Article Summary"):
        if url_input:
            if url_input != st.session_state.current_url:
                reset_chat_state()
                st.session_state.current_url = url_input

            try:
                with st.spinner("Processing article... this may take a moment."):
                    st.session_state.scraped_article = get_or_scrape_article(url_input)

                logging.info("Generating full article summary...")
                with st.spinner("Generating full article summary..."):
                    summarizer = ArticleSummarizer()
                    st.session_state.article_summary = summarizer.generate(st.session_state.scraped_article.content)
                    logging.info("Full article summary generation complete.")
                st.rerun()

            except Exception as e:
                logging.error(f"Pipeline crashed: Encountered an Error: {e}")
                st.error(f"An error occurred: {e}")
                st.session_state.scraped_article = None
                st.session_state.article_summary = None
        else:
            st.warning("Please enter a URL.")

    if st.session_state.article_summary:
        st.markdown(f"""
        <div class="summary-box">
            <h3>Article Summary</h3>
            <p>{st.session_state.article_summary}</p>
        </div>
        """, unsafe_allow_html=True)

st.title("Chat with the Article")

if st.session_state.scraped_article:
    st.write(f"Now asking questions about: **{st.session_state.scraped_article.title}**")
else:
    st.write("First, provide a URL and generate an article summary.")


chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "critique" in message and message["critique"]:
                critique = message["critique"]
                cols = st.columns(2)
                with cols[0]:
                    with st.popover(f"Faithful: {critique.is_faithful}", use_container_width=True):
                        st.markdown(f"**Justification:** {critique.faithfulness_explanation}")
                with cols[1]:
                    with st.popover(f"Relevant: {critique.is_relevant}", use_container_width=True):
                         st.markdown(f"**Justification:** {critique.relevance_explanation}")


if prompt := st.chat_input("Ask a question about the article..."):
    if not st.session_state.scraped_article:
        st.warning("Please provide a URL and generate the article summary first.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        try:
            article_dict = json.loads(st.session_state.scraped_article.model_dump_json())

            retriever = ContextRetriever(openai_api_key=openai_api_key)
            retrieval_results = retriever.retrieve(scraped_data=article_dict, query=prompt, k=3)
            passages = retrieval_results.get("retrieved_passages", [])

            if not passages:
                answer = "I could not find relevant information in the article to answer your question."
                critique_result = None
            else:
                summary_gen = SummaryGenerator()
                answer = summary_gen.generate(prompt, passages)

                critique_gen = SelfCritique(openai_api_key=openai_api_key)
                context_for_critique = "\n---\n".join([p["text"] for p in passages])
                critique_result = critique_gen.evaluate(prompt, context_for_critique, answer)

            assistant_message = {
                "role": "assistant",
                "content": answer,
                "critique": critique_result
            }
            st.session_state.messages.append(assistant_message)
            st.rerun()

        except Exception as e:
            logging.error(f"Query processing failed due to an error: {e}")
            st.error(f"Failed to process your query. Error: {e}")