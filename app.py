import streamlit as st
import re
import logging
import time
import os
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urlparse, urldefrag
import requests
from newspaper import Article
from bs4 import BeautifulSoup, Comment
import dateutil.parser
from pydantic import BaseModel, HttpUrl, Field, field_validator
import numpy as np
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from sklearn.metrics.pairwise import cosine_similarity
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    try:
        openai_api_key = st.secrets["OPENAI_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("OPENAI_API_KEY not found. Please add it to your .env file or Streamlit secrets.")
        st.stop()

class ScrapedArticle(BaseModel):
    url: HttpUrl
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=50)
    authors: List[str] = Field(default_factory=list)
    publish_date: Optional[datetime] = None
    source_domain: str = Field(...)
    word_count: int = Field(ge=0)
    extraction_method: str = Field(...)

    @field_validator('content')
    @classmethod
    def content_must_be_substantial(cls, v):
        if len(v.strip().split()) < 10:
            raise ValueError('Content must have at least 10 words.')
        return v.strip()

    @field_validator('source_domain', mode='before')
    @classmethod
    def extract_domain(cls, v, values):
        url = values.data.get('url')
        if url:
            return urlparse(str(url)).netloc
        return v

class Critique(BaseModel):
    is_faithful: bool = Field(..., description="Is the summary factually consistent with the provided context?")
    faithfulness_explanation: str = Field(..., description="A brief justification for the faithfulness score.")
    is_relevant: bool = Field(..., description="Does the summary directly answer the user's query?")
    relevance_explanation: str = Field(..., description="A brief justification for the relevance score.")

class NewsArticleScraper:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    def scrape_article(self, url: str) -> ScrapedArticle:
        try:
            article_data = self._scrape_with_newspaper(url)
            return ScrapedArticle(**article_data)
        except Exception as e:
            logging.warning(f"Newspaper3k failed: {e}. Falling back to BeautifulSoup.")
            try:
                article_data = self._scrape_with_beautifulsoup(url)
                return ScrapedArticle(**article_data)
            except Exception as bs_e:
                logging.error(f"BeautifulSoup fallback also failed: {bs_e}")
                raise ValueError(f"Failed to extract article from {url}")

    def _scrape_with_newspaper(self, url: str) -> dict:
        article = Article(url, request_timeout=self.timeout)
        article.download()
        article.parse()
        if not article.text or len(article.text.strip()) < 100:
            raise ValueError("Insufficient content from newspaper3k.")
        return {
            'url': url,
            'title': article.title or "No title found",
            'content': self._clean_text(article.text),
            'authors': article.authors,
            'publish_date': article.publish_date,
            'source_domain': url,
            'word_count': len(article.text.split()),
            'extraction_method': "newspaper3k"
        }

    def _scrape_with_beautifulsoup(self, url: str) -> dict:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        self._remove_extras(soup)
        content = self._extract_content(soup)
        if not content or len(content.strip()) < 100:
            raise ValueError("Insufficient content from BeautifulSoup.")
        return {
            'url': url,
            'title': self._extract_title(soup),
            'content': self._clean_text(content),
            'authors': self._extract_authors(soup),
            'publish_date': self._extract_publish_date(soup),
            'source_domain': url,
            'word_count': len(content.split()),
            'extraction_method': "beautifulsoup"
        }

    def _remove_extras(self, soup: BeautifulSoup):
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        for comment in soup.findAll(text=lambda text: isinstance(text, Comment)):
            comment.extract()

    def _extract_title(self, soup: BeautifulSoup) -> str:
        return soup.find('h1').get_text(strip=True) if soup.find('h1') else "No title found"

    def _extract_content(self, soup: BeautifulSoup) -> str:
        paragraphs = soup.find_all('p')
        return '\n\n'.join(p.get_text(strip=True) for p in paragraphs)

    def _extract_authors(self, soup: BeautifulSoup) -> List[str]:
        author_tag = soup.select_one('[class*="author"], [rel="author"]')
        return [author_tag.get_text(strip=True)] if author_tag else []

    def _extract_publish_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        time_tag = soup.select_one('time, [datetime]')
        if time_tag:
            date_str = time_tag.get('datetime') or time_tag.get_text(strip=True)
            try:
                return dateutil.parser.parse(date_str)
            except (ValueError, TypeError):
                return None
        return None

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

