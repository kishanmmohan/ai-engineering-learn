# AI Engineering Curriculum — Progress

## Current

- Phase: 1 — LLM Fundamentals (started 2026-07-09)

## Phase 1 — LLM Fundamentals

### Concepts (internalize)

- [ ] Tokens and context windows
- [ ] Messages structure / statelessness
- [ ] Sampling (temperature, top_p, max_tokens)
- [ ] Tool / function calling loop
- [ ] Structured outputs
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

## Session journal

<!-- - YYYY-MM-DD: one line -->
