import json
import logging
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

import dateutil.parser
import requests
from bs4 import BeautifulSoup, Comment
from newspaper import Article
from pydantic import BaseModel, Field, HttpUrl, field_validator


logger = logging.getLogger(__name__)


class ScrapedArticle(BaseModel):
    """Structured article data produced by the scraper.

    Attributes
    ----------
    url:
        Canonical article URL.
    title:
        Headline or article title.
    content:
        Main cleaned body text.
    authors:
        Extracted author names.
    publish_date:
        Parsed publication timestamp when available.
    summary:
        Optional summary field retained for compatibility.
    source_domain:
        Domain derived from the article URL.
    word_count:
        Total number of words in the extracted content.
    extraction_method:
        Extraction backend that produced the content.
    """

    url: HttpUrl
    title: str = Field(..., min_length=1, description="Article Title")
    content: str = Field(..., min_length=50, description="Main article content")
    authors: List[str] = Field(default_factory=list, description="Article authors")
    publish_date: Optional[datetime] = Field(
        default=None,
        description="Publication date",
    )
    summary: str = Field(default="", description="Auto-generated summary")
    source_domain: str = Field(..., description="Source website domain")
    word_count: int = Field(ge=0, description="Word count of main content")
    extraction_method: str = Field(..., description="Method used for extraction")

    @field_validator("content")
    @classmethod
    def content_must_be_substantial(cls, value: str) -> str:
        if len(value.strip().split()) < 10:
            raise ValueError("Minimum 10 words required")
        return value.strip()

    @field_validator("source_domain")
    @classmethod
    def extract_domain(cls, value: str, info) -> str:
        if "url" in info.data:
            parsed = urlparse(str(info.data["url"]))
            return parsed.netloc
        return value


