# =============================================================================
# STAGE 1 — builder
#
# Think of this stage as a disposable workshop. We bring in every heavy tool
# we need to compile and install Python packages (C compilers, header files,
# etc.), do all the work, then walk away and lock the door. Nothing from this
# stage ends up in the image users actually run — only the finished goods get
# carried over to Stage 2.
# =============================================================================
FROM python:3.13-slim AS builder

# Some packages (lxml, numpy, scikit-learn) ship as C extensions. They need a
# C/C++ compiler and the XML library headers to build their wheels from source.
# We install them here in the builder ONLY — they will NOT appear in the final
# image, which is the whole point of multi-stage builds.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libxml2-dev \
        libxslt-dev \
    # Clean up the apt cache in the same RUN so the layer doesn't carry the
    # cache bytes forward. Every RUN creates a new layer; if you clean in a
    # separate RUN the cache is already baked into the previous layer forever.
    && rm -rf /var/lib/apt/lists/*

# We pull the uv binary directly from its own official image instead of
# pip-installing it. This is faster, avoids a pip dependency chain, and keeps
# the uv version pinned without polluting our virtualenv.
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv

# UV_COMPILE_BYTECODE: tells uv to pre-compile .pyc files during install.
#   The .pyc files are what Python actually executes. Pre-compiling here means
#   the first import of every module at runtime is instant — no "warm up" lag.
#
# UV_LINK_MODE=copy: by default uv hard-links files from its cache to the venv.
#   Inside Docker there is no persistent cache between builds, so we tell it to
#   just copy instead. Avoids confusing "cross-device link" errors.
#
# UV_PROJECT_ENVIRONMENT: where uv creates the virtualenv.
#   We put it under /app/.venv so we know exactly where to find it in Stage 2.
#
# PYTHONDONTWRITEBYTECODE: tells the Python interpreter NOT to write .pyc files
#   at runtime. We already compiled them during install (UV_COMPILE_BYTECODE),
#   so writing them again at runtime would just waste I/O.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# --- Dependency installation (the most cache-friendly layer in the file) ---
#
# Docker rebuilds every layer that comes AFTER the first changed layer.
# By copying ONLY the lock files here — before any application source code —
# we get a very stable cache hit: this expensive install step is skipped on
# every rebuild where only .py files changed, which is most of your day-to-day
# development cycle.
#
# Rule of thumb: copy things that change rarely BEFORE things that change often.
COPY pyproject.toml uv.lock ./

# uv sync flags explained:
#   --frozen        → treat the lockfile as the single source of truth; error
#                     out if pyproject.toml and uv.lock are out of sync instead
#                     of silently resolving a different set of packages.
#   --no-dev        → skip any [tool.uv.dev-dependencies]; we don't need pytest
#                     or black inside a production container.
#   --no-install-project → don't install our own package (rag-news-summarizer)
#                     yet; we're only materialising third-party dependencies so
#                     this layer can be cached independently of our source code.
RUN uv sync \
        --frozen \
        --no-dev \
        --no-install-project

# --- NLTK data download (one layer, zero leftover artifacts) ---
#
# newspaper4k (our article scraper) needs the NLTK punkt tokenizer to split
# text into sentences. We download it here, in the builder, so the final image
# has it baked in and never needs to phone home at runtime.
#
# Key design decisions:
#   1. We download into /app/nltk_data (not ~/nltk_data) so the path is
#      predictable and we can copy it to Stage 2 without hunting for it.
#   2. After downloading, we delete every .zip archive in the same RUN command.
#      NLTK keeps the zip alongside the extracted folder "just in case". We
#      don't need it and it adds ~15 MB of dead weight. Deleting in the same
#      RUN is critical — a separate RUN would still bake the zips into the
#      previous layer's snapshot.
#   3. stopwords is included proactively because langchain text splitters and
#      newspaper4k's summariser both reach for it. Better to have it now than
#      get a surprise LookupError in production at 2 AM.
RUN uv run python -c "\
import nltk; \
nltk.download('punkt',      download_dir='/app/nltk_data', quiet=True); \
nltk.download('punkt_tab',  download_dir='/app/nltk_data', quiet=True); \
nltk.download('stopwords',  download_dir='/app/nltk_data', quiet=True); \
" \
    && find /app/nltk_data -name "*.zip" -delete


# =============================================================================
# STAGE 2 — runtime
#
# This is the image that actually ships and runs. It starts fresh from the same
# slim base — no compiler, no header files, no uv binary, no build caches.
# We only bring in the three things we built in Stage 1:
#   • the virtualenv with all compiled packages  (/app/.venv)
#   • the NLTK tokenizer data                    (/app/nltk_data)
# And then we add our own application source code from the host.
# =============================================================================
FROM python:3.13-slim AS runtime

# At runtime lxml needs the shared libraries (.so files) for libxml2 and
# libxslt to be present on the system — but NOT the -dev header files, which
# are only needed at compile time. This saves ~80 MB compared to the builder's
# apt install.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring in the fully-compiled, ready-to-run virtualenv from the builder stage.
# The --from=builder flag is what makes this a multi-stage build. Everything
# else from the builder (compiler, headers, uv, pip caches) is left behind.
COPY --from=builder /app/.venv    /app/.venv

# Bring in the pre-downloaded NLTK corpora. Without this, every container
# start would attempt a network download, which fails in air-gapped environments
# and introduces a non-deterministic external dependency into your runtime.
COPY --from=builder /app/nltk_data /app/nltk_data

# Copy our application source code. This is intentionally the LAST COPY so
# that day-to-day code changes only invalidate this single thin layer, not the
# expensive dependency or NLTK layers above.
#
# NOTE: In development, docker-compose mounts ./backend → /app/backend as a
# bind mount, which overwrites this COPY at runtime and gives you live reload.
# This COPY is still useful for production builds where no bind mount is used.
COPY backend/ /app/backend/
COPY db_migrations/ /app/db_migrations/
COPY alembic.ini /app/alembic.ini

# --- Runtime environment variables ---
#
# PATH: Instead of running "source .venv/bin/activate" (which only works in an
#   interactive shell), we prepend the venv's bin/ to PATH. This is the correct
#   way to activate a venv non-interactively. Every subsequent command — python,
#   uvicorn, etc. — will resolve to the venv's copy automatically.
#
# PYTHONPATH: Tells Python where to look for packages when using absolute
#   imports like "from backend.core.config import ...". Since our app lives at
#   /app/backend and imports itself as `backend.*`, we set PYTHONPATH=/app so
#   Python sees the `backend` package at the top level.
#
# PYTHONUNBUFFERED: Forces Python's stdout/stderr to flush immediately instead
#   of buffering output. Critical for Docker — without this, logs from your app
#   can appear seconds late or be lost entirely if the container crashes.
#
# NLTK_DATA: Tells every NLTK call exactly where to find the corpora we
#   downloaded in the builder. Without this, NLTK searches a list of default
#   paths (home dir, /usr/share/nltk_data, etc.) and may not find our data.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NLTK_DATA=/app/nltk_data

# Document which port the app listens on. EXPOSE is metadata only — it does
# not actually publish the port. Publishing happens in docker-compose.yml via
# the `ports:` key or `docker run -p 8000:8000`.
EXPOSE 8000

# --reload watches /app/backend for file changes and restarts uvicorn
# automatically — great for development with the bind mount.
# For a production-only image, swap --reload for --workers 2 (or more).
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--reload-dir", "/app/backend"]
