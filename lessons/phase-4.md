# Phase 4 — Security & Guardrails (Threat Modeling, Input/Output/Tool Rails, Red-Teaming)

## 1. Outcome Statement

At the end of this phase you can threat-model an LLM system end to end and defend it in depth: input rails (injection detection, PII redaction), output rails (schema validation, moderation, grounding checks), and tool rails (least privilege, allowlists, approval gates, sandboxing). You can red-team your own agent systematically using the OWASP LLM Top 10 as a map, and you understand — from having tried to break your own build — why no single guardrail is sufficient and how layers compensate for each other's gaps.

## 2. Prerequisites

- Phase 3 exit gate passed. This phase hardens what you built:
  - The Research Analyst agent (LangGraph + Temporal) with its tools, including the `send_email`-style consequential tool and the human-approval gate
  - The poisoned-corpus document from Phase 2 and the excessive-agency attack from Phase 3 — you've already *seen* these break things; now you build the systematic defenses
  - LangFuse tracing — guardrail decisions become traced events/scores here
- New setup: at least one guardrail framework (NeMo Guardrails, Guardrails AI, or Llama Guard), a provider moderation endpoint, and a small red-team harness (a script that fires a battery of adversarial inputs at your agent and records outcomes).

## 3. Concepts

### Internalize (reason from first principles)

