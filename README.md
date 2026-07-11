# AI Engineering Learn

A personal, hands-on curriculum for learning AI engineering — from raw LLM
primitives up to a production-hardened capstone system. Each phase is a
self-contained lesson plan with an outcome statement, concepts to internalize,
and projects to build; the code in this repo grows phase by phase.

The stack used throughout: LiteLLM, Langfuse, LangChain/LangGraph, Qdrant,
Neo4j, Temporal, FastAPI, and Streamlit.

## Curriculum

| Phase | Focus |
| --- | --- |
| [Phase 1 — LLM Fundamentals](lessons/phase-1.md) | Raw primitives against provider APIs — structured outputs, tool calling, streaming, embeddings — via a LiteLLM proxy, with every request traced and cost-attributed in Langfuse. |
| [Phase 2 — Retrieval + RAG + MCP](lessons/phase-2.md) | Production-shaped RAG over Qdrant (chunking, hybrid search, reranking, grounded citations), GraphRAG over Neo4j, and building/consuming MCP servers — the RAG pipeline itself becomes an MCP server. |
| [Phase 3 — Orchestration & Agents](lessons/phase-3.md) | Durable agentic systems: LangGraph state machines with checkpointing and human-in-the-loop, wrapped in Temporal workflows, with cost-aware model routing — and evidence for when an agent is the wrong answer. |
| [Phase 4 — Security & Guardrails](lessons/phase-4.md) | Threat modeling and defense in depth — input, output, and tool rails — plus systematic red-teaming of your own agent using the OWASP LLM Top 10. |
| [Phase 5 — Observability & Evals](lessons/phase-5.md) | Evaluation as a test suite: golden datasets, validated LLM-as-judge, RAG/agent metrics, and CI gating so a prompt or model change can't ship if it regresses quality. |
| [Phase 6 — Cost & Latency Engineering + Capstone](lessons/phase-6.md) | Prompt/semantic caching, cost-aware routing, token budgets, latency optimization against measured data — assembled into a capstone exercising the whole stack. |

Three background disciplines — **evals**, **security**, and **cost** — start in
Phase 1 and run through every later phase before getting their own deep dives.

## Getting started

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```sh
uv sync                                        # install deps (Python >=3.14)
cp .env.tool.example .env.tool                 # configure backing services
docker compose -f docker-compose-tool.yml up -d  # Postgres, Temporal, Neo4j, Qdrant
cp .env.proxy.example .env.proxy               # add provider + LangFuse keys
docker compose -f docker-compose-proxy.yml up -d # LiteLLM proxy (LLM gateway, :4000)
```

## Run the chat service

With the proxy up, start the FastAPI chat service (it reads the proxy master
key from `.env.proxy`, so load it into the shell first):

```sh
set -a; source .env.proxy; set +a                    # export proxy + provider keys
uv run uvicorn services.chat.src.main:app --reload   # http://localhost:8000
```

Then send a prompt — every `/chat` call is routed through the proxy:

```sh
curl -s localhost:8000/chat -X POST -H 'content-type: application/json' \
  -d '{"prompt": "In one word, reply: ok"}'
# -> {"reply":"Ok"}
```

Interactive API docs are at `http://localhost:8000/docs`.

Development commands and tooling conventions are documented in
[CLAUDE.md](CLAUDE.md).
