# News Article Summarizer

Authenticated RAG-powered news article summarizer and Q&A with a FastAPI backend, Next.js frontend, PostgreSQL persistence, SQLAlchemy ORM, and Alembic migrations.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

When the stack is healthy:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Backend health: `http://localhost:8000/health`
- PostgreSQL: `localhost:5432`

## Environment Variables

Required:
- `ANTHROPIC_API_KEY`
- `VOYAGE_API_KEY`
- `ACCESS_TOKEN_SECRET`

Important defaults:
- `DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/news_summarizer`
- `CORS_ORIGINS=http://localhost:3000`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`

## Architecture

```text
frontend/               Next.js UI, auth flow, article/chat canvas
backend/api/            FastAPI route modules
backend/core/           Centralized config, security, exceptions
backend/db/             SQLAlchemy engine/session and Alembic helpers
backend/models/         SQLAlchemy ORM models
backend/repositories/   Database access layer
backend/schema/         Pydantic request and response schemas
backend/services/       Auth, session, article, and chat services
db_migrations/          Migration environment and versions
```

## Auth and Session Flow

- `POST /auth/register` creates a user and returns a bearer token.
- `POST /auth/login` authenticates an existing user and returns a bearer token.
- `GET /auth/me` returns the current authenticated user.
- Session endpoints are now user-scoped and require `Authorization: Bearer <token>`.
- Browser state stores the auth token and current session ID in `localStorage`.

## Database and Migrations

The backend uses PostgreSQL via SQLAlchemy. Alembic manages schema evolution.

Apply migrations manually:

```bash
uv run alembic upgrade head
```

Create a new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

The FastAPI app also runs `upgrade head` during startup so containers come up on the latest schema automatically.

Milvus logging is intentionally reduced in Docker by mounting [deploy/milvus.yaml](/home/raad/Bandicam_8.2.0.2524/rag-news-summarizer/deploy/milvus.yaml), which sets `log.level` to `warn`.

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | Log in |
| `GET` | `/auth/me` | Current user profile |
| `POST` | `/sessions` | Create session |
| `GET` | `/sessions/{id}` | Load session |
| `GET` | `/sessions/{id}/history` | Session chat history |
| `POST` | `/sessions/{id}/article` | Scrape and index an article |
| `POST` | `/sessions/{id}/summarize` | Generate full summary |
| `POST` | `/sessions/{id}/chat` | Ask a question |

## Frontend Changes

- Login and registration flow added.
- Favicon added via `frontend/app/icon.svg`.
- Summary cards and chat items can open a full-canvas detail view.
- Expanded canvas shows:
  - generated summary
  - full article text
  - context specific to the selected article card or chat message
  - supporting passages when available

## Local Development

Backend:

```bash
uv sync
uv run python -m nltk.downloader punkt punkt_tab stopwords
uv run alembic upgrade head
uv run uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## RAG Evaluation

```bash
uv run python evaluate_rag.py --dataset eval/samples.json --output eval/report.json
```

The evaluation pipeline still reuses the same scraper, chunking, embeddings, retrieval, and answer generation services as the app runtime.

## Notes

- Existing article loading, summary generation, and RAG chat behavior remain intact behind the new auth and persistence layer.
- Session records store article payloads, chat history, and retrieval metadata as ORM-managed JSON columns.
- Structured error responses now include stable error codes for auth and validation failures.
