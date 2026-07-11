# syntax=docker/dockerfile:1
# FastAPI chat service. Build context is the repo root (needs pyproject.toml +
# uv.lock), so build via docker-compose-proxy.yml, not `docker build services/chat`.
#
# Astral's uv image bundles a pinned CPython, so uv + Python are pinned in one tag
# (matches local uv 0.11.28 / Python 3.14).
FROM ghcr.io/astral-sh/uv:0.11.28-python3.14-trixie-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Install dependencies first as a cached layer, from the lockfile only. This is a
# non-packaged ("virtual") project, so `uv sync` installs deps without needing the
# app source. README.md is copied because pyproject.toml references it.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# App source (only the chat service is needed to serve the API).
COPY services/chat ./services/chat

# Use the venv directly (uvicorn comes in via streamlit -> uvicorn).
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
# uvicorn inserts the cwd on sys.path, so `services.chat.src.main` resolves from /app.
CMD ["uvicorn", "services.chat.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
