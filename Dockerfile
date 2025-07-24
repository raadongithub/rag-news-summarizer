FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .

RUN uv pip install --no-cache-dir --system -r pyproject.toml


COPY . .

RUN python -m nltk.downloader punkt

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--browser.serverAddress=localhost"]