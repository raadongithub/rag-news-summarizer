"""Article scraping and summarization service."""

from ..ai.scraper import NewsArticleScraper, ScrapedArticle
from ..ai.summary import ArticleSummarizer
from ..core.config import AppConfig, get_settings


class ArticleService:
    """Scrape articles and generate summaries."""

    def __init__(
        self,
        settings: AppConfig | None = None,
        scraper: NewsArticleScraper | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.scraper = scraper or NewsArticleScraper()

    def scrape_article(self, url: str) -> ScrapedArticle:
        """Fetch and parse a news article URL."""
        return self.scraper.scrape_article(url)

    def generate_summary(self, content: str) -> str:
        """Generate a summary for a full article body."""
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured - summarization is unavailable"
            )
        summarizer = ArticleSummarizer(
            anthropic_api_key=self.settings.anthropic_api_key
        )
        return summarizer.generate(content)
