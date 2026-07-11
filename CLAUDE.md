# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`ai-engineering-learn` is a personal learning project for AI engineering, structured as a six-phase curriculum in `lessons/` (phase-1 through phase-6): LLM fundamentals → RAG/MCP → orchestration & agents → security/guardrails → observability/evals → cost/latency + capstone. Code is written against that plan, so check the relevant `lessons/phase-N.md` for context on what's being built and why. Application code is still minimal (`main.py` is a hello-world), but the dependency stack for all phases is already installed: LiteLLM, LangChain/LangGraph, Langfuse, FastAPI, SQLAlchemy/Alembic, Qdrant, Neo4j, Temporal, Streamlit, structlog.

## Environment

- Managed by [`uv`](https://docs.astral.sh/uv/). Requires Python `>=3.14` (pinned via `.python-version`).
- Runtime deps in `[project.dependencies]`; dev tools (pytest, ruff, basedpyright, httpx) in the `dev` dependency group. `uv sync` installs both.

## Commands

- Run the app: `uv run main.py`
- Add a dependency: `uv add <package>` (dev tool: `uv add --group dev <package>`)
- Tests: `uv run pytest` (single test: `uv run pytest path/to/test.py::test_name`; async tests use `pytest-asyncio`)
- Lint: `uv run ruff check --fix .` — format: `uv run ruff format .`
- Type-check: `uv run basedpyright` (must run via `uv run` so it sees the project venv)
- All checks at once: `uv run pre-commit run --all-files`

## Backing services

Local infra (Postgres, Temporal + UI, Neo4j, Qdrant) runs via Docker Compose:

```
cp .env.tool.example .env.tool   # required before first `up`
docker compose -f docker-compose-tool.yml up -d
docker compose -f docker-compose-tool.yml down   # add -v to drop volumes
```

Ports: Postgres 5432, Temporal 7233 (UI at 8080), Neo4j 7474/7687, Qdrant 6333/6334. Gotcha documented in `.env.tool.example`: `POSTGRES_USER` must not be `temporal`, or Temporal's auto-setup silently skips creating its databases.

## LiteLLM proxy (LLM gateway)

All provider traffic goes through a LiteLLM proxy — the app never calls Anthropic/OpenAI directly (a Phase 1 acceptance criterion). It runs in its own compose file, separate from the backing-infra stack, so it can be restarted without bouncing the databases:

```
cp .env.proxy.example .env.proxy   # then fill in real provider + LangFuse keys
docker compose -f docker-compose-proxy.yml up -d
docker compose -f docker-compose-proxy.yml restart litellm   # after editing config.yaml
docker compose -f docker-compose-proxy.yml up -d --force-recreate  # after editing .env.proxy (env is only read at container creation, not on restart)
docker compose -f docker-compose-proxy.yml down
```

Config is `services/proxy/config.yaml` (secrets referenced via `os.environ/...`, never inline). Model groups: `primary` (Anthropic) → `fallback` (OpenAI) cross-provider failover, plus `embeddings` (OpenAI). LangFuse success/failure callbacks handle tracing + cost; the proxy is stateless (no spend DB). Port 4000; every request must send `Authorization: Bearer $LITELLM_MASTER_KEY`.

## Tooling conventions

- Ruff owns lint + formatting (config in `pyproject.toml`: line length 88, target py314, rules E/F/I/UP/B); basedpyright owns type-checking. Zed is configured (`.zed/settings.json`) to format on save with ruff and use both language servers — keep `pyproject.toml` the single source of truth for ruff settings.
- Pre-commit (`.pre-commit-config.yaml`) enforces the same on commit: hygiene hooks, `ruff --fix`, `ruff-format`, and basedpyright (run whole-project via `uv run`). Enable with `uv run pre-commit install` after cloning.
