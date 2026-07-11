# Phase 6 — Cost & Latency Engineering + Capstone (Caching, Routing, Budgets, Production Hardening)

## 1. Outcome Statement

At the end of this phase you can make an LLM system production-economical: prompt caching and semantic caching, cost-aware model routing, token-budget controls and load shedding, and latency optimization (streaming, parallelism, TTFT). Crucially, you optimize *against measured data* from your observability layer rather than by guessing. You then assemble everything into a single capstone system that exercises the whole stack, and you can speak to its cost, latency, quality, and security characteristics with numbers. You are production-ready.

## 2. Prerequisites

- Phase 5 exit gate passed. This phase is last on purpose: **optimization without measurement is guessing**, and you now have the measurement.
  - The full evaluated, secured Research Analyst agent, fully traced with cost/latency/quality data
  - Model routing basics from Phase 3 and the eval suite from Phase 5 — you'll optimize routing *and prove quality held* using the eval gate
  - Cost/latency numbers captured as background threads since Phase 1 — you have baselines to beat
- New setup: a semantic cache (GPTCache-style or a vector-DB-backed cache using your existing Qdrant), LiteLLM proxy budget/rate-limit features enabled, and a cost dashboard built from LangFuse data.

## 3. Concepts

### Internalize (reason from first principles)

- **Optimize against data, not vibes**: every optimization must be justified by a measured baseline and validated to not regress quality (via the Phase 5 eval gate) or security. This is the discipline that makes the phase safe — you already have the instruments.
- **The cost model of an LLM system**: input vs. output token pricing (output is usually far pricier), the multiplier effect of agent loops (N turns × context that grows each turn), retrieval context cost, and eval/judge cost. Be able to decompose a system's bill into its drivers and know which lever hits the biggest driver.
- **Prompt caching (provider-native)**: caching stable prefixes (system prompts, few-shot examples, large RAG context) so repeated tokens are billed at a fraction. What's cacheable, cache lifetime, how to structure prompts to maximize hits (stable content first), and the real savings math. (You enabled this in Phase 1; now optimize it deliberately.)
- **Semantic caching**: caching *responses* keyed by embedding similarity of requests, so near-duplicate queries skip the model entirely. The correctness risk (a cache hit on a subtly different query returns a wrong answer) and how to bound it with similarity thresholds and scope keys. When it's a huge win (FAQ-like traffic) vs. dangerous (high-variance, personalized, or freshness-sensitive queries).
- **Cost-aware model routing (deepened from Phase 3)**: right-sizing model per task and per step, cascade patterns (cheap first, escalate on validation failure — your rails and evals *are* the escalation signal), and quantifying the cost/quality frontier for your workload. Routing is where the largest sustained savings live.
- **Latency engineering**: streaming to cut *perceived* latency (TTFT is the number users feel), parallelizing independent tool/LLM calls, speculative/eager execution, prompt-size reduction, and choosing faster models on the critical path. Distinguish perceived from total latency and optimize each appropriately.
- **Budgets and controls (your backend wheelhouse)**: per-user / per-feature / per-tenant token budgets via the LiteLLM proxy, rate limiting, alerting on cost anomalies, and load shedding / graceful degradation under budget pressure (fall back to a cheaper model or a cached/canned response rather than failing). These map almost directly onto rate-limiting and capacity-planning patterns you already know.
- **The cost/latency/quality/safety quadrilemma**: every optimization trades among these four. Caching risks staleness; cheap models risk quality; aggressive rails add latency; skipping rails saves latency but adds risk. Being able to reason about the whole frontier — and defend a chosen operating point — is the capstone-level skill.

### Recognize (vocabulary + mental map, no depth)

- Inference-serving internals: batching, KV-cache, paged attention, speculative decoding at the serving layer — recognize; relevant if you ever self-host, out of scope here
- Self-hosting / open-weight economics (GPU cost, throughput, quantization tradeoffs) — recognize the decision framework, don't execute
- Fine-tuning / distillation as a cost lever (a small tuned model replacing a big prompted one) — recognize; this is the deliberately-skipped topic, know *when* you'd reach for it
- Provider batch APIs for offline workloads — recognize and use if a capstone path needs offline processing
- Edge/geographic routing and multi-region latency — recognize
- FinOps tooling for LLMs / commercial cost platforms — recognize; you're building the small version

### The one topic you deliberately skip
**Fine-tuning.** Know the decision framework — you fine-tune when prompting has plateaued on quality *and* a smaller tuned model would cut cost/latency at your volume *and* you have the eval suite to prove it helps (you now do). For this plan, the answer is almost always "don't, yet." Recognize when that changes; don't execute.

## 4. The Build — Optimize, Then Assemble the Capstone