class ContextRetriever:
    def __init__(self, api_key: str):
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=api_key)

    def _split_to_chunks(self, content: str, chunk_size: int=50, chunk_overlap: int=10) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', content.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences: return []
        chunks = []
        step = chunk_size - chunk_overlap
        for i in range(0, len(sentences), step):
            chunks.append(" ".join(sentences[i:i + chunk_size]))
        return [c for c in chunks if c]

    def retrieve(self, content: str, query: str, k: int=3) -> List[Dict]:
        if not content.strip(): return []
        chunks = self._split_to_chunks(content)
        if not chunks: return []
        query_embedding = np.array(self.embeddings.embed_query(query))
        passage_embeddings = np.array(self.embeddings.embed_documents(chunks))
        similarities = cosine_similarity([query_embedding], passage_embeddings)[0]
        top_indices = np.argsort(similarities)[-k:][::-1]
        return [{"text": chunks[i], "score": float(similarities[i])} for i in top_indices]

class SummaryGenerator:
    def __init__(self, api_key: str):
        self.llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.0, api_key=api_key)
        self.chain = (
            ChatPromptTemplate.from_messages([
                ("system", "You are an expert AI news summarizer. Provide a concise, single-sentence summary that directly answers the user's question based *only* on the provided context. Do not add introductory phrases."),
                ("human", "Please answer: \"{query}\"\n\nUse only this context:\n{context}"),
            ]) | self.llm | StrOutputParser()
        )

    def generate(self, query: str, retrieved_passages: List[Dict]) -> str:
        context = "\n---\n".join([p["text"] for p in retrieved_passages])
        if not context.strip(): return "Could not find relevant information to answer the query."
        return self.chain.invoke({"query": query, "context": context}).strip()

class ArticleSummarizer:
    def __init__(self, api_key: str):
        self.llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.2, api_key=api_key)
        self.chain = (
            ChatPromptTemplate.from_messages([
                ("system", "You are an expert news editor. Create a comprehensive, well-structured summary of the news article in 5-7 lines, capturing the main events, key figures, and significance. Return plain text only."),
                ("human", "Please summarize:\n\n{content}"),
            ]) | self.llm | StrOutputParser()
        )

    def generate(self, content: str) -> str:
        if not content.strip(): return "Article content is empty."
        return self.chain.invoke({"content": content}).strip()

class SelfCritique:
    def __init__(self, api_key: str):
        self.llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.0, api_key=api_key).with_structured_output(Critique)

    def evaluate(self, query: str, context: str, summary: str) -> Critique:
        return self.llm.invoke([
            SystemMessage("You are an expert AI fact-checker. Evaluate the summary based on the source text and user query for factual consistency (faithfulness) and directness in answering the query (relevance)."),
            HumanMessage(f"Evaluate the following summary.\n\n**User Query:**\n\"{query}\"\n\n**Source Context:**\n---\n{context}\n---\n\n**Summary to Evaluate:**\n\"{summary}\""),
        ])

