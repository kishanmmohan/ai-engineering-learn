# AI Engineering Curriculum — Progress

## Current

- Phase: 1 — LLM Fundamentals (started 2026-07-09)

## Phase 1 — LLM Fundamentals

### Concepts (internalize)

- [x] Tokens and context windows (2026-07-09)
- [x] Messages structure / statelessness (2026-07-09)
- [x] Sampling (temperature, top_p, max_tokens) (2026-07-09)
- [x] Tool / function calling loop (2026-07-09)
- [x] Structured outputs (2026-07-09)
- [ ] Streaming (SSE, TTFT)
- [ ] Failure handling (429s, backoff, timeouts)
- [ ] Prompt caching
- [ ] Context engineering, part 1
- [ ] Embeddings

### Acceptance criteria (teacher-verified)

- [ ] All traffic flows through the LiteLLM proxy; direct provider calls appear nowhere in app code
- [ ] Provider fallback works: kill the primary provider's key and requests transparently fail over
- [ ] `/extract` returns schema-valid JSON or a clean, typed error after N retries — never malformed output
- [ ] `/chat` streams; TTFT and total latency are both measured and logged
- [ ] Every request produces a LangFuse trace with token counts and cost attached (model pricing configured in LangFuse)
- [ ] The tool-calling loop handles a tool that throws an exception without crashing the conversation
- [ ] Prompt caching enabled on the stable system prompt; cache hits visible in traces

### Background threads

- [ ] Evals v0: golden dataset of 15–20 pairs for `/extract`, runner script, scores pushed to LangFuse
- [ ] First attack: injection embedded in an `/extract` document; one mitigation attempted; write-up on why it reduces but doesn't eliminate risk
- [ ] Cost & latency: cost-per-request per endpoint; TTFT vs total latency with/without streaming; prompt-caching cost delta recorded
- [ ] Instrumentation: LiteLLM → LangFuse logger wired; sessions on `/chat`; eval runner and attack attempts visible as traces/scores

### Break-it exercises

- [ ] 1. Blow the context window
- [ ] 2. Force invalid structured output
- [ ] 3. Rate-limit storm
- [ ] 4. Kill a stream mid-flight

### Gates (teacher-only)

- [ ] Failure demo presented and probed
- [ ] Closed-book self-assessment passed
- [ ] Acceptance criteria verified
- [ ] Teach-back deliverable done

## Struggled with

<!-- - YYYY-MM-DD: concept — the specific gap (cleared YYYY-MM-DD) -->
- 2026-07-09: pattern (not a single concept) — tends to answer the "what" correctly but leave the "why/mechanism" thin until pushed. Cleared within each concept via transfer questions, but keep asking "why, in terms of the mechanism?" — don't accept the label as the understanding.

## Session journal

<!-- - YYYY-MM-DD: one line -->
- 2026-07-09: Covered tokens & context windows (subword/BPE, content-type cost differences, window as validated hard cap, max_tokens stop_reason gotcha). First answer conflated tokenization granularity with context/hallucination — cleared same session via transfer questions.
- 2026-07-09: Covered messages structure & statelessness (no server session, full transcript resent per turn, state = recurring billable payload not just storage, shrink strategies summarize vs truncate both lossy). Solid grasp; named both shrink strategies unprompted.
- 2026-07-09: Covered sampling (distribution+sampler model, temp/top_p reliability dials, temp-0 non-determinism from FP non-associativity under batching = SAQ#1, greedy≠globally-valid JSON so validate+retry). Nailed the FP/hardware cause unprompted; "why" in mechanism terms was thin, filled in — watch for tendency to give the what without the mechanism.
- 2026-07-09: Covered tool/function calling loop (SAQ#3). Started with the classic "model executes the tool" misconception; corrected to schema-not-code, model-emits-requests-only, code-is-orchestrator, request/result matched pair resupplied every turn. Landed the full messages-array list on the transfer question. Strong finish.
- 2026-07-09: Covered structured outputs (SAQ#4). Nailed constrained-decoding mechanism (mask illegal tokens) unprompted from the sampling model. Distinguished native (enforcement) vs prompt-based (convention) failure modes; landed both transfer answers (hallucinated values + fallback provider not enforcing → validate regardless). Very strong.
- 2026-07-09: SESSION CLOSE — first session of Phase 1. Covered concepts 1–5 of 10 (tokens/context, statelessness, sampling, tool loop, structured outputs) including the two heaviest (tool loop, structured outputs). Answers strengthened over the session; ending reaching for failure-mode/validate-the-tail thinking unprompted. NEXT: concept #6 streaming (SSE, TTFT vs total latency, perceived latency as product decision).
