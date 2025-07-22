import re
import logging
from datetime import datetime
from typing import Optional, List
from urllib.parse import urlparse
import sys
import requests
from newspaper import Article
from bs4 import BeautifulSoup, Comment
import dateutil.parser
from pydantic import BaseModel, HttpUrl, Field, field_validator



class ScrapedArticle(BaseModel):
    """
    Pydantic model
    """
    url: HttpUrl
    title: str = Field(..., min_length=1, description="Article Title")
    content: str = Field(..., min_length=50, description="Main article content")
    authors: List[str] = Field(default_factory=list, description="Article authors")
    publish_date: Optional[datetime] = Field(default=None, description="Publication date")
    summary: str = Field(default="", description="Auto-generated summary")
    source_domain: str = Field(..., description="Source website domain")
    word_count: int = Field(ge=0, description="Word count of main content")
    extraction_method: str = Field(..., description="Method used for extraction")
    
    @field_validator('content')
    @classmethod
    def content_must_be_substantial(cls, v):
        if len(v.strip().split()) < 10:
            raise ValueError('Minimum 10 words required')
        return v.strip()
    
    @field_validator('source_domain')
    @classmethod
    def extract_domain(cls, v, info):
        if 'url' in info.data:
            parsed = urlparse(str(info.data['url']))
            return parsed.netloc
        return v


