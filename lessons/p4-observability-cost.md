# P4 · Observability & Cost

> **Production AI Learning Plan · Unit P4**

You can't fix what you can't trace — and tokens are your COGS. This unit covers tracing across the whole pipeline, per-request/per-tenant cost accounting, the prompt registry, and gateway operations (fallbacks, caching, rate limits).

**~1 week · Core · 3 lessons · Capstone Stage 4 · Exit check gates P5**

**On this page:** [4.1 Tracing](#41-tracing) · [4.2 Cost & the prompt registry](#42-cost--the-prompt-registry) · [4.3 Gateway operations](#43-gateway-operations) · [Capstone Stage 4](#capstone--stage-4--instrument-traces-unit-economics-and-an-outage-drill) · [Practice](#practice--hands-on-probes) · [Exit check](#exit-check)

---

## 4.1 Tracing

*A log line tells you a call happened. A trace tells you the story of a request.*

### Why logs aren't enough here

One user question fans out into many operations: embed query → vector search → rerank → assemble context → model call → maybe tool calls → maybe a judge. When the answer is wrong, "which step?" is the only question that matters — and flat logs can't answer it. You need the **tree**.

### Span anatomy

- A **trace** is one unit of work (one user request); **spans** are nested operations within it (retrieval, each tool call, generation), each with start/end, status, and attributes.
- Record at each span what you'd want at 2am: for retrieval — query, filters, chunk ids, scores; for generation — prompt version, model, token counts, stop reason, cost; for tools — arguments, result size, latency.
- **Inputs and outputs on the LLM span** are non-negotiable. The single most common production question is "what *exactly* did we send the model, and what came back?" A trace that omits them is a trace you'll curse.

### Correlation and sampling

- Thread a **session id** (conversation) and **user/tenant id** through every span. Debugging, per-tenant cost (§4.2), and abuse investigation all depend on this correlation.
- At volume, sample: keep a percentage of successful traces, but **keep 100% of errors and high-cost/high-latency outliers** — the tail is where the incidents live. Head-based uniform sampling throws away exactly what you need.

> **Systems analogy** — This is distributed tracing (you know Jaeger/OpenTelemetry) pointed at an LLM pipeline. The one new must-have is content capture: elsewhere you trace *that* a call happened; here you also need *what was said*, because the bug is usually in the words.

---

## 4.2 Cost & the prompt registry

*Tokens are COGS. An AI feature without a cost-per-request number is a feature you can't price, budget, or defend.*

### Cost accounting

- Compute cost per request from the usage block (P0 §0.5) and attach it to the trace. Aggregate by **feature, tenant, model, and prompt version** — those are the axes you'll actually be asked about.
- Know your **cost per successful answer**, not just per call: retries, judge calls, and failed tool loops all bill. A "cheap" feature with a 3× retry rate isn't cheap.
- **Budget alerts** on spend-per-tenant and spend-per-feature catch the runaway loop (P2) and the abusive tenant before the invoice does.
- The levers, ranked, all trace to P0 §0.5: cut input tokens (retrieval precision, prompt caching), cut output tokens (concise-output instructions, `max_tokens`), route cheaper models where evals (P3) prove they hold, cache (§4.3).

### The prompt registry

- Prompts live in a **registry**, versioned, resolved at runtime by label (`production`/`staging`) — not baked into code (P0 §0.3, P3).
- What it buys: **rollback in seconds** (flip the label, no deploy); an audit trail of who changed what when; the join key between a trace and the exact prompt text that served it; and the substrate for P3's promotion flow.
- The discipline: the prompt version is stamped on every trace. "Which prompt produced this bad answer?" must be a lookup, never a guess.

> **Systems analogy** — The registry is feature flags for prompts: decouple "what's deployed" from "what's active", so changing behavior and rolling it back are config operations, not releases. You already run production on this pattern.

---

## 4.3 Gateway operations

*One choke point for every model call turns cross-cutting concerns into config.*

### Why a gateway

Routing an LLM gateway (e.g., LiteLLM) between your app and providers gives you one place for the concerns that otherwise smear across the codebase:

- **Routing & fallback chains:** primary model 429s or 5xxes → automatically fail over to a secondary (same or different provider). Your app issues one logical call; the gateway handles provider reality.
- **Retries & timeouts:** centralized backoff on transient errors; per-call deadlines so a slow provider doesn't cascade. (Standard resilience — you know it; here it lives at the gateway.)
- **Caching:** exact-match caching for identical requests; semantic caching (embed the request, serve a cached answer if a near-duplicate exists) for FAQ-shaped traffic. Semantic caching trades a correctness risk (near ≠ same) for cost — measure it against evals before trusting it.
- **Rate/quota management:** stay under provider limits; enforce per-tenant quotas; queue or shed load rather than hard-failing.
- **Provider abstraction:** swap or add providers without touching app code — which also keeps your learning (and your system) provider-neutral.

### The trade-off

A gateway is one more hop and one more thing to run — it adds a little latency and becomes a critical dependency. For anything past a toy, the operational leverage is worth it; just size and monitor it like the critical path it now is.

> **Failure modes to internalize**
>
> - **Silent fallback quality drift** — failover to a weaker model "works" (no error) but answers degrade. Trace which model actually served, and eval the fallback.
> - **Semantic cache poisoning** — a near-match served as exact returns a subtly wrong answer. Tune the similarity threshold conservatively; log cache hits.
> - **Retry storms** — naïve retries against a struggling provider add load and deepen the outage. Backoff + circuit-break.

---

## Capstone · Stage 4 — Instrument: traces, unit economics, and an outage drill

Instrument your Stage-2 agent:

1. **Tracing:** spans for retrieval, each tool call, and generation — with query/filters/scores on retrieval and prompt-version/model/tokens/cost on generation. Thread session and user ids.
2. **Cost report:** a script that reports cost per request and per session, plus p50/p95 TTFT and total latency, from the traces.
3. **Outage drill:** configure a gateway fallback chain; simulate a primary-provider outage; confirm from the trace that failover happened and which model actually served.
4. **Diagnosis drill:** have someone (or a script) plant a change — e.g., top-k 8 → 40 — and find it from traces alone, without reading the diff.

> **Solid when:** you find the planted change from traces without reading the code, and you can quote your system's cost per query from memory.

**Tooling →** Langfuse (self-hostable) / Phoenix / LangSmith · LiteLLM for fallbacks & caching

---

## Practice — hands-on probes

1. Add tracing; open one trace and find the exact prompt sent and the raw model response.
   *Exit: the 2am question — "what did we send?" — is a click, not an archaeology dig.*
2. Attach cost to each trace; sum cost per session across a 5-turn conversation.
   *Exit: you can state your cost per answered question as a number.*
3. Instrument a retry path; force a transient error; confirm the retry and its added cost both show in the trace.
   *Exit: hidden retry cost, made visible.*
4. Put a gateway in front; configure a fallback; kill the primary; read which model served from the trace.
   *Exit: failover works — and you can prove which model answered.*
5. Turn on caching; replay an identical request; confirm the cache hit and the near-zero cost.
   *Exit: caching economics, demonstrated on your own traffic.*
6. Do the diagnosis drill: someone changes one parameter; you find it from traces only.
   *Exit: traces-as-first-debugging-surface, proven.*

---

## Exit check

*Answer each from memory, out loud. Tick a box only when you could defend the answer to a colleague. All six → start P5.*

- [ ] Why does a flat log fail where a trace succeeds for a RAG request? What must the LLM span always capture?
- [ ] You're sampling traces at volume. What do you keep at 100%, and why is uniform sampling a trap?
- [ ] What's the difference between cost-per-call and cost-per-answered-question, and why does the gap matter?
- [ ] Walk a prompt rollback through the registry. Why is it seconds, not a deploy?
- [ ] Name three things a gateway centralizes, and the new critical-dependency risk it introduces.
- [ ] Semantic caching cut your cost 40%. What's the failure mode you now have to watch, and how do you watch it?

---

*Unit P4 of the [Production AI learning plan](./learning-plan.md) · previous: [P3 — Evals](./p3-evals.md) · next: [P5 — Hardening & Scale](./p5-hardening-scale.md)*