- **The core mental model**: treat every LLM output as untrusted input, and treat everything entering the context — user input, RAG chunks, tool results, MCP tool descriptions, file uploads — as a potential injection vector. Your backend instinct that "all input is hostile" transfers directly; the twist is that *the model's own output* is also input to the next stage.
- **Prompt injection, direct vs. indirect**: direct (user types the attack) vs. indirect (attack arrives via retrieved content or a tool result the user never sees). Indirect is the dangerous one and the reason "just validate user input" fails. Why there is no complete fix — only mitigation and containment.
- **The confused-deputy / excessive-agency problem**: the agent has legitimate permissions; the attacker doesn't need to breach anything, just to *redirect the agent's authority*. This reframes security from "keep attackers out" to "constrain what the trusted agent can do."
- **Defense in depth for LLMs**: no single rail is reliable (detectors have false negatives, models can be jailbroken), so you layer independent controls where each one's failure is caught by another. Be able to reason about *residual risk* after each layer.
- **Input rails**: injection/jailbreak detection (classifier and heuristic), PII detection and redaction before the model sees data, topic/scope filtering, input length and structure validation.
- **Output rails**: structured-output schema validation (you built retry-on-invalid in Phase 1 — now it's a security control), content moderation, grounding/faithfulness checks against retrieved sources, secret/PII leakage detection in outputs, refusing to emit tool calls that violate policy.
- **Tool rails — the highest-leverage layer for agents**: least-privilege scoping (the tool can do exactly one thing), allowlists over denylists, parameterized/sandboxed execution, human-in-the-loop approval for consequential actions (you have this — now formalize *which* actions require it and why), rate/quota limits per tool, and dry-run/simulation before commit.
- **System prompt hardening and its limits**: instruction hierarchy, delimiting untrusted content, spotlighting/data-marking — plus honest acknowledgement that these raise the bar but don't close the door, which is *why* the other layers exist.
- **The trust boundary map**: being able to draw, for your own system, where trusted and untrusted data meet, and placing a control at each boundary. This is the deliverable-shaped skill.

### Recognize (vocabulary + mental map, no depth)

- Specific jailbreak taxonomies (DAN-style, roleplay, encoding, many-shot, crescendo) — recognize the families, don't memorize payloads
- Adversarial-suffix / gradient-based attacks on open models — know they exist, out of scope to execute
- Data-poisoning and model-supply-chain attacks (poisoned training data, malicious model weights) — recognize; mostly out of your control as an app engineer
- Formal guardrail DSLs (NeMo Colang in depth) — use one, don't master its full grammar
- Differential privacy, PII tokenization vaults — recognize as the heavier-weight options beyond redaction
- Model/agent sandboxing infra (gVisor, microVMs, WASM isolates) — recognize; you'll use a simpler sandbox
- Constitutional/self-critique as a soft guardrail — know the pattern, don't rely on it as a primary control

## 4. The Build — Harden the Research Analyst

No new application; you're wrapping the Phase 3 agent in a security layer and proving it holds.

**Stage A — Threat model artifact**
1. Draw the trust-boundary diagram for your agent: every point where untrusted data (user, RAG corpus, external tool, MCP descriptions) enters, and every consequential action it can take. Map each to a relevant OWASP LLM Top 10 category. This diagram drives everything else.

**Stage B — Rails**
2. **Input rail**: a pre-processing node that runs injection detection + PII redaction before user input and before retrieved chunks enter the context. Log every decision to LangFuse.
3. **Output rail**: a post-processing node enforcing schema validation, moderation, a grounding check (does the answer's claims trace to retrieved sources?), and outbound PII/secret leakage detection.
4. **Tool rail**: formalize the approval policy — a declarative allowlist of which tools are auto-allowed vs. approval-required vs. forbidden-in-context; least-privilege the consequential tool; add a per-tool rate limit; make the `send_email`-style tool run a dry-run/preview that the human approves.

**Stage C — Red-team harness**
5. A script firing a battery of adversarial inputs — direct injections, indirect injections planted in the corpus, jailbreak attempts, PII-exfiltration prompts, excessive-agency manipulations — at the agent, recording for each: did it breach, which rail (if any) caught it, and the trace ID. Produce a pass/fail red-team report.

### Acceptance criteria

- [ ] A trust-boundary diagram exists, with each boundary mapped to an OWASP LLM Top 10 item and the control placed there
- [ ] The indirect injection from Phase 2's poisoned corpus is now **caught or contained** — either the input rail flags it, or the output rail's grounding check rejects the hijacked answer, or the tool rail prevents the resulting action; you can name which layer(s) caught it
- [ ] The excessive-agency attack from Phase 3 no longer results in an unapproved consequential action — demonstrated against the same attack that previously succeeded
- [ ] PII in inputs is redacted before reaching the model, and PII in outputs is blocked — verified with seeded test data
- [ ] Structured-output schema violations are rejected (not silently passed downstream)
- [ ] The red-team harness runs a battery of ≥20 attacks and produces a report: breach rate, catches-per-rail, and residual known-risks with honest write-ups
- [ ] Every rail decision (allow/block/redact/escalate) is a traced event in LangFuse; you can audit false positives
- [ ] A written residual-risk statement: what your defenses do *not* stop, and what would be required to (accepting that "fully prevent injection" is not on the table)

## 5. Background Threads Checklist

- [ ] **Evals — the security/quality tension**: guardrails cause false positives. Add a "benign-but-suspicious" eval set (legitimate inputs that look attack-like) and measure how many your rails wrongly block. The metric that matters is breach-rate *and* false-positive-rate together — a rail that blocks everything is not secure, it's broken. Push both numbers to LangFuse.
- [ ] **Attack (this IS the phase)**: the red-team harness is the attack thread, escalated to systematic. Beyond the harness, do one manual creative session trying to defeat your own rails — attackers are creative in ways batteries aren't.
- [ ] **Cost & latency**: rails add cost and latency (extra model calls for detection, extra validation passes). Measure the overhead per request and decide which rails are worth their cost on which paths — a fast heuristic rail on every request, an expensive LLM-judge rail only on flagged ones (a routing/cascade pattern, reused from Phase 3).
- [ ] **Instrumentation**: a security view in LangFuse — filterable by rail-triggered events, so you can review blocks, tune thresholds, and catch false positives. Blocked attempts should be as visible as errors.

## 6. Break-It Exercises → Failure Demo

1. **Beat your own input rail**: find an injection phrasing the detector misses (obfuscation, encoding, language switching). This *will* be possible — the lesson is that input detection is a filter, not a wall, and why you need the output and tool layers behind it.
2. **Grounding-check bypass**: craft a hijacked answer that stays superficially grounded in retrieved text while still following an injected instruction. Watch the grounding rail's blind spot.
3. **Approval-gate social engineering**: make the agent present the dry-run preview in a misleading way so a hurried human would approve a bad action. This teaches that the human gate's quality depends on *what the human is shown* — the preview is itself a security-relevant artifact.
4. **False-positive storm**: tune the input rail aggressive enough to catch your hardest attack, then run the benign eval set and watch legitimate traffic get blocked. Find the operating point. There is no threshold that's both perfectly safe and perfectly permissive — internalize the tradeoff curve.
5. **Rail-removal ablation**: disable each rail in turn, re-run the red-team harness, and record which attacks each rail was uniquely stopping. This proves defense-in-depth empirically — some attacks are caught only by the combination.

**Failure demo (exit-gate component #1):** post-mortem format — but this phase's demo is essentially your red-team report plus the ablation results: here's what breaks each defense, here's the residual risk, here's why layering is non-negotiable.

## 7. Self-Assessment Questions (exit-gate component #2 — closed book)

1. Why is indirect prompt injection harder to defend than direct, and why does input validation alone never fully solve it?
2. Explain the confused-deputy problem in your own agent: the agent isn't compromised, so what exactly is the attacker exploiting, and where does the fix live?
3. You can't fully prevent prompt injection. Given that, how do you build a system you'd still deploy? Frame the answer around containment and blast-radius, not prevention.
4. Walk the trust boundaries of your agent and name the control at each. Which boundary, if left unguarded, is the most dangerous and why?
5. Defense in depth: give a concrete attack that your input rail misses, your output rail misses, but your tool rail catches — and one that gets through everything. What's the residual risk statement for the second one?
6. A grounding check verifies the answer traces to sources. Construct an attack that satisfies the grounding check while still being an injection success. What does this tell you about the limits of any single verifier?
7. Rails have false positives. How do you set an operating point, and how does a cascade (cheap heuristic → expensive LLM judge) let you afford stronger checks without taxing every request?
8. Which agent actions warrant a human-approval gate, what must the human be shown for the gate to be meaningful, and how could an attacker turn the preview itself into an attack surface?
9. Map three OWASP LLM Top 10 categories to specific controls in your build, and name one category your build does not meaningfully address.

**Exit-gate component #3:** all acceptance criteria checked. Spaced review: re-answer Phase 2 Q7 (injection surfaces) and Phase 3 Q6 (`send_email` causal chains) from memory — this phase should have turned both from theory into reflex.

## 8. Teach-Back Deliverable

A security design doc: **"Threat model and defense-in-depth for an LLM agent"** — the trust-boundary diagram, the OWASP mapping, each rail with what it catches and what it misses, the red-team report with breach and false-positive rates, and an unflinching residual-risk section. This is the document that would let a security reviewer at a real company take your system seriously — write it to that bar.

## 9. Depth Stops

- **Jailbreak payload collecting**: understand the families, run a representative sample in the harness. Do not turn into a prompt-injection payload librarian — out of scope.
- **Gradient/adversarial-suffix attacks**: recognize-level only; executing them is a research project, not app engineering.
- **Guardrail DSL mastery**: use one framework functionally. Do not go deep on Colang grammar or build a custom rail engine.
- **Sandboxing infra**: a simple sandbox (restricted subprocess, container, or the framework's built-in) is enough. MicroVM/WASM isolation — recognize-level.
- **PII tooling**: redaction with an off-the-shelf detector is the ceiling. Tokenization vaults / DP — recognize-level.
- **Don't rebuild the agent**: the temptation is to re-architect for security. Resist — wrap and constrain the Phase 3 agent; the point is defending a realistic system, not a security-native rewrite.

## 10. Curated Resources (max 5)

1. **OWASP Top 10 for LLM Applications** *(primary)*: the canonical threat map; drives your Stage A diagram and red-team categories.
2. **One guardrail framework's docs** — NeMo Guardrails *or* Guardrails AI *or* Llama Guard: pick one, implement rails with it.
3. **A serious practitioner write-up on indirect prompt injection** (e.g., Simon Willison's prompt-injection series or an equivalent well-regarded treatment): for the "why there's no clean fix" intuition.
4. **Provider moderation + safety docs** (Anthropic/OpenAI safety best practices): moderation endpoints, instruction hierarchy, data-marking/spotlighting guidance.
5. **A red-teaming guide for LLMs** (a framework like promptfoo's red-team feature or Microsoft's LLM red-teaming guidance): to structure your Stage C harness rather than inventing it from scratch.
