FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY rag-news-summarizer/pyproject.toml /app/rag-news-summarizer/pyproject.toml
COPY rag-news-summarizer/uv.lock /app/rag-news-summarizer/uv.lock

RUN uv pip install --no-cache-dir --system -r /app/rag-news-summarizer/pyproject.toml

COPY rag-news-summarizer /app/rag-news-summarizer

RUN python -m nltk.downloader punkt

ENV PYTHONPATH=/app/rag-news-summarizer

EXPOSE 8501

CMD ["streamlit", "run", "/app/rag-news-summarizer/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--browser.serverAddress=localhost"]