class NewsArticleScraper:
    """Scrape article content with newspaper4k and BeautifulSoup fallback.

    Parameters
    ----------
    timeout:
        Request timeout in seconds.
    user_agent:
        Optional HTTP user agent override.
    """

    def __init__(self, timeout: int = 30, user_agent: str | None = None):
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def scrape_article(self, url: str) -> ScrapedArticle:
        """Scrape a URL into a validated article model.

        Parameters
        ----------
        url:
            Article URL to fetch and parse.

        Returns
        -------
        ScrapedArticle
            Validated article payload.

        Raises
        ------
        ValueError
            If both primary and fallback extraction fail.
        """
        try:
            article_data = self.scrape_with_newspaper(url)
            return ScrapedArticle(**article_data)
        except Exception as error:
            logger.warning("Newspaper extraction failed: %s", error)

        try:
            article_data = self.scrape_with_beautifulsoup(url)
            logger.info("Successfully extracted content using BeautifulSoup fallback")
            return ScrapedArticle(**article_data)
        except Exception as error:
            logger.error("BeautifulSoup extraction also failed: %s", error)
            raise ValueError(f"Failed to extract article content from {url}") from error

    def scrape_with_newspaper(self, url: str) -> dict:
        """Extract article content using newspaper4k.

        Parameters
        ----------
        url:
            Article URL to fetch and parse.

        Returns
        -------
        dict
            Raw extraction payload suitable for ``ScrapedArticle``.
        """
        try:
            article = Article(url, request_timeout=self.timeout)
            article.download()

            if not article.html:
                raise ValueError("Failed to download article HTML")

            article.parse()
            if not article.text or len(article.text.strip()) < 100:
                raise ValueError("Insufficient content extracted by newspaper4k")

            return {
                "url": url,
                "title": article.title or "No title found",
                "content": self.clean_text(article.text),
                "authors": [article.authors[0]] if article.authors else [],
                "publish_date": article.publish_date,
                "source_domain": "",
                "word_count": len(article.text.split()),
                "extraction_method": "newspaper4k",
            }
        except Exception as error:
            logger.error("Newspaper extraction failed: %s", error)
            raise

    def scrape_with_beautifulsoup(self, url: str) -> dict:
        """Extract article content using BeautifulSoup selectors.

        Parameters
        ----------
        url:
            Article URL to fetch and parse.

        Returns
        -------
        dict
            Raw extraction payload suitable for ``ScrapedArticle``.
        """
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        self.remove_extras(soup)

        title = self.extract_title(soup)
        content = self.extract_content(soup)
        if not content or len(content.strip()) < 100:
            raise ValueError("Insufficient content extracted by BeautifulSoup")

        authors = self.extract_authors(soup)
        publish_date = self.extract_publish_date(soup)

        return {
            "url": url,
            "title": title,
            "content": self.clean_text(content),
            "authors": authors,
            "publish_date": publish_date,
            "summary": "",
            "source_domain": "",
            "word_count": len(content.split()),
            "extraction_method": "beautifulsoup",
        }

    def remove_extras(self, soup: BeautifulSoup) -> None:
        """Remove boilerplate and non-content elements from a parsed document.

        Parameters
        ----------
        soup:
            Parsed HTML document.
        """
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.extract()

        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        unwanted_selectors = [
            '[class*="ad"]',
            '[class*="advertisement"]',
            '[class*="banner"]',
            '[class*="nav"]',
            '[class*="menu"]',
            '[class*="sidebar"]',
            '[class*="comment"]',
            '[class*="social"]',
            '[class*="share"]',
            '[id*="ad"]',
            '[id*="advertisement"]',
            '[id*="banner"]',
            '[id*="nav"]',
            '[id*="menu"]',
            '[id*="sidebar"]',
            ".related-articles",
            ".recommended",
            ".newsletter",
        ]

        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()

    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract the best candidate article title from a parsed document.

        Parameters
        ----------
        soup:
            Parsed HTML document.

        Returns
        -------
        str
            Best matching title string or a fallback label.
        """
        title_selectors = [
            "h1.entry-title",
            "h1.post-title",
            "h1.article-title",
            'h1[class*="title"]',
            'h1[class*="headline"]',
            "h1",
            "title",
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()

        return "No title found"

    def extract_content(self, soup: BeautifulSoup) -> str:
        """Extract the main article body from a parsed document.

        Parameters
        ----------
        soup:
            Parsed HTML document.

        Returns
        -------
        str
            Extracted article body text.
        """
        content_selectors = [
            "article",
            ".entry-content",
            ".post-content",
            ".article-content",
            ".content",
            '[class*="article-body"]',
            '[class*="post-body"]',
            ".story-body",
            '[itemprop="articleBody"]',
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                paragraphs = element.find_all("p")
                if paragraphs:
                    content = "\n\n".join(
                        paragraph.get_text().strip()
                        for paragraph in paragraphs
                        if paragraph.get_text().strip()
                    )
                    if len(content) > 200:
                        return content

        all_paragraphs = soup.find_all("p")
        if all_paragraphs:
            return "\n\n".join(
                paragraph.get_text().strip()
                for paragraph in all_paragraphs
                if paragraph.get_text().strip()
            )

        return soup.get_text()

    def extract_authors(self, soup: BeautifulSoup) -> List[str]:
        """Extract likely author names from a parsed document.

        Parameters
        ----------
        soup:
            Parsed HTML document.

        Returns
        -------
        list of str
            Candidate author names.
        """
        authors = []
        author_selectors = [
            '[class*="author"]',
            '[class*="byline"]',
            '[rel="author"]',
            '[itemprop="author"]',
            ".writer",
            ".journalist",
        ]

        for selector in author_selectors:
            elements = soup.select(selector)
            for element in elements:
                author_text = element.get_text().strip()
                if author_text and len(author_text) < 100:
                    author_text = re.sub(
                        r"^(by|author:?)\s*",
                        "",
                        author_text,
                        flags=re.IGNORECASE,
                    )
                    if author_text not in authors:
                        authors.append(author_text)

        return authors[:1]

    def extract_publish_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract a publication timestamp from a parsed document.

        Parameters
        ----------
        soup:
            Parsed HTML document.

        Returns
        -------
        datetime or None
            Parsed publication timestamp when found.
        """
        date_selectors = [
            "[datetime]",
            '[class*="date"]',
            '[class*="time"]',
            '[itemprop="datePublished"]',
            "time",
        ]

        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                date_str = (
                    element.get("datetime")
                    or element.get("content")
                    or element.get_text()
                )
                if date_str:
                    try:
                        return dateutil.parser.parse(date_str)
                    except Exception as error:
                        logger.debug("Failed to parse date '%s': %s", date_str, error)
                        continue
        return None

    def clean_text(self, text: str) -> str:
        """Normalize extracted article text.

        Parameters
        ----------
        text:
            Raw extracted text.

        Returns
        -------
        str
            Normalized text with noise reduced.
        """
        if not text:
            return ""

        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"\[.*?\]", "", text)
        text = re.sub(
            r"^\s*advertisement\s*$",
            "",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        return text.strip()


def main() -> None:
    """Run a simple local scraper smoke test.

    Notes
    -----
    This helper is intended for manual command-line use.
    """
    url = input("Enter Url: ")
    print(f"Scraping URL: {url}")

    try:
        scraper = NewsArticleScraper()
        article = scraper.scrape_article(url)
        print(
            json.dumps(
                json.loads(article.model_dump_json()),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
    except ImportError as error:
        print(f"Missing dependency: {error}")
    except Exception as error:
        print(f"Scraping failed: {error}")


if __name__ == "__main__":
    main()