class NewsArticleScraper:
    
    def __init__(self, timeout: int = 30, user_agent: str = None):
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
    
    def scrape_article(self, url: str) -> ScrapedArticle:
        
        # Try newspaper3k first (primary method)
        try:
            article_data = self.scrape_with_newspaper(url)
            return ScrapedArticle(**article_data)
        except Exception as e:
            logger.warning(f"Newspaper3k extraction failed: {str(e)}")
        
        # Fallback to BeautifulSoup
        try:
            article_data = self._scrape_with_beautifulsoup(url)
            logger.info("Successfully extracted content using BeautifulSoup fallback")
            return ScrapedArticle(**article_data)
        except Exception as e:
            logger.error(f"BeautifulSoup extraction also failed: {str(e)}")
            raise ValueError(f"Failed to extract article content from {url}")
    
    def scrape_with_newspaper(self, url: str) -> dict:
       
        try:
            article = Article(url, request_timeout=self.timeout)
            article.download()
            
            if not article.html:
                raise ValueError("Failed to download article HTML")
                
            article.parse()
            
            # Validate that we got substantial content
            if not article.text or len(article.text.strip()) < 100:
                raise ValueError("Insufficient content extracted by newspaper3k")
            
         
            return {
                'url': url,
                'title': article.title or "No title found",
                'content': self.clean_text(article.text),
                'authors': [article.authors[0]] if article.authors else [],
                'publish_date': article.publish_date,
                'source_domain': "",  
                'word_count': len(article.text.split()),
                'extraction_method': "newspaper3k"
            }
        except Exception as e:
            logger.error(f"Newspaper3k failed: {e}")
            raise
    
    def _scrape_with_beautifulsoup(self, url: str) -> dict:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        self.remove_unwanted_elements(soup)
    
        title = self.extract_title(soup)
        content = self.extract_content(soup)
        
        if not content or len(content.strip()) < 100:
            raise ValueError("Insufficient content extracted by BeautifulSoup")
        
        authors = self.extract_authors(soup)
        publish_date = self.extract_publish_date(soup)
        
        return {
            'url': url,
            'title': title,
            'content': self.clean_text(content),
            'authors': authors,
            'publish_date': publish_date,
            'summary': "",  # No auto-summary in fallback mode
            'source_domain': "",  # Will be set by validator
            'word_count': len(content.split()),
            'extraction_method': "beautifulsoup"
        }
    
    def remove_unwanted_elements(self, soup: BeautifulSoup) -> None:

        comments = soup.findAll(text=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.extract()
        
        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # Remove common ad/navigation classes and IDs
        unwanted_selectors = [
            '[class*="ad"]', '[class*="advertisement"]', '[class*="banner"]',
            '[class*="nav"]', '[class*="menu"]', '[class*="sidebar"]',
            '[class*="comment"]', '[class*="social"]', '[class*="share"]',
            '[id*="ad"]', '[id*="advertisement"]', '[id*="banner"]',
            '[id*="nav"]', '[id*="menu"]', '[id*="sidebar"]',
            '.related-articles', '.recommended', '.newsletter'
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
    
    def extract_title(self, soup: BeautifulSoup) -> str:
        # Try multiple selectors in order of preference
        title_selectors = [
            'h1.entry-title', 'h1.post-title', 'h1.article-title',
            'h1[class*="title"]', 'h1[class*="headline"]',
            'h1', 'title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()
        
        return "No title found"
    
    def extract_content(self, soup: BeautifulSoup) -> str:
        content_selectors = [
            'article', '.entry-content', '.post-content', '.article-content',
            '.content', '[class*="article-body"]', '[class*="post-body"]',
            '.story-body', '[itemprop="articleBody"]'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                paragraphs = element.find_all('p')
                if paragraphs:
                    content = '\n\n'.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
                    if len(content) > 200: #Making sure the extracted content is more than 200 
                        return content
        
        # Fallback: find the longest text block
        all_paragraphs = soup.find_all('p')
        if all_paragraphs:
            content = '\n\n'.join(p.get_text().strip() for p in all_paragraphs if p.get_text().strip())
            return content

        return soup.get_text()
    
    def extract_authors(self, soup: BeautifulSoup) -> List[str]:
        authors = []
        
    
        author_selectors = [
            '[class*="author"]', '[class*="byline"]', '[rel="author"]',
            '[itemprop="author"]', '.writer', '.journalist'
        ]
        
        for selector in author_selectors:
            elements = soup.select(selector)
            for element in elements:
                author_text = element.get_text().strip()
                if author_text and len(author_text) < 100:  # Reasonable author name length
                    # Clean up author text
                    author_text = re.sub(r'^(by|author:?)\s*', '', author_text, flags=re.IGNORECASE)
                    if author_text not in authors:
                        authors.append(author_text)
        
        return authors[:1]  # Limit to 1 author max
    
    def extract_publish_date(self, soup: BeautifulSoup) -> Optional[datetime]:
 
        date_selectors = [
            '[datetime]', '[class*="date"]', '[class*="time"]',
            '[itemprop="datePublished"]', 'time'
        ]
        
        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                # Try datetime attribute first
                date_str = element.get('datetime') or element.get('content') or element.get_text()
                if date_str:
                    try:
                        # Simple date parsing that handle common formats
                        return dateutil.parser.parse(date_str)
                    except Exception as e:
                        logger.debug(f"Failed to parse date '{date_str}': {e}")
                        continue
        return None
    

    
    def clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
        
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        text = re.sub(r'\[.*?\]', '', text)  
        text = re.sub(r'^\s*advertisement\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        return text.strip()


def main():
    """
    testing scraper
            """
    import sys
    
    
    url = input("Enter Url: ")
    print(f"Scraping URL: {url}")
    
    try:
        scraper = NewsArticleScraper()
        article = scraper.scrape_article(url)
        
        print("\n" + "="*50)
        print("SCRAPED ARTICLE DATA")
        print("="*50)
        print(f"Title: {article.title}")
        print(f"URL: {article.url}")
        print(f"Source Domain: {article.source_domain}")
        print(f"Authors: {', '.join(article.authors) if article.authors else 'Unknown'}")
        print(f"Publish Date: {article.publish_date or 'Unknown'}")
        print(f"Word Count: {article.word_count}")
        print(f"Extraction Method: {article.extraction_method}")
        print(f"\nContent Preview: ")
        print("-" * 30)
        print(article.content)
        
    except ImportError as e:
        print(f"Missing dependency: {e}")
    except Exception as e:
        print(f"Scraping failed: {str(e)}")




if __name__ == "__main__":
    main()