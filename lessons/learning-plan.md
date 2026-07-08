# Production AI Engineering

> **AI Engineer Onboarding · General Curriculum**

A six-week curriculum for a senior backend engineer moving into AI engineering: 20 lessons with explicit topic coverage and 8 hands-on projects threaded through one evolving capstone. General concepts, tool-agnostic — specific codebases come after.

**~6 weeks · 20 lessons · 8 projects · 1 capstone thread**

## The route

Weight ≈ time investment.

| Phase | Title | Weight | Duration |
|---|---|---|---|
| [P0](#p0--llm-mechanics) | LLM Mechanics | fast pass | 2–3 days |
| [P1](#p1--production-rag) | Production RAG | **core** | ~1.5 weeks |
| [P2](#p2--agents--orchestration) | Agents & Orchestration | **core** | ~1 week |
| [P3](#p3--evals--the-discipline) | Evals — the Discipline | **core** | ~1.5 weeks |
| [P4](#p4--observability--cost) | Observability & Cost | **core** | ~1 week |
| [P5](#p5--hardening--scale) | Hardening & Scale | **core** | ~1 week |
| [P6](#p6--staying-current) | Staying Current | ongoing | — |

## What transfers and what changes

**Carries over from backend**

- Distributed systems & async I/O
- API design, queues, idempotency, retries
- Observability & capacity planning
- Multi-tenancy & data isolation

**The delta to internalize**

- Correctness is a distribution — tests become evals
- Failures are silent: confident wrong answers, not stack traces
- Cost & latency vary per request with input size
- The model is your least reliable component

## The capstone thread — one system, hardened progressively

Most projects below are stages of a single build: a **document QA system** over one dense technical PDF of your choice (a standards document, a hardware manual, a legal contract — anything ~100 pages with structure). You build it bare in P1, then each phase upgrades the same system. By P5 it's a portfolio-grade production artifact, built entirely on your machine with open tools. Cadence: lessons in the morning, project in the afternoon.

```
P1 BUILD → P2 AGENTIFY → P3 EVALUATE → P4 INSTRUMENT → P5 HARDEN
```

---

## P0 · LLM Mechanics

**Fast pass · 2–3 days**

*Just enough theory to reason about everything that follows — don't linger here.*

Full unit text with worked examples and exit check: [P0 deep-dive](./p0-llm-mechanics.md)

### Lessons & topics

- **L1 · Generation mechanics** — Tokens & BPE; context windows and "lost in the middle"; prompt caching and prefix ordering; temperature / top-p; the TTFT + n×TPOT latency model; stop reasons and truncation.
- **L2 · Embeddings** — Text → vector; cosine similarity; the blind spots — negation, exact identifiers, numbers/units, long-text mush; score calibration; the embedding model as a schema decision.
- **L3 · Prompting & structured output** — Message roles and trust boundaries; few-shot and format bias; chain-of-thought economics; specifying the failure path; JSON mode vs schema-constrained decoding; the validation boundary (e.g., Pydantic); the tool-calling loop.

### Projects

**Project A · Token Ledger — estimate-then-verify harness**

- CLI script: given a prompt file, *predict* tokens, cost, and latency from the provider's price sheet — then fire the call and diff prediction vs the actual usage block and measured TTFT.
- Run it against three call shapes: short chat, long-context QA, structured extraction.

> **Solid when:** your estimates land within ~25% on cost and latency for all three shapes.

**Project B · Structured Extractor — typed fields from messy text**

- Extract a typed model (enums, optional fields, units) from messy real-world text — an inspection report, a support ticket, an invoice; one validation-retry loop that feeds the error back.
- Include two adversarial inputs where the data is genuinely absent.

> **Solid when:** 10 varied inputs pass with zero unhandled validation errors — and the absent-data cases return honest nulls, not fabricated values.

### Objective

**Estimate the cost, latency, and likely failure modes of any LLM call before you run it.**

**Tooling →** any provider SDK, or a gateway like LiteLLM · a tokenizer (tiktoken / provider count-tokens API) · Pydantic

---

## P1 · Production RAG

**Core · ~1.5 weeks**

*Retrieval quality caps answer quality — most "model problems" are retrieval problems.*

Full unit text with worked examples and exit check: [P1 deep-dive](./p1-production-rag.md)

### Lessons & topics

- **L1 · Ingestion** — PDF parsing, OCR and VLM extraction for tables/figures; layout-aware chunking; chunk size and overlap trade-offs; metadata design; multi-tenancy — scoping every record and query by tenant.
- **L2 · Retrieval** — Dense vs sparse (BM25) vs hybrid search; metadata filters; cross-encoder reranking; query expansion and HyDE; top-k selection and context budgeting.
- **L3 · Grounding & graphs** — The citation contract; abstention ("not in the documents"); the failure taxonomy — attribute every bad answer to ingestion, retrieval, or generation; knowledge-graph basics; when graph traversal beats vector similarity.

### Project

**Capstone · Stage 1 — Build: document QA from scratch**

- Ingest your chosen PDF (~100 pages): parse, layout-aware chunking, metadata (section, page).
- Embed into a vector store; hybrid search (dense + BM25); grounded answers with page-level citations and an explicit abstention path.
- Write a failure log for five hard queries — negation, exact clause/section number, cross-reference, table lookup, out-of-corpus — attributing each to its pipeline stage.
- Stretch: add a reranker; measure before/after on 20 self-written queries.

> **Solid when:** 15 of 20 queries answered with correct citations, and every failure is attributed to a stage with evidence.

### Objective

**Build and debug a retrieval pipeline end-to-end; diagnose any bad answer to its pipeline stage.**

**Tooling →** Qdrant / pgvector / FAISS · rank-bm25 or built-in sparse vectors · a PDF parser (PyMuPDF, unstructured) · optional: Neo4j for the graph lesson

---

## P2 · Agents & Orchestration

**Core · ~1 week**

*An agent is a state machine with a probabilistic core — design for the loop, not the demo.*

Full unit text with worked examples and exit check: [P2 deep-dive](./p2-agents-orchestration.md)

### Lessons & topics

- **L1 · Agent architectures** — State machines for agents (e.g., LangGraph): state schemas, nodes and conditional edges, checkpoints and persistence; the workflow-vs-agent spectrum — when to give the model control flow, and when not to.
- **L2 · Tools & protocols** — Small, typed, idempotent tool design; tool descriptions are prompts; argument validation at the boundary; MCP as an open tool protocol.
- **L3 · Control & streaming** — Iteration caps and timeouts; graceful degradation when a tool or dependency is down; SSE token/event streaming; human-in-the-loop interrupts.

### Project

**Capstone · Stage 2 — Agentify: two-tool streaming agent**

- Wrap Stage-1 search as a typed tool; add a second tool (unit converter or calculator); build the agent graph with conditional routing and an iteration cap.
- Tool-failure drill: kill the vector store mid-run — the agent must degrade gracefully, not hallucinate an answer.
- HTTP endpoint streaming tokens and tool events over SSE; checkpointing — kill the process mid-run and resume.

> **Solid when:** it streams, survives a dead dependency honestly, and resumes from a checkpoint.

### Objective

**Ship an agent with tools, guardrails, and streaming — and know exactly what it does when a dependency fails.**

**Tooling →** LangGraph (or hand-rolled loop first — worth doing once) · FastAPI + SSE · MCP SDK optional

---

## P3 · Evals — the Discipline

**Core · ~1.5 weeks**

*Without evals you're deploying vibes. Evals are to AI what tests are to code — the single highest-leverage production skill.*

Full unit text with worked examples and exit check: [P3 deep-dive](./p3-evals.md)

### Lessons & topics

- **L1 · Gold sets** — Case design and coverage — happy path, edge, adversarial, abstention; annotation discipline; small-but-clean beats large-but-noisy; versioning gold sets like code.
- **L2 · Metrics & judges** — Citation precision, grounding ratio, hallucination rate, answer correctness; LLM-as-judge rubrics; position and verbosity bias; calibrating the judge against human labels before trusting it.
- **L3 · Gates & promotion** — CI regression gates; prompt lifecycle draft → staging → production with rollback; A/B comparison of variants; confidence thresholds and abstention tuning.

### Project

**Capstone · Stage 3 — Evaluate: gold set, judge, and gate**

- 25-case JSONL gold set for your QA system — include abstention and adversarial cases.
- Implement citation precision, grounding ratio, and hallucination rate with an LLM-as-judge; hand-label 15 cases and report judge–human agreement.
- Run two prompt variants through the harness → a promote/reject verdict; wire it as a CI gate (non-zero exit on regression).
- Plant a deliberate regression (e.g., weaken the grounding instruction) — the gate must catch it.

> **Solid when:** the planted regression is caught automatically, and judge–human agreement is ≥80% before you rely on it.

### Objective

**Never ship a prompt, model, or retrieval change without eval evidence.**

**Tooling →** hand-roll the harness first (JSONL + pytest) — you'll understand every eval tool after · then compare with promptfoo / Ragas

---

## P4 · Observability & Cost

**Core · ~1 week**

*You can't fix what you can't trace — and tokens are your COGS.*

Full unit text with worked examples and exit check: [P4 deep-dive](./p4-observability-cost.md)

### Lessons & topics

- **L1 · Tracing** — Span anatomy across retrieval → tools → generation; sessions and user attribution; what to record at each hop; sampling strategies for high-volume paths.
- **L2 · Cost & the prompt registry** — Token accounting per request, tenant, and feature; budget alerts; prompt registries — versioned prompts resolved at runtime by label, with instant rollback instead of redeploys.
- **L3 · Gateway operations** — LLM gateways (e.g., LiteLLM): routing tables, fallback chains, retries and timeouts, response caching, rate limits and quotas per provider.

### Project

**Capstone · Stage 4 — Instrument: traces, unit economics, and an outage drill**

- Instrument the Stage-2 agent with a tracing tool: spans for retrieval, each tool call, and generation, with session and user attribution.
- Cost report script: cost per request and per session; p50/p95 TTFT and total latency.
- Outage drill: configure a gateway fallback chain, simulate a primary-provider outage, verify the failover in traces.
- Diagnosis drill: have someone plant a change (e.g., top-k 8 → 40) — find it from traces alone.

> **Solid when:** you find the planted change from traces without reading the code, and you can quote your system's cost per query from memory.

### Objective

**Diagnose a production incident from traces alone; quote the unit cost of any feature.**

**Tooling →** Langfuse (self-hostable) / Phoenix / LangSmith · LiteLLM for fallbacks & caching

---

## P5 · Hardening & Scale

**Core · ~1 week**

*Where your ten years of backend experience compound hardest.*

Full unit text with worked examples and exit check: [P5 deep-dive](./p5-hardening-scale.md)

### Lessons & topics

- **L1 · Security** — OWASP LLM Top 10; direct and indirect prompt injection (poisoned documents); insecure output handling; tool allow-lists and spend caps; tenant isolation on every retrieval path.
- **L2 · Durability** — Durable execution (e.g., Temporal): workflows vs activities; idempotency keys; retry policies and heartbeats; backpressure; completion events.
- **L3 · Performance & degradation** — Latency budgets per hop; parallel tool fan-out; semantic caching; fallback models; partial answers with stated confidence.

### Project

**Capstone · Stage 5 — Harden: break it, defend it, make it durable**

- Attack: write 10 prompt-injection attempts against your agent — direct, and indirect via a poisoned chunk ("ignore previous instructions…" planted inside an ingested document).
- Defend: data/instruction delimiting, output validation, tool allow-list, iteration and spend caps. Write a one-page threat model.
- Durability: move ingestion into a durable workflow; inject a 30% failure rate into one step; prove retries work and re-runs create zero duplicates.

> **Solid when:** ≥8 of 10 attacks fail post-hardening, and ingestion completes through injected failures — run twice, no duplicate records.

### Objective

**Run an AI feature under an SLO, with a written threat model.**

**Tooling →** Temporal (single docker command) or Inngest · your Stage-2 agent as the attack target

---

## P6 · Staying Current

**Ongoing**

*The field moves monthly — build a filter, not a feed.*

Full unit text with practice and framework detail: [P6 deep-dive](./p6-staying-current.md)

### Lessons & topics

- **L1 · The reading loop** — Triage sources (papers, model releases, engineering blogs); replicate-small before adopting; benchmark skepticism — contamination, cherry-picking, apples-to-oranges comparisons.
- **L2 · Decision frameworks** — RAG vs fine-tuning vs distillation; build vs adopt; multimodal/VLM capability tracking; reasoning models and when test-time compute is worth paying for.

### Project

**Recurring · Tech Radar Memo — replicate small, decide with numbers**

- Each quarter: pick one technique (a new reranker, late-interaction retrieval, a judge method), replicate it small on your capstone system.
- Write a one-page build-vs-adopt memo: measured numbers, a recommendation, and a named kill-criterion.

> **Solid when:** the memo argues from your own measurements, not the paper's claims.

### Objective

**Make build-vs-adopt calls with evidence, not hype.**

**Sources →** arXiv & model release notes · provider changelogs & engineering blogs · your own capstone as the test bench

---

## Operating principles for production AI

1. **Evals are your unit tests.** No eval evidence, no merge.
2. **Traces are your logs.** Instrument before you debug.
3. **Prompts are code.** Versioned, reviewed, promoted, rolled back.
4. **Ground every answer.** A citation or an abstention — nothing in between.
5. **Tokens are money.** Know the unit economics of every feature.
6. **The model is the least reliable component.** Architect accordingly.

---

*General curriculum · concepts first — codebase-specific onboarding comes after · revise as the field moves*