def inject_custom_css():
    st.markdown("""
    <style>
        .stApp {
            background-color: #FFFFFF;
        }
        
        [data-testid="stSidebar"] {
            background-color: #F0F2F6;
            width: 30% !important;
            min-width: 300px !important;
            max-width: 30% !important;
        }
        
        .stChatInputContainer {
            background-color: #FFFFFF;
            border-top: 1px solid #E0E0E0;
            padding: 1rem 1.5rem;
        }
        
        [data-testid="stChatInput"] textarea {
            background-color: #F0F2F6;
            border-radius: 12px;
            border: 1px solid #D1D5DB;
            color: #111827;
            min-height: 60px !important;
            height: 60px !important;
        }
        
        [data-testid="stChatMessage"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        [data-testid="stChatMessage"][data-testid*="user"] {
            margin-left: 10% !important;
            margin-right: 0 !important;
        }
        
        [data-testid="stChatMessage"][data-testid*="assistant"] {
            margin-left: 0 !important;
            margin-right: 10% !important;
        }
        
        [data-testid="stChatMessage"] p {
            margin: 0;
            font-size: 1rem;
            color: #374151;
        }
        
        .stButton>button {
            border-radius: 8px;
            border: 1px solid transparent;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .true-button {
            background-color: #D1FAE5 !important;
            color: #065F46 !important;
            border: 1px solid #6EE7B7 !important;
        }
        
        .false-button {
            background-color: #FEE2E2 !important;
            color: #991B1B !important;
            border: 1px solid #FCA5A5 !important;
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
        
        .stPopoverContent {
            background-color: white !important;
            border: 1px solid #E5E7EB !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
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

def get_or_scrape_article(url: str) -> ScrapedArticle:
    if url in st.session_state.article_cache:
        logging.info(f"Using cached article content for URL: {url}")
        return st.session_state.article_cache[url]
    
    logging.info(f"Initiated scraping for URL: {url}")
    scraper = NewsArticleScraper()
    scraped_article = scraper.scrape_article(url)
    st.session_state.article_cache[url] = scraped_article
    logging.info("Scraping completed")
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
                    summarizer = ArticleSummarizer(api_key=openai_api_key)
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
st.write("Ask specific questions about the article content.")

chat_container = st.container()
with chat_container:
    for i, message in enumerate(reversed(st.session_state.messages)):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "critique" in message:
                critique = message["critique"]
                cols = st.columns(2)
                with cols[0]:
                    relevance_class = "true-button" if critique.is_relevant else "false-button"
                    with st.popover(f"Relevance: {critique.is_relevant}", use_container_width=True):
                        st.markdown(f"**Explanation:** {critique.relevance_explanation}")
                    
                with cols[1]:
                    faithfulness_class = "true-button" if critique.is_faithful else "false-button"
                    with st.popover(f"Faithfulness: {critique.is_faithful}", use_container_width=True):
                         st.markdown(f"**Explanation:** {critique.faithfulness_explanation}")

if prompt := st.chat_input("Ask a question about the article..."):
    if not st.session_state.scraped_article:
        st.warning("Please generate an article summary first using the sidebar.")
        st.stop()

    logging.info(f"Retrieving passages for query: '{prompt}'")
    
    st.session_state.messages.insert(0, {"role": "user", "content": prompt})
    
    with st.spinner("Thinking..."):
        try:
            retriever = ContextRetriever(api_key=openai_api_key)
            passages = retriever.retrieve(st.session_state.scraped_article.content, prompt)
            logging.info("Passage retrieval completed.")
            
            if not passages:
                logging.warning("No relevant passages were found for the query.")
                answer = "Could not find relevant information to answer the query."
                critique_result = None
            else:
                logging.info("Generating initial summary...")
                summary_gen = SummaryGenerator(api_key=openai_api_key)
                answer = summary_gen.generate(prompt, passages)
                logging.info("Summary generation complete.")

                logging.info("Performing critique evaluation")
                critique_gen = SelfCritique(api_key=openai_api_key)
                context_for_critique = "\n---\n".join([p["text"] for p in passages])
                critique_result = critique_gen.evaluate(prompt, context_for_critique, answer)
                logging.info("Self-critique evaluation complete.")
            
            assistant_message = {
                "role": "assistant",
                "content": answer,
                "critique": critique_result
            }
            st.session_state.messages.insert(0, assistant_message)
            st.rerun()

        except Exception as e:
            logging.error(f"Pipeline stopped due to Error: {e}")
            st.error(f"Failed to process your query. Error: {e}")