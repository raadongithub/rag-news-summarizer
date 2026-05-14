"""Streamlit interface for the news summarizer."""

from __future__ import annotations

import json
import logging
from dataclasses import replace

import streamlit as st

from backend.core.config import AppConfig, get_settings
from backend.services import ArticleService, ChatService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_SETTINGS = get_settings()


def get_secret(name: str, fallback: str | None = None) -> str | None:
    """Read a key from environment variables or Streamlit secrets.

    Parameters
    ----------
    name : str
        Secret or environment variable name.
    fallback : str or None, optional
        Value returned when the secret is not configured anywhere else.

    Returns
    -------
    str or None
        Secret value when found, otherwise the provided fallback.
    """
    try:
        value = st.secrets[name]
        if value:
            return str(value)
    except (KeyError, FileNotFoundError):
        pass
    return fallback


def resolve_app_settings() -> AppConfig:
    """Resolve runtime settings for the Streamlit application.

    Returns
    -------
    AppConfig
        Settings with Streamlit secret overrides applied.
    """
    return replace(
        BASE_SETTINGS,
        anthropic_api_key=get_secret(
            "ANTHROPIC_API_KEY",
            BASE_SETTINGS.anthropic_api_key,
        ),
        voyage_api_key=get_secret(
            "VOYAGE_API_KEY",
            BASE_SETTINGS.voyage_api_key,
        ),
    )


SETTINGS = resolve_app_settings()
ARTICLE_SERVICE = ArticleService(SETTINGS)
CHAT_SERVICE = ChatService(SETTINGS)

if not SETTINGS.anthropic_api_key:
    st.error(
        "ANTHROPIC_API_KEY not found. Please set it in your environment or Streamlit secrets."
    )
    st.stop()


def inject_custom_css() -> None:
    """Inject the custom CSS used by the Streamlit interface."""
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True,
    )


