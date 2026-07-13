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
- [x] Streaming (SSE, TTFT) (2026-07-10)
- [x] Failure handling (429s, backoff, timeouts) (2026-07-10)
- [x] Prompt caching (2026-07-10)
- [x] Context engineering, part 1 (2026-07-10)
- [x] Embeddings (2026-07-10)

### Acceptance criteria (teacher-verified)

- [ ] All traffic flows through the LiteLLM proxy; direct provider calls appear nowhere in app code
- [ ] Provider fallback works: kill the primary provider's key and requests transparently fail over
- [ ] `/extract` returns schema-valid JSON or a clean, typed error after N retries — never malformed output
- [ ] `/chat` streams; TTFT and total latency are both measured and logged
- [ ] Every request produces a LangFuse trace with token counts and cost attached (model pricing configured in LangFuse)
- [ ] The tool-calling loop handles a tool that throws an exception without crashing the conversation
- [x] Prompt caching enabled on the stable system prompt; cache hits visible in traces (2026-07-11) — verified via trace: call 1 cache_creation=4691, identical call 2 cache_read=4691

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
- 2026-07-10: BUILD STARTED (ahead of concept track) — scaffolded services/chat/ with a FastAPI /health endpoint (commit f1a4671), i.e. the beginning of the /chat service from the Phase 1 build. Concept track is at #6 (streaming); build is not yet gated. Keep both tracks in view; acceptance criteria still unverified.
- 2026-07-10: Covered streaming (concept #6). First answer restated mechanism (multiple SSE events) instead of the benefit — same what-vs-why pattern; one redirect landed the insight (perceived vs actual latency). Solid on TTFT vs total latency decoupled + measured separately, product-decision rule (human-incremental→stream, machine-atomic→don't), stream-exposes-live-generation break. Landed the /extract transfer (can't validate partial JSON). Pattern to keep watching: reaches for the mechanism/label before the value.
- 2026-07-10: Covered failure handling (concept #7). First answer misattributed retry difficulty to statelessness (wrong shelf) — redirected to concept #3 (non-determinism) and landed it: retries give different output, can't dedupe by idempotency key, double-billing, and tool side effects make agent-loop retries dangerous. Nailed the transfer (agent-loop risky vs extract wasteful) crisply. Retry safety = property of what the call executed, not the call itself.
- 2026-07-10: Covered prompt caching (concept #8, SAQ#6 substantially). First answer got "input cached" but missed the prefix-ordering constraint (guessed "context overloaded" — wrong concept); derived "stable prefix first, variable last" cleanly after a where-in-the-prompt nudge. Solid on KV-cache prefix mechanism, write-premium/read-discount break-even, TTL locality, CDN-breaks-because-caches-input-not-output. Landed the timestamp-poisons-prefix transfer with the fix. What-vs-why pattern still present but self-correcting faster.
- 2026-07-10: Covered context engineering pt1 (concept #9). Strong intuition first try (wider pool → worse focus / hallucination); sharpened to the three named effects (attention dilution, lost-in-the-middle, distraction) and non-monotonicity (more true context can lower quality). Landed the curated-vs-verbatim transfer (B raises signal + positions fresh turns at high-attention end). Window-as-budget, curate-don't-fill; sets up Phase 2 RAG selectivity.
- 2026-07-10: Covered embeddings (concept #10, SAQ#7). Nailed synonym example (car/automobile) and topical-relatedness-not-sentiment misleading case (comfortable vs uncomfortable running shoes → high cosine); correct fix (re-ranking). Solid on text→vector, semantic vs lexical, cosine=angle/direction, topical≠relevant/true/agreeing, fuzzy-vs-explainable break. On-ramp to Phase 2 RAG.
- 2026-07-10: MILESTONE — all 10 Phase 1 concepts now covered. Concept track complete; build track has only /health scaffold so far. NEXT: build the workbench (4 endpoints), background threads (evals/attack/cost/instrumentation), break-it exercises, THEN the 3-part exit gate (failure demo + closed-book self-assessment + acceptance criteria verified). Concepts covered ≠ phase passed — gate still pending.
- 2026-07-10: Created lessons/phase-1-project.md — build brief (assignment, no code) with 6 sequenced milestones (M0 proxy+tracing → M1 /chat → M2 /extract → M3 /similar → M4 /agent-loop → M5 fallback), each tagged with the concepts it forces, plus acceptance criteria, background threads, break-it exercises, definition-of-done, and self-check gates. Learner will code it solo and bring walls to the teacher question-first.
- 2026-07-11: Build-guidance on the prompt-caching acceptance criterion (concept #8 already covered 7/10, so this was applying it, not re-teaching). Learner derived the solution from their own model: current /chat has no stable prefix (forwards client messages only) → fix = fixed system message at index 0; re-derived the minimum-cacheable-length floor from write-premium economics (landed prefix-not-role: cache span = start → cache_control breakpoint; system-only breakpoint ⇒ only system discounted, growing history re-billed full price every turn — connected it back to statelessness unprompted). One wrong-shelf slip early ("embed each message" — confused with embeddings/#10), corrected fast. Multi-breakpoint incremental conversation caching depth-stopped to Phase 6.
- 2026-07-13: IMPLEMENTED deliberate sampling temperature (concept #3, build side). Found the gap by inspection: both litellm.completion calls omitted temperature and config.yaml set none, so /chat had been running at Anthropic's default of 1.0 by omission, not by choice. Fix in ai_client.py: `CHAT_TEMPERATURE = float(os.environ.get("CHAT_TEMPERATURE", "0.7"))`, passed to both the streaming and non-streaming calls. Why 0.7: natural, varied conversational replies that stay coherent — deliberately below 1.0, and the intended contrast with the temperature=0 a future /extract endpoint needs for reproducible schema-valid output. Set temperature only, not top_p (tune one not both, as system_prompt.md itself states). Documented the rationale next to the constant + in README. No gate box — #3 is already checked on the concept track and has no separate acceptance-criteria checkbox.
- 2026-07-11: Build-guidance then IMPLEMENTED context engineering pt1 / history management (concept #9, build side; learner said "implement in the current codebase"). Question-first first: learner re-derived that the cached span runs start→`cache_control` breakpoint with all history strictly after it, so any history surgery (truncate or summarize) can't disturb the cached prefix — the two features are decoupled. Decision: TRUNCATE oldest turns (not summarize) — summarization would add an LLM round-trip per long turn (latency + spend + a non-deterministic failure path per #3/#7) to buy fidelity a workbench chat doesn't need. Impl in ai_client.py: `_fit_to_window` walks newest→oldest keeping turns under a token budget (`CONTEXT_WINDOW_TOKENS - OUTPUT_HEADROOM_TOKENS - system-prompt tokens`, all env-overridable so `CHAT_CONTEXT_WINDOW_TOKENS` low forces the drill), then drops a dangling leading assistant so the request stays Anthropic-valid; system prefix at front, freshest at end; `history_truncated` structlog line when turns drop. Verified against the real tokenizer: truncation fires under budget, guard keeps first turn = user, current turn always survives, default 200K window is a no-op. Ties back to #2 (statelessness → history is a growing billable payload) and #8 (front-truncation preserves the cache).
- 2026-07-11: IMPLEMENTED prompt caching (learner said "implement it", exited teaching frame). Correction to my teaching: the Haiku 4.5 minimum cacheable prefix is 4096 tokens, not the ~2048 I gave during the lesson (verified against Anthropic docs via the claude-api reference — 4096 for Haiku 4.5 / Opus 4.5–4.8, 2048 for Sonnet 4.6 / Haiku 3.x, 1024 for Sonnet 3.7–4.5). Two empirical findings that cost iterations: (1) the litellm SDK in proxy mode does NOT forward `metadata=` to the proxy body — cache_control/trace metadata must ride in `extra_body`; (2) a 1119-token then 2314-token system prompt cached NOTHING (0/0) because both were under the 4096 floor. Final impl: system prompt moved to services/chat/src/system_prompt.md (4311 tok, clears floor), loaded in ai_client.py, prepended as a `{cache_control: ephemeral}` system block. VERIFIED live: identical calls → call 1 cache_creation=4691, call 2 cache_read=4691, input dropped to 11. Acceptance criterion checked. Lesson for the learner: "marking cacheable ≠ caching; size gates it" was exactly right, and the exact floor is a provider fact to look up, not derive.
