# progress.md Format

Canonical schema for `lessons/progress.md`. Create it from this template on the
first session; keep the structure stable so any session can parse it.

## Rules

- Only the teacher checks items under **Gates** and **Acceptance criteria**,
  and only after verification per `gate-protocol.md`.
- Concept items may be marked `exposed` when taught, but `[x]` only after the
  learner passes the verify question (step 6 of the teaching exchange).
- Date everything (YYYY-MM-DD). Convert "yesterday/last week" to absolute dates.
- "Struggled with" entries are cleared (struck through with a cleared date)
  only after a successful reworded re-test.
- One journal line per session, appended at close.

## Template

```markdown
# AI Engineering Curriculum — Progress

## Current

- Phase: 1 — LLM Fundamentals (started YYYY-MM-DD)

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

<!-- copy the checklist from lessons/phase-1.md §4 -->

### Background threads

<!-- copy the checklist from lessons/phase-1.md §5 -->

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
```

Later phases: add a `## Phase N — <title>` section (same sub-structure, with
that phase's concept/criteria/exercise lists) when the phase starts, not before.