**Stage A — Cost/latency optimization of the existing agent**
1. Build a **cost dashboard** from LangFuse data: cost per request/user/session, broken down by model and by agent step; latency percentiles with TTFT separated from total.
2. Decompose the bill, find the top cost driver, and attack it: optimize prompt-cache structure, add semantic caching where safe (measure hit rate and guard correctness with your eval set), and refine routing. **After each optimization, run the Phase 5 eval gate** to prove quality held and the Phase 4 security regression suite to prove safety held.
3. Add budget controls: per-user token budgets in the LiteLLM proxy, cost-anomaly alerting, and a load-shedding path (degrade to cheaper model / cached response under budget pressure).

**Stage B — The Capstone**
4. Assemble the full system as one coherent service and document it. It must exercise the entire stack:
   - **Agentic core** on LangGraph, made durable with Temporal (P3)
   - Calls your own **MCP server** exposing RAG over **Qdrant** with hybrid search + reranking + a GraphRAG path (P2)
   - Fronted by **LiteLLM** with **cost-aware model routing** (P3 + P6)
   - Wrapped in **input/output/tool guardrails** with human-in-the-loop for consequential actions (P4)
   - Fully **traced in LangFuse**, with an **eval suite gating changes in CI** (P5)
   - **Prompt/semantic caching, budgets, and a cost dashboard** (P6)
5. Write the capstone system-design doc and do a final failure demo covering the whole system.

### Acceptance criteria

- [ ] A cost dashboard exists showing cost broken down by model and agent step, plus latency percentiles with TTFT separated
- [ ] You identified the top cost driver with data and cut it measurably — with a before/after number
- [ ] Prompt caching is structured for high hit rate; hit rate and savings are measured
- [ ] Semantic caching is in place *where safe*, with a measured hit rate, a documented correctness guard, and a stated list of query types it must NOT cache
- [ ] Every optimization was followed by a green eval gate (quality held) and a green security regression suite (safety held) — no optimization shipped on cost grounds alone
- [ ] Per-user budget enforcement and a load-shedding/degradation path both work — demonstrated by driving a user over budget and watching graceful degradation, not failure
- [ ] The capstone runs end to end and exercises every prior phase's component
- [ ] A capstone system-design doc exists with a numbers table: cost/request, latency percentiles, eval scores, and security posture
- [ ] A whole-system failure demo: what breaks, blast radius, detection, mitigation, residual risk — across all layers

## 5. Background Threads Checklist

- [ ] **Cost & latency (this IS the phase)**: the thread becomes the subject. Meta-discipline going forward: cost and latency are continuously monitored properties, not a one-time optimization.
- [ ] **Evals**: the eval gate is now your optimization safety net — its job this phase is to catch cost optimizations that quietly degrade quality. Confirm it actually does by trying to sneak a quality-regressing "optimization" past it.
- [ ] **Attack**: the security regression suite is the *other* safety net — confirm no optimization (especially caching) opened a hole. A semantic cache, notably, can become a data-leakage vector across users if scoped wrong — test this explicitly.
- [ ] **Instrumentation**: the cost dashboard is instrumentation's final form. Ensure it's something you'd actually put in front of a team — this is the artifact that makes cost a shared, visible concern rather than a surprise invoice.

## 6. Break-It Exercises → Failure Demo

1. **Semantic-cache poisoning / mismatch**: find two queries similar enough to collide in the cache but different enough that the cached answer is wrong for the second. Tune the threshold; internalize that semantic caching trades correctness for cost and must be bounded.
2. **Cross-user cache leak**: deliberately mis-scope the semantic cache so one user's cached response is served to another. Watch a privacy incident happen in miniature, then fix the scoping. (This is a Phase 4 lesson resurfacing inside a Phase 6 optimization — optimizations create new attack surfaces.)
3. **Cheap-model quality cliff**: route more aggressively to the cheap model to save cost, then watch the eval gate catch the quality drop. Find the point where savings stop being worth it — with numbers.
4. **Budget exhaustion**: drive a user past their token budget mid-agent-run. Verify graceful degradation (cheaper model / cached / queued) rather than a hard crash or a half-finished durable workflow stuck forever.
5. **Latency vs. safety**: measure how much latency your Phase 4 rails add, then try removing the expensive one on the critical path. Quantify the latency win against the security loss — and decide the operating point deliberately, not by default.

