FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Download NLTK punkt tokenizer data required by newspaper4k
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# Copy source (overridden by bind mounts in dev, but needed for build)
COPY backend/ /app/backend/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--reload-dir", "/app/backend"]
