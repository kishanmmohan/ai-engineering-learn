# P0 · LLM Mechanics — the Fast Pass

> **Production AI Learning Plan · Unit P0**

Four ideas — generation, embeddings, prompting, structured output — taught through the systems concepts you already hold. General concepts, any provider: everything in P1–P5 stands on this unit.

**2–3 days · 4 topics + pre-flight math · 6 practice tasks · Exit check gates P1**

**On this page:** [0.0 The mental model](#00-the-mental-model-a-stateless-function-with-a-sampler) · [0.1 Generation](#01-generation-tokens-context-sampling-latency) · [0.2 Embeddings](#02-embeddings-meaning-as-geometry) · [0.3 Prompting](#03-prompting-the-api-contract) · [0.4 Structured output](#04-structured-output--tool-calling) · [0.5 Pre-flight math](#05-pre-flight-math-cost-latency-failure) · [Practice](#practice--hands-on-probes) · [Exit check](#exit-check)

---

## 0.0 The mental model: a stateless function with a sampler

*Get this one abstraction right and most LLM behavior stops being surprising.*

An LLM is a pure, stateless function: it takes a sequence of tokens and returns a *probability distribution* over the next token. Generation is that function in a loop — sample a token, append it, call again — until a stop condition. That's the whole machine.

- **Stateless:** the model retains nothing between calls. "Conversation memory" is an illusion created by the client re-sending the entire transcript on every call.
- **Probabilistic:** the output is a *sample* from a distribution, not a lookup. Correctness is a rate, not a boolean — which is why testing becomes evals (P3).
- **No self-knowledge:** the model can't inspect its own confidence reliably, can't tell you what it doesn't know, and completes plausible-looking text even when wrong. Hallucination is the default behavior, not a bug.

> **Systems analogy** — Treat the model like an unreliable downstream service with no SLA on correctness: idempotent, stateless, occasionally wrong with HTTP 200. Everything you know about defending against flaky dependencies — validation at the boundary, retries, timeouts, fallbacks, circuit breakers — applies directly. That's most of P5.

---

## 0.1 Generation: tokens, context, sampling, latency

*Tokens are the unit of cost, latency, and limits — learn to think in them.*

### Tokens

- Models read **subword units** (byte-pair encoding), not words or characters. Rule of thumb for English prose: **1 token ≈ 4 characters ≈ 0.75 words**. Code and JSON tokenize denser (~3 chars/token); numbers split arbitrarily — one reason LLMs are unreliable at arithmetic.
- Everything is metered in tokens: pricing (input and output priced *separately* — output is typically ~5× dearer), rate limits, and the context window.

### Context window

- The hard cap on **input + output tokens per call**. It is not RAM — attention cost grows roughly quadratically with sequence length, so long context costs more and is slower.
- **"Lost in the middle":** models recall the start and end of a long context better than the middle. Stuffing 50 chunks into context is not retrieval — it degrades quality while raising cost. This motivates all of P1.
- Because the transcript is re-sent every turn, a conversation's *cumulative* token spend grows roughly **quadratically** with turn count. Long-running chats and agent loops need history management (truncation, summarization).
- **Prompt caching:** providers cache a stable prompt *prefix* — cached input tokens are heavily discounted and faster. Design consequence: static content (system prompt, tool definitions) goes first and never churns; volatile content (retrieved chunks, user question) goes last.

### Sampling

- **Temperature** rescales the distribution before sampling: 0 ≈ always pick the argmax (use for extraction/classification); higher values flatten it (use sparingly, for variety).
- **Top-p (nucleus)** truncates the distribution to the smallest set of tokens covering probability mass p. Tune temperature *or* top-p, not both.
- **Temperature 0 is not determinism.** Batching, floating-point non-associativity, and mixture-of-experts routing all introduce run-to-run variance. Never build on the assumption that the same input yields the same output — build evals instead.

### The latency model

Two phases with different physics: **prefill** (process the whole input; sets time-to-first-token) and **decode** (emit one token at a time).

```
latency ≈ TTFT(input_tokens) + output_tokens × TPOT

TTFT  time to first token — grows with input size; ~0.5–2s typical
TPOT  time per output token — model-dependent; ~10–50ms each
```

Output length dominates wall-clock time: 400 output tokens at 25ms each is 10 seconds *after* the first token. That's why token streaming exists: perceived latency collapses to TTFT. It's also why "be concise" in a prompt is a latency *and* cost optimization.

> **Failure modes to internalize**
>
> - **Truncation:** hitting `max_tokens` stops generation mid-thought — and silently corrupts JSON output. Always check the stop reason.
> - **Context overflow:** input too large → hard API error. Budget context before the call, not after the 400.
> - **Long-context degradation:** no error at all — answers just quietly get worse. Only evals catch this.

---

## 0.2 Embeddings: meaning as geometry

*The foundation of retrieval — and the source of its most surprising failures.*

An embedding model maps text to a fixed-dimension vector (typically 1,024–3,072 floats), trained so that semantically similar texts land close together. Similarity is measured with **cosine similarity** (a normalized dot product); "search" becomes nearest-neighbor lookup in vector space — the job of a vector database.

> **Systems analogy** — An embedding is a learned index key: a locality-sensitive hash for *meaning*, where collisions are the feature. And like any index, it answers exactly one query shape fast — "what's semantically nearby" — and nothing else.

### What the geometry can't capture

- **Negation blindness:** "include stainless fasteners" and "exclude stainless fasteners" embed almost identically — same topic, opposite meaning. Retrieval happily returns the wrong one.
- **Exact identifiers:** clause numbers, part codes, "Section 4.2.1" — semantic proximity is the wrong tool for exact-match needs. This is *the* argument for hybrid search (BM25 + vectors) in P1.
- **Numbers and units:** "30 MPa" vs "4,350 psi" — numerically related, geometrically unrelated.
- **Long text turns to mush:** embedding a 10-page document averages its meanings into a vector near nothing in particular. This is why chunking exists — the embedding is only as sharp as the chunk.

### Operational properties

- **Scores are relative, not absolute.** A cosine similarity of 0.83 means nothing across models or corpora. Thresholds must be calibrated empirically — per model, per collection.
- **The embedding model is a schema decision.** Vectors from different models are incompatible; switching models means re-embedding the entire corpus. Treat it like a database migration, with the same reluctance.
- **Queries and documents are asymmetric.** Modern embedders encode a short question and a long passage differently (instruction-prefixed modes) — use the right mode per side.

---

## 0.3 Prompting: the API contract

*Prompts are interfaces, not incantations — engineer them like one.*

### Roles and structure

- A call is a **message array**: a `system` message (your contract: role, rules, output format, refusal behavior) plus alternating `user` / `assistant` turns. The full array is re-sent on every call.
- **Security framing from day one:** the system prompt is trusted configuration; user content — and anything retrieved into context — is untrusted input. The model cannot reliably tell instruction from data, which is what makes prompt injection possible (P5).
- Delimit data explicitly: put retrieved evidence in clearly labeled blocks, and make the contract explicit — answer *only* from those blocks, with citations, or say the answer isn't there.

### Techniques that actually move accuracy

- **Few-shot examples** beat abstract instructions. The model imitates the *format and style* of examples aggressively — a wrong example does more damage than a wrong instruction.
- **Chain-of-thought** ("work through this step by step") trades output tokens — cost and latency — for accuracy on multi-step problems. Reasoning models internalize this trade; you pay for it as "thinking tokens".
- **Specify the failure path.** Tell the model what to do when it can't comply: "if the context doesn't contain the answer, say so." An unspecified failure path is how you get confident fabrication.
- **Anti-patterns:** the junk-drawer prompt (every incident adds a rule, nothing is ever removed or re-tested); incantations ("be very accurate"); examples that contradict instructions — examples win.

### Prompts are code

- Versioned, reviewed, evaluated before promotion, rolled back when they regress. A prompt edit can regress behavior as badly as a code change — but nothing fails loudly. Only evals (P3) catch it.
- Mature systems don't hardcode prompts: they live in a **prompt registry** (e.g., Langfuse) and resolve at runtime by label — `production`, `staging`. Promotion and rollback become registry operations, not redeploys.

---

## 0.4 Structured output & tool calling

*Where LLM output stops being prose and starts being data your code depends on.*

### Getting data out

- **JSON mode** guarantees syntactically valid JSON — nothing more. **Schema-constrained output** (structured outputs / grammar-constrained decoding) guarantees shape too. Neither guarantees the *values* are right.
- The robust pattern: define a typed model (e.g., **Pydantic**), derive the JSON schema from it, pass that to the model, then validate the response against it. On validation failure, retry once with the error message fed back — then fail loudly.
- Validation is the boundary between probabilistic and deterministic code. Everything downstream of a validated object is normal engineering again.

### Schema design rules

- Small and flat beats deep and clever. Every required field is pressure on the model to fill *something* — over-constrained schemas produce confident junk.
- **Field descriptions are prompts.** The model reads them. Write them as instructions, with the same care.
- Prefer enums over free strings; prefer `optional` over `required` when absence is legitimate — give the model an honest way to say "not present".

### Tool calling is a protocol, not magic

The model never executes anything. It emits a structured request — tool name plus JSON arguments — your code executes it, appends the result to the transcript, and calls the model again. That loop is the entire basis of agents (P2) and of open tool protocols like MCP.

> **Systems analogy** — Tool calling is RPC where the caller is untrusted. The model can request the wrong tool, with wrong arguments, at the wrong time. Validate arguments like you'd validate a public API request — because that's what it is.

> **Failure modes to internalize**
>
> - Valid JSON, wrong semantics — schema passes, values are fabricated. Only evals catch it.
> - Hallucinated enum values and unit mix-ups (psi vs MPa) in extraction work.
> - Truncation mid-JSON when `max_tokens` is too tight for the schema — budget output size from the schema, not vibes.
> - Tool-loop runaways — the model keeps calling tools without converging. Cap iterations, always (P2).

---

## 0.5 Pre-flight math: cost, latency, failure

*The unit's objective, made mechanical — run this in your head before any call.*

```
cost    = in_tokens × in_price  +  out_tokens × out_price
          (cached prefix tokens billed at a steep discount)
latency ≈ TTFT(in_tokens) + out_tokens × TPOT
failure = truncation | overflow | invalid-JSON | ungrounded answer | provider 429/5xx
```

### Worked example — one grounded QA call

A question answered over retrieved document context. Illustrative rates: $3 / M input, $15 / M output — check your provider's current price sheet; never trust memorized prices.

| Component | Tokens | Notes |
|---|---:|---|
| System prompt + tool definitions | 1,200 | Stable prefix — cache hit after first call |
| Retrieved context (8 chunks) | 8,000 | Volatile — the bulk of input spend |
| User question | 100 | |
| Answer + citations (output) | 400 | Dominates wall-clock time |
| **Cost** | $0.034 | 9,300 × $3/M + 400 × $15/M |
| **Latency** | ~11 s | ~1 s TTFT + 400 × 25 ms — stream it, or it feels broken |
| **At 1,000 queries/day** | ~$1,020 /mo | Before caching; unit economics are a design input |

Two design levers fall straight out of the math: **retrieval precision** (fewer, better chunks cut the dominant input cost — P1) and **output discipline** (shorter answers cut the dominant latency). This is why cost work and quality work are the same work.

> **Unit objective — restated:** Before any LLM call, you can estimate its cost to the cent, its latency to the second, and name its three most likely failure modes — without running it.

---

## Practice — hands-on probes

*Roughly half your P0 time goes here, not in reading. Any provider works; a gateway like LiteLLM keeps you provider-neutral from day one.*

1. Set up one provider SDK or a gateway (e.g., LiteLLM). Make a single call and find the **usage block** in the response: input tokens, output tokens, stop reason.
   *Exit: you know where every number in §0.5 comes from.*
2. Run a tokenizer (tiktoken, or your provider's count-tokens API) on three inputs: a paragraph of prose, a JSON blob, a 12-digit number.
   *Exit: you can explain why code costs more per character and why arithmetic is unreliable.*
3. Write a 5-turn conversation loop that re-sends history each call. Print input tokens per turn.
   *Exit: you've watched turn 5 cost several times turn 1 — the quadratic trap, live.*
4. Embed ~10 sentences including an include/exclude pair and an exact identifier (a part number, a clause number). Compute the cosine-similarity matrix.
   *Exit: you've watched embeddings fail on exactly the cases §0.2 predicts.*
5. Design one extraction schema (typed model with enums + optional fields), then critique it against the §0.4 design rules before running it.
   *Exit: one concrete improvement you could defend in review — this becomes Project B.*
6. Pick any call, estimate cost and latency on paper first, then run it and check the usage block. Repeat until your estimate lands within ~25%.
   *Exit: the unit objective, demonstrated — this becomes Project A.*

---

## Exit check

*Answer each from memory, out loud, in two or three sentences. Tick a box only when you could defend the answer to a colleague. All six → start P1.*

- [ ] Why does a 20-turn conversation cost far more than 20 independent calls — and what are two mitigations?
- [ ] Temperature 0: why is it still not deterministic, and what discipline replaces the determinism you lost?
- [ ] Why do "include X" and "exclude X" retrieve the same chunks — and which P1 technique compensates?
- [ ] Your extraction returned truncated JSON. Name the likely cause and the two-line fix.
- [ ] Why should prompts live in a versioned registry instead of code — and what does a rollback look like in each case?
- [ ] Estimate the monthly cost of the §0.5 call shape at 5,000 queries/day — then name the two levers that cut it most.

---

*Unit P0 of the [Production AI learning plan](./learning-plan.md) · next: P1 — Production RAG*
