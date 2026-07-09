# Phase 5 — Observability & Evals (LangFuse Deep, Golden Datasets, LLM-as-Judge, CI Gating)

## 1. Outcome Statement

At the end of this phase you can treat evaluation as your test suite: golden datasets, LLM-as-judge with validated judges, RAG-specific and agent-specific metrics, regression testing of prompts, and offline-vs-online evaluation — all in LangFuse, wired into CI so a prompt or model change can't ship if it regresses quality. You have turned the eval habit you've been building since Phase 1 into a rigorous, automated discipline, and you can debug any production request from its trace alone.

## 2. Prerequisites

- Phase 4 exit gate passed. This phase formalizes threads you've run all along:
  - Eval datasets accumulated in every phase (extraction set from P1, RAG set from P2, agent set from P3, security/false-positive sets from P4) — now unified and rigorous
  - LangFuse tracing wired through the proxy, RAG pipeline, agent graph, Temporal activities, and guardrails — now used to its full depth
  - The hardened Research Analyst agent as the system under evaluation
- New setup: a CI environment (GitHub Actions or equivalent) with API keys as secrets, plus Ragas and/or DeepEval and promptfoo installed. You've touched all of these lightly; here they become load-bearing.

## 3. Concepts

### Internalize (reason from first principles)

- **Why evals are the test suite**: outputs are probabilistic, so correctness is statistical, not binary. You can't unit-test a prompt, but you can measure a distribution of quality on a dataset and gate changes on it. This is the mindset shift that separates production AI from demos — internalize it fully.
- **Golden datasets**: how to build one that's representative (mirrors real input distribution), discriminative (hard enough to expose regressions), and maintained (grows from real production failures). The dataset is the asset; the harness is commodity.
- **Metric taxonomy**: deterministic checks (schema valid? contains required field? within latency budget?), reference-based metrics (similarity to a known-good answer), and reference-free / LLM-as-judge (faithfulness, relevance, helpfulness) — and knowing which to reach for. Prefer the cheapest reliable metric; escalate to LLM-judge only where cheaper checks can't capture quality.
- **LLM-as-judge, done right**: the judge is itself a model that can be wrong or biased (position bias, verbosity bias, self-preference). You must *validate the judge* against human labels before trusting it, use pairwise comparison where possible, and pin/version the judge model. An unvalidated judge is measurement theater.
- **RAG evaluation, decomposed**: retrieval metrics (context recall/precision, is the right chunk retrieved?) separated from generation metrics (faithfulness — does the answer stick to retrieved context? — and answer relevance). They fail independently; measuring them jointly hides which stage broke. (You did this in P2; now with rigor and a validated judge.)
- **Agent evaluation**: outcome metrics (final-answer quality) vs. trajectory metrics (right tools, sensible order, terminated, cost/steps within budget). Outcome-only evals let dangerous or wasteful agents pass — you proved this need in P3/P4; now you systematize it.
- **Offline vs. online evaluation**: offline = dataset-based, pre-deploy, regression-gating. Online = production traffic — sampling real requests, user feedback signals (thumbs, corrections, downstream success), drift detection, and building tomorrow's golden dataset from today's failures. The loop between them is the flywheel.
- **Regression gating in CI**: a change (prompt edit, model swap, retrieval tweak) runs the eval suite; if quality on the golden set drops below threshold, the build fails. Treat prompts and model choices as versioned, testable artifacts — LangFuse prompt management makes this real.
- **Experimentation**: A/B evaluation of two prompt/model variants on the same dataset, reading the comparison honestly (effect size, not just "the number went up"), and the risk of overfitting your prompts to your eval set.

### Recognize (vocabulary + mental map, no depth)