**Failure demo (exit-gate component #1) — whole-system post-mortem**: this is the capstone demo. Walk the entire system's failure modes across all six phases' concerns — retrieval, agent loops, durability, security, evals, cost — with blast radius, detection signal, mitigation, and residual risk for each. This is your graduation.

## 7. Self-Assessment Questions (exit-gate component #2 — closed book)

1. Decompose the bill of an agentic RAG system into its cost drivers. For a given workload, which lever hits the biggest driver, and why is output-token cost usually where you look first?
2. Prompt caching vs. semantic caching: what does each cache, what does each save, and what distinct correctness/staleness risk does each carry?
3. When is semantic caching a large win and when is it dangerous? Give a query type you would never semantically cache and explain the failure.
4. You want to route more traffic to a cheaper model. Walk through how you decide how far to push it *safely*, using your eval gate and security suite as the guardrails on the optimization itself.
5. Perceived vs. total latency: what's the difference, why does TTFT dominate perceived latency, and which optimizations target which?
6. Design per-tenant budget enforcement with graceful degradation. What are the degradation tiers, and how do you avoid a durable Temporal workflow getting stuck when a budget runs out mid-run?
7. The cost/latency/quality/safety quadrilemma: pick two optimizations and describe exactly what each one trades away. How do you defend a chosen operating point to a skeptical team?
8. An optimization is a new attack surface — explain using the cross-user semantic-cache leak. What class of optimizations warrants a security review, not just an eval run?
9. When would you actually reach for fine-tuning, and what must your eval and cost data show first for that to be a defensible decision rather than a resume-driven one?
10. **Capstone integration question**: trace a single request through your entire capstone — proxy, routing, cache check, guardrails, agent loop, MCP/RAG, durability, tracing, cost accounting — and name what could fail at each stage and what catches it.

**Exit-gate component #3:** all acceptance criteria checked, capstone running. Final spaced review: re-answer one flagship question from *each* prior phase from memory (P1 Q2, P2 Q1, P3 Q1, P4 Q3, P5 Q1) — if all five are solid, the plan has done its job.

## 8. Teach-Back Deliverable

Two artifacts:
1. A focused cost/latency doc: **"Making an LLM agent production-economical"** — the bill decomposition, each optimization with before/after numbers, the caching correctness guards, and the quadrilemma operating-point defense.
2. **The capstone system-design document** — the portfolio centerpiece. Full architecture, every major decision with rejected alternatives (ADR-style), the numbers table (cost, latency, eval scores, security posture), and an honest "known limitations and what I'd do at 100× scale" section. This is the document you bring to your next project's first design review. Write it to be the strongest single evidence that you are a production-ready AI engineer — because it is.

## 9. Depth Stops

- **Inference-serving internals**: recognize batching/KV-cache/paged-attention. Do not go into serving-layer engineering unless you self-host — out of scope.
- **Self-hosting economics**: understand the decision framework; do not stand up GPU inference for this plan.
- **Fine-tuning**: recognize the decision criteria only. Do not fine-tune anything — it's the deliberately-skipped topic; executing it is a separate learning project.
- **Semantic cache sophistication**: threshold + scoping + correctness guard is enough. Do not build an adaptive/learned cache policy — recognize-level.
- **FinOps tooling**: your LangFuse-based dashboard is the ceiling. Commercial cost platforms — recognize-level.
- **Capstone gold-plating**: the capstone must *exercise* every component convincingly, not be a shippable product. No production infra rabbit holes (k8s, multi-region, CI/CD beyond the eval gate). Integration and the numbers table are the deliverable — resist the urge to make it a startup.

## 10. Curated Resources (max 5)

1. **Provider prompt-caching docs (Anthropic + OpenAI)** *(primary)*: what's cacheable, how to structure prompts, the savings math — from the source.
2. **LiteLLM docs — budgets, rate limits, caching, and routing**: the proxy features for Stage A's controls and cost tracking.
3. **A semantic-caching guide** (GPTCache docs or an equivalent practitioner write-up): implementation plus the correctness/scoping pitfalls.
4. **LangFuse docs — cost tracking, model pricing config, and dashboard/metrics**: to build the cost dashboard from data you're already collecting.
5. **One high-signal "LLMs in production: cost & latency" practitioner write-up**: for the whole-system optimization mindset and the quadrilemma framing, from someone who ran the invoice.

---

## Plan complete

Six phases, one system that grew from a raw-SDK workbench into a durable, secured, evaluated, cost-optimized agentic RAG platform:

1. **Fundamentals** — primitives + LiteLLM + tracing (the workbench)
2. **RAG + MCP** — Qdrant, GraphRAG, your own MCP server
3. **Orchestration** — LangGraph + Temporal agents, routing, agent context
4. **Security** — threat modeling, defense-in-depth rails, red-teaming
5. **Evals** — golden datasets, validated judges, CI gating, the online loop
6. **Cost/latency + capstone** — caching, budgets, and the assembled system

The three disciplines — evals, security, cost — ran as background threads from Phase 1 so that by the time each got its dedicated phase, you were formalizing a habit rather than starting cold. The exit gates (working artifact + failure demo + closed-book questions + spaced review of prior phases) are the backbone that replaces the calendar. Progress when the gate passes; the capstone assembles itself because every build extended the last.