def initialize_session() -> None:
    """Initialize expected Streamlit session state keys."""
    defaults = {
        "messages": [],
        "scraped_article": None,
        "article_summary": None,
        "current_url": "",
        "article_cache": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_chat_state() -> None:
    """Reset chat-specific state when the active article URL changes."""
    st.session_state.messages = []
    st.session_state.article_summary = None


def get_or_scrape_article(url: str):
    """Fetch an article from cache or scrape it on demand.

    Parameters
    ----------
    url : str
        Article URL selected by the user.

    Returns
    -------
    ScrapedArticle
        Cached or newly scraped article payload.
    """
    if url in st.session_state.article_cache:
        logger.info("Using cached article for URL: %s", url)
        return st.session_state.article_cache[url]

    logger.info("Initiated scraping for URL: %s", url)
    scraped_article = ARTICLE_SERVICE.scrape_article(url)
    st.session_state.article_cache[url] = scraped_article
    logger.info("Scraping completed.")
    print(f"\n--- Scraped Article Title ---\n{scraped_article.title}\n")
    return scraped_article


st.set_page_config(page_title="News Summarizer", layout="wide", initial_sidebar_state="auto")
inject_custom_css()
initialize_session()

with st.sidebar:
    st.markdown("## News Summarizer")
    st.markdown("Enter an article URL to load it for querying.")

    url_input = st.text_input(
        "Enter Article URL",
        placeholder="https://example.com/news/article",
    )

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
            except Exception as exc:
                logger.error("Pipeline crashed during scraping: %s", exc)
                st.error(f"An error occurred while loading the article: {exc}")
                st.session_state.scraped_article = None
        else:
            st.warning("Please enter a URL.")

    if st.session_state.scraped_article:
        st.markdown("---")
        st.success(f"Article Loaded: **{st.session_state.scraped_article.title}**")
        if st.button("Generate Full Article Summary"):
            try:
                logger.info("Generating full article summary")
                with st.spinner("Generating summary, please wait...."):
                    summary_text = ARTICLE_SERVICE.generate_summary(
                        st.session_state.scraped_article.content
                    )
                    st.session_state.article_summary = summary_text
                    logger.info("Full article summary generation complete.")
                    print("\n\n\n--- Full Article Summary ---")
                    print(json.dumps({"full_article_summary": summary_text}, indent=2))
                    print("------------------------------\n")
            except Exception as exc:
                logger.error("Could not generate full article summary. Error: %s", exc)
                st.error("Failed to generate summary.")

    if st.session_state.article_summary:
        st.markdown(
            f"""
            <div class="summary-box">
                <h3>Article Summary</h3>
                <p>{st.session_state.article_summary}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.title("Chat with the Article")

if not st.session_state.scraped_article:
    st.info("Load an article using the sidebar to begin the chat.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("critique"):
            critique = message["critique"]
            cols = st.columns(2)

            relevance_class = "true-box" if critique.is_relevant else "false-box"
            cols[0].markdown(
                f'<div class="{relevance_class}">Relevance: {critique.is_relevant}</div>',
                unsafe_allow_html=True,
            )

            faithfulness_class = "true-box" if critique.is_faithful else "false-box"
            cols[1].markdown(
                f'<div class="{faithfulness_class}">Faithfulness: {critique.is_faithful}</div>',
                unsafe_allow_html=True,
            )

            with st.expander("See Details and Retrieved Context"):
                st.markdown(
                    f"**Relevance Justification:** {critique.relevance_explanation}"
                )
                st.markdown(
                    f"**Faithfulness Justification:** {critique.faithfulness_explanation}"
                )
                if message.get("passages"):
                    st.markdown("---")
                    st.markdown("**Passages Used as Context:**")
                    for index, passage in enumerate(message["passages"], start=1):
                        st.info(
                            f"**{index}.** {passage['text']} "
                            f"(Score: {passage.get('similarity_score', 'N/A'):.2f})"
                        )


if prompt := st.chat_input("Ask a question about the article..."):
    if not st.session_state.scraped_article:
        st.warning("Please load an article using the sidebar first.")
        st.stop()
    if not SETTINGS.voyage_api_key:
        st.warning("VOYAGE_API_KEY is required for chat retrieval features.")
        st.stop()
    if not SETTINGS.anthropic_api_key:
        st.warning("ANTHROPIC_API_KEY is required for chat generation features.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        try:
            article_dict = json.loads(st.session_state.scraped_article.model_dump_json())
            pipeline = CHAT_SERVICE.create_pipeline()
            pipeline_result = pipeline.answer_question(
                article=article_dict,
                query=prompt,
                k=SETTINGS.default_top_k,
                chunk_size=SETTINGS.default_chunk_size,
                chunk_overlap=SETTINGS.default_chunk_overlap,
            )
            passages = [
                passage.model_dump() for passage in pipeline_result.retrieved_passages
            ]

            if pipeline_result.used_fallback_answer:
                logger.warning("No relevant passages were found for query.")
                answer = pipeline_result.answer
                critique_result = None
            else:
                logger.info(
                    "Passage retrieval completed in %.1fms with %d/%d chunks returned.",
                    pipeline_result.retrieval.elapsed_ms,
                    pipeline_result.retrieval.returned_k,
                    pipeline_result.retrieval.total_chunks,
                )
                print("\n\n\n--- Retrieved Passages for Context ---")
                for index, passage in enumerate(passages, start=1):
                    print(
                        f"{index}. {passage['text']} "
                        f"(Score: {passage.get('similarity_score', 'N/A'):.2f})\n\n"
                    )
                print("-" * 40)

                answer = pipeline_result.answer
                logger.info("Summary generation complete.")
                print(f"\n--- Generated Summary ---\n{answer}\n" + "-" * 27)

                logger.info("Performing critique evaluation...")
                context_for_critique = "\n---\n".join(
                    passage["text"] for passage in passages
                )
                critique_result = CHAT_SERVICE.evaluate_answer(
                    prompt,
                    context_for_critique,
                    answer,
                )
                logger.info("Critique evaluation complete.")

            assistant_message = {
                "role": "assistant",
                "content": answer,
                "critique": critique_result,
                "passages": passages,
            }
            st.session_state.messages.append(assistant_message)

            logger.info("Combining results in JSON")
            final_output = {
                "summary": answer,
                "self_critique": (
                    critique_result.model_dump() if critique_result else None
                ),
                "metadata": {
                    "source_url": st.session_state.current_url,
                    "user_query": prompt,
                },
            }
            print("\n--- Final Output---")
            print(json.dumps(final_output, indent=2))
            print("----------------------------------\n")

            st.rerun()
        except Exception as exc:
            logger.error("Query processing failed due to error: %s", exc)
            st.error(f"Failed to process your query. Error: {exc}")