- Statistical rigor for evals: confidence intervals, sample-size adequacy, significance of small deltas — recognize enough to be skeptical of noise, not to run formal power analyses
- Specialized metric libraries beyond Ragas/DeepEval (TruLens, OpenAI Evals, Braintrust) — know they exist and overlap
- Human annotation at scale: labeling guidelines, inter-annotator agreement — recognize; you'll do small-scale annotation yourself
- Trace-based fine-tuning data collection (harvesting good traces to fine-tune later) — recognize; ties to the deliberately-skipped fine-tuning topic
- Canary / shadow deployment for models — recognize as the online-eval infrastructure you'd add at scale
- Cost of evaluation itself (LLM-judge on a big dataset isn't free) — recognize, it feeds Phase 6

### Internalize vs recognize note
The eval *mindset* and the offline regression-gating loop are internalize. Large-scale online-eval infrastructure is recognize — you'll build the small version and understand the big version.

## 4. The Build — An Eval System, Not Just Evals

Turn the accumulated datasets and tracing into a real evaluation system around the Research Analyst agent.

**Stage A — Unified golden datasets in LangFuse**
1. Consolidate the per-phase datasets into versioned LangFuse datasets: an extraction set, a RAG set (with retrieval + generation labels), an agent-task set (with expected trajectories), and a security set (attacks + benign-suspicious). Each item has input, expected outcome, and metadata.

**Stage B — A validated judge and a metric suite**
2. Build LLM-as-judge evaluators for faithfulness, relevance, and citation-correctness. **Validate them**: hand-label ~30 items, measure judge-vs-human agreement, iterate the judge prompt until agreement is acceptable, pin the judge model. Combine with deterministic checks (schema, latency, cost budgets) and Ragas metrics for RAG.

**Stage C — Regression gating in CI**
3. A CI pipeline that, on any change to prompts/models/retrieval config, runs the eval suite against the golden datasets and **fails the build if quality regresses** past a threshold. Prompts are pulled from LangFuse prompt management (versioned), so a prompt change is a reviewable, testable artifact.

**Stage D — Online loop**
4. Wire production-style feedback: a scores API call attaching user feedback (or simulated feedback) to traces, a sampling job that pulls low-scoring real traces into an annotation queue, and a documented process for promoting annotated failures into the golden dataset. Close the loop.

### Acceptance criteria

- [ ] Versioned golden datasets live in LangFuse, covering extraction, RAG (retrieval + generation separated), agent trajectories, and security
- [ ] Your LLM-as-judge is validated against human labels with a reported agreement number, and the judge model is pinned — no unvalidated judge in the pipeline
- [ ] RAG evals report retrieval and generation metrics *separately*
- [ ] Agent evals report trajectory metrics (tools, steps, termination, cost) alongside outcome quality
- [ ] A prompt change that degrades quality is **caught by CI and blocks the merge** — demonstrated by intentionally shipping a worse prompt and watching the pipeline go red
- [ ] Prompts are versioned in LangFuse and fetched at runtime; you can roll back a prompt without a code deploy
- [ ] The online loop works end to end: a low-scoring trace flows into the annotation queue and can be promoted into the golden set
- [ ] You can take any single production-style trace and fully explain what happened and why, from the trace alone

## 5. Background Threads Checklist

- [ ] **Evals (this IS the phase)**: the thread becomes the subject. The remaining thread-discipline is meta: keep the datasets growing from real failures even after this phase.
- [ ] **Attack**: add the Phase 4 attacks as a permanent regression suite — security is not a one-time pass; a prompt or model change can silently reopen a closed vulnerability. Your CI should fail if a previously-caught attack starts getting through.
- [ ] **Cost & latency**: measure the cost of evaluation itself (LLM-judge over a full dataset is a real bill) and design the suite so CI runs are affordable — deterministic checks on every run, expensive LLM-judge on a sampled or nightly cadence. This directly sets up Phase 6.
- [ ] **Instrumentation**: this phase is instrumentation's payoff — everything you've traced since Phase 1 now becomes queryable evaluation data. Confirm that traces carry enough structured metadata (model, tokens, cost, rail decisions, retrieval scores) to slice quality by any dimension.

## 6. Break-It Exercises → Failure Demo

1. **Judge disagreement**: find inputs where your LLM-judge confidently disagrees with your own judgment. Diagnose the bias (verbosity? position? self-preference?). This is why unvalidated judges are dangerous — feel it directly.
2. **Overfit the eval set**: tune a prompt until it aces the golden set, then run it on fresh held-out inputs and watch it underperform. Learn why a held-out set and dataset freshness matter.
3. **Regression that outcome-metrics miss**: introduce a change that keeps final-answer quality flat but degrades the trajectory (more steps, higher cost, worse tool choices). Confirm your trajectory metrics catch what outcome metrics don't.
4. **Metric gaming**: construct an answer that scores high on your faithfulness metric while being unhelpful or evasive. Every metric is a proxy; watch the proxy diverge from what you actually care about.
5. **CI false confidence**: make the eval dataset too small/easy, ship a genuinely worse change, and watch CI pass anyway. Learn the failure mode of a weak eval suite — green CI on a bad dataset is worse than no CI, because it's trusted.

**Failure demo (exit-gate component #1):** post-mortem format — the theme is *ways your measurement lies to you*: unvalidated judges, overfit datasets, proxy metrics, weak suites. Each with the detection signal and the mitigation.

## 7. Self-Assessment Questions (exit-gate component #2 — closed book)

1. Why can't you unit-test an LLM feature, and what replaces the unit test? What does "green" mean for a probabilistic system?
2. Your LLM-as-judge says quality improved 8%. Before you believe it, what must be true about the judge, the dataset, and the delta itself?
3. Separate the failure modes: retrieval metrics look great but answers are wrong; answers are faithful but users are unhappy. Diagnose each and name the metric that would have surfaced it.
4. Outcome-only agent evals pass a dangerous agent. Give a concrete case and the trajectory metric that would have failed it.
5. Design the CI gate: what runs on every commit, what runs nightly, what's the failure threshold, and how do you keep the judge cost from making CI unaffordable?
6. What makes a golden dataset good? Walk through representative, discriminative, and maintained — and how the online loop feeds the last one.
7. You tuned a prompt to ace your eval set and quality dropped in production. What happened, and what practices prevent it?
8. Offline vs. online evaluation: what can each catch that the other can't, and how do they form a loop rather than two separate activities?
9. Every metric is a proxy. Pick one of your metrics and describe how an output could game it — and what defense-in-depth for *metrics* looks like.

**Exit-gate component #3:** all acceptance criteria checked. Spaced review: re-answer Phase 1 Q2 (cost levers), Phase 2 Q9 (recall@k vs faithfulness), and Phase 3 Q9 (trajectory vs outcome) from memory — this phase is where those three converge.

## 8. Teach-Back Deliverable

A design doc: **"Evaluation as the test suite for a probabilistic system"** — your dataset strategy, judge validation methodology (with the agreement number), the metric taxonomy and why each metric earns its place, the CI gating design, and the offline↔online flywheel. Include a candid "how my measurements could lie to me and what I did about it" section — the failure demo, written up. This doc demonstrates the single most senior-differentiating skill in AI engineering: knowing whether your system actually works.

## 9. Depth Stops

- **Statistical formalism**: enough to distrust small deltas and tiny datasets. Do not build formal power analyses or significance-testing frameworks — recognize-level.
- **Judge sophistication**: validate one judge well. Do not build ensembles of judges or a judge-tuning pipeline — out of scope.
- **Metric library sprawl**: Ragas/DeepEval + your own deterministic and judge metrics. Do not tour every eval library — recognize the others by name.
- **Annotation at scale**: small self-annotation for judge validation only. No annotation platforms, no inter-annotator-agreement machinery — recognize-level.
- **Online-eval infra**: build the small version (scores, sampling, annotation queue). Shadow/canary deployment infrastructure — recognize-level, revisit at real production scale.
- **Don't gold-plate the datasets**: representative and discriminative beats large. A tight 30–50 item set that reliably catches regressions is worth more than 500 noisy items. Resist dataset-size vanity.

## 10. Curated Resources (max 5)

1. **LangFuse docs — Datasets, Evaluation, Scores, and Prompt Management** *(primary)*: the backbone for all four stages; you already know the tool, now use these sections in depth.
2. **Ragas docs — metrics + how they're computed**: faithfulness, context precision/recall, answer relevance; enough to trust the numbers, not just call the functions.
3. **A rigorous LLM-as-judge treatment** (a well-regarded practitioner or research write-up on judge bias and validation): the "validate your judge" discipline that most teams skip.
4. **promptfoo docs — evaluation + CI integration**: for the regression-gating pipeline and prompt-level A/B testing.
5. **One practitioner piece on eval-driven development / building golden datasets from production** (e.g., a well-known applied-AI blog on the offline↔online loop): the flywheel mindset, from someone who ran it in production.