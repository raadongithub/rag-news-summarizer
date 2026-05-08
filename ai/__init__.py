"""AI pipeline package for scraping, retrieval, and summarization.

Notes
-----
Exports the core package surface used by the Streamlit app and CLI pipeline.
"""

from .retriever import ContextRetriever
from .scraper import NewsArticleScraper, ScrapedArticle
from .summary import ArticleSummarizer, Critique, SelfCritique, SummaryGenerator

__all__ = [
    "ArticleSummarizer",
    "ContextRetriever",
    "Critique",
    "NewsArticleScraper",
    "ScrapedArticle",
    "SelfCritique",
    "SummaryGenerator",
]
