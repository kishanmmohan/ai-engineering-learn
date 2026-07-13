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

`POST /chat` takes the full conversation history (`messages`) and streams the
reply back as Server-Sent Events — one `data:` line per token delta, then a
`[DONE]` sentinel — routed through the proxy. `curl -N` disables buffering so
tokens arrive live; `-D -` prints the response headers:

```sh
curl -sN -D - localhost:8000/chat -X POST -H 'content-type: application/json' \
  -d '{"messages": [{"role": "user", "content": "In one word, reply: ok"}]}'
# X-Trace-Id:   <hex>          <- find this request in LangFuse
# X-Session-Id: <hex>          <- resend as "session_id" next turn to keep the session
# -> data: {"delta": "Ok"}
#    data: [DONE]
```

The endpoint samples at a deliberate `temperature=0.7` (env-overridable via
`CHAT_TEMPERATURE`) — natural, varied replies that stay coherent, chosen on purpose
rather than inheriting the provider default of 1.0; a structured endpoint like
`/extract` would instead pin it to `0` for reproducible, schema-valid output.

Every request is one LangFuse trace: token counts + cost from the proxy, plus
two NUMERIC scores the service measures and attaches — `ttft_ms` (time to first
token) and `total_latency_ms`. The server is stateless, so a multi-turn client
resends the whole `messages` list each turn and reuses the `X-Session-Id` it got
back, which groups the turns into one LangFuse session.

A fixed system prompt (`services/chat/src/system_prompt.md`) is prepended as a
cacheable prefix (Anthropic `cache_control`), so its tokens are written to cache
once and re-read at ~0.1× cost on later turns — watch `cache_read_input_tokens`
climb in the trace. It's deliberately long: Anthropic won't cache a prefix below
its minimum (4096 tokens for Haiku 4.5), so a short prompt would never hit.

Because the service is stateless, the resent history only grows. When it nears the
context window the server **truncates the oldest turns** to fit, keeping the system
prefix at the front and the freshest turns at the end (`_fit_to_window` in
`ai_client.py`). Truncation is chosen over summarization to avoid an extra LLM call
per long turn (latency, cost, a non-deterministic failure path); trimming only the
history — which sits after the cache breakpoint — leaves the cached prefix intact.
Set `CHAT_CONTEXT_WINDOW_TOKENS` low (e.g. `4600`) to force truncation on a short
conversation; a `history_truncated` log line reports how many turns were dropped.

Interactive API docs are at `http://localhost:8000/docs`.

## Structured extraction (`POST /extract`)

`POST /extract` takes raw `text` plus a `json_schema` and returns JSON that
**validates against that schema** — or, when the model can't produce valid output
within a retry budget, a clean typed error (a `422` with an `ExtractError` body,
never malformed JSON and never a 500 stack trace):

```sh
curl -s -D - localhost:8000/extract -X POST -H 'content-type: application/json' -d '{
  "text": "Ada Lovelace was 36.",
  "json_schema": {"type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"], "additionalProperties": false},
  "mode": "native"
}'
# X-Trace-Id: <hex>                 <- find this request (and its retries) in LangFuse
# -> {"name": "Ada Lovelace", "age": 36}
```

It is **not streamed**: the consumer is a machine that must validate the whole
payload against the schema before using any of it, so a half-arrived JSON object is
unparseable — there is nothing to stream toward. It samples at `temperature=0`
(env `EXTRACT_TEMPERATURE`): greedy decoding takes the arg-max token each step,
which minimises excursions into the low-probability regions where malformed tokens
live and makes a given failure reproducible. Greedy decoding still doesn't guarantee
valid structure, which is exactly why the result is validated and retried rather
than trusted.

Extraction runs one of two ways, chosen per request via `mode` (default
`EXTRACT_DEFAULT_MODE`, `native`):

- **`native`** — sends a `response_format` json_schema. The proxy translates it
  per provider: `primary` (Anthropic) becomes a forced tool call (server-side JSON
  enforcement), the `fallback` (OpenAI) uses strict json_schema. Note `drop_params:
  true` in `config.yaml` can silently drop the param on an unsupported path.
- **`prompt`** — no `response_format`; the schema is embedded in the prompt with a
  "return only JSON" instruction. Enforcement is nothing but the model's obedience.

Both modes exist so Break-It #2 can compare their failure **rates** on the same
adversarial input. Either way the parsed result is validated with `jsonschema`; on a
parse or validation failure the error is fed back into the messages and the model is
re-prompted up to `EXTRACT_MAX_RETRIES` times (default `2` → 3 attempts total). At
`temperature=0` a bare retry re-rolls nearly the same output, so it's the fed-back
error — not the retry count — that changes the next attempt; hence a small N.

A malformed input `json_schema` is rejected up front (`kind: "bad_schema"`, no model
call). To watch the **retry loop fire in a trace**, grab the `X-Trace-Id` header and
run `uv run python services/proxy/verify_trace.py --trace-id <id>` — each attempt is
a separate generation under the one trace, and the run carries `extract_attempts` /
`extract_outcome` scores. Force the typed-error path with `EXTRACT_MAX_RETRIES=0`
and adversarial input.

## Similarity search (`POST /similar`)

`POST /similar` embeds a query and returns the top-k most similar documents from
a small (~50-doc) in-memory corpus (`services/chat/src/corpus.py`), ranked by
**cosine similarity computed by hand** (`cosine_similarity` in `similar.py` — no
`scipy`/`sklearn` one-liner). The corpus is embedded **once at startup** (a single
batched call, warmed by the app's lifespan handler); each request embeds only the
query:

```sh
curl -s -D - localhost:8000/similar -X POST -H 'content-type: application/json' \
  -d '{"query": "which language is best for data science?", "k": 3}'
# X-Trace-Id: <hex>   <- find the embedding call (tokens + cost) in LangFuse
# -> {"query": "...", "matches": [{"index": 0, "score": 0.62, "text": "Python is ..."}],
#     "query_tokens": 8, "estimated_cost_usd": 1.6e-07, "corpus_tokens": 1023}
```

**Tokens & cost (#1).** Every embedding call logs its token count and an estimated
USD cost (`corpus_embedded` at startup, `query_embedded` per request); the proxy's
LangFuse callback records the authoritative cost. The corpus is ~50 one-sentence
docs of ~20 tokens each, so the one-time embedding is ≈ 1,000 tokens; at
`text-embedding-3-small`'s $0.02 / 1M tokens that is ≈ **$0.00002**. Check the paper
estimate against the trace with `uv run python services/proxy/verify_trace.py
--trace-id <id>`.

**The trap (self-check).** The corpus seeds a *trap pair* — two docs on the same
topic with opposite sentiment (a firmware update that *helped* vs. *hurt* battery
life, `corpus.TRAP_PAIR`). Query the topic neutrally:

```sh
curl -s localhost:8000/similar -X POST -H 'content-type: application/json' \
  -d '{"query": "phone battery life after the firmware update", "k": 2}'
# -> both the positive AND the negative doc come back with near-identical scores
```

Both rank at the top because the embedding encodes *topical and lexical
proximity*, not truth or sentiment: the two sentences differ in only a few tokens
("two full days / best" vs. "half a day / worst"), so their vectors are close and
cosine is high — a high-similarity result that is the **wrong answer**. Cosine
cannot be tuned to separate them; the fix is a **second stage** over the top
candidates — a cross-encoder reranker, a stance/sentiment filter, or an
LLM-as-judge — which is exactly what Phase 2's `/ask` (retrieve-wide-then-rerank)
introduces.

## Agent loop (`POST /agent-loop`)

`POST /agent-loop` answers a query with **a hand-rolled tool-calling loop — the
model requests, our code executes** (`run_agent_loop` in `agent_loop.py`; no
framework). Two tools are advertised: `calculator` (safe arithmetic, evaluated via
an AST whitelist — never `eval`) and `weather` (a deterministic stub). The
orchestrator sends the tool schemas, detects when the model wants a tool, **runs it
itself**, appends the result to the transcript, and resends — until the model emits
a final answer with no tool call:

```sh
curl -s -D - localhost:8000/agent-loop -X POST -H 'content-type: application/json' \
  -d '{"query": "What is 47 * 89, and what is the weather in Paris?"}'
# X-Trace-Id: <hex>   <- every iteration is one generation under this single trace
# -> {"answer": "47 × 89 = 4,183 ... Paris: 18°C, light rain", "iterations": 2,
#     "steps": [{"tool": "calculator", "ok": true, "result": "{\"result\": 4183.0}"},
#               {"tool": "weather", "ok": true, "result": "..."}]}
```

**The tool loop (#4).** Who does what is the whole lesson: *we* define the schemas,
the *model* decides which tool to call and with what args, *our code* executes it,
and the model only ever sees the `tool` result we append — it runs nothing. A tool
request is just sampled text, so it's **validated before execution** (unknown tool
name or un-parseable args are rejected and fed back as a structured error, not
trusted). The loop is **capped** (`AGENT_LOOP_MAX_ITERATIONS`, default 6); a model
that never stops asking for tools gets a typed `422` (`kind: "max_iterations"`),
not an infinite spend.

**Failure handling (#7) — the self-check.** One tool can throw: ask for a division
by zero and watch the conversation *survive* it —

```sh
curl -s localhost:8000/agent-loop -X POST -H 'content-type: application/json' \
  -d '{"query": "Use the calculator to compute 10 divided by 0."}'
# -> HTTP 200; the step is {"ok": false, "error": "{\"error\": \"ZeroDivisionError: ...\"}"}
#    and the model recovers with a graceful final answer — not a 500
```

The tool's exception is caught, serialized, and returned to the model as the tool
result; it reads the error and explains it instead of crashing the loop. *If a tool
throws, does the conversation survive — and where does the model's tool request get
validated before execution?* (`_execute_tool` in `agent_loop.py`.) This raw loop is
the foundation Phase 3's LangGraph is "just a state machine around."

## Chat UI

A Nuxt frontend (Claude/ChatGPT-style: streaming replies, markdown, multi-turn)
lives in [`services/chat-ui/`](services/chat-ui/). It never calls the backend from
the browser — its Nitro server proxies `/api/chat` to the chat service, so there's
no CORS and the backend stays unexposed. For local dev against a running backend:

```sh
cd services/chat-ui && pnpm install
CHAT_API_URL=http://localhost:8000 pnpm dev   # http://localhost:3000
```

## Run the full chat app (Docker)

`docker-compose-proxy.yml` runs the whole app — LiteLLM gateway, FastAPI backend,
and Nuxt UI — wired together over the compose network (`chat-ui → chat → litellm`):

```sh
cp .env.proxy.example .env.proxy                        # then fill in real keys
docker compose -f docker-compose-proxy.yml up -d --build
open http://localhost:3000                              # the chat UI
```

Only the UI (`:3000`) and the gateway (`:4000`) are published to the host; the
backend is reachable only inside the network at `http://chat:8000`. After changing
app code, rebuild just the app: `docker compose -f docker-compose-proxy.yml up -d
--build chat chat-ui`.

Development commands and tooling conventions are documented in
[CLAUDE.md](CLAUDE.md).
