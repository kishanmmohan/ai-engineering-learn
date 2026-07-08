# P3 · Evals — the Discipline

> **Production AI Learning Plan · Unit P3**

Without evals you're deploying vibes. Evals are to AI what tests are to code — the single highest-leverage production skill. This unit covers gold sets, metrics, LLM-as-judge (and its biases), and the gates that make "no eval evidence, no merge" real.

**~1.5 weeks · Core · 3 lessons · Capstone Stage 3 · Exit check gates P4**

**On this page:** [3.1 Gold sets](#31-gold-sets) · [3.2 Metrics & judges](#32-metrics--judges) · [3.3 Gates & promotion](#33-gates--promotion) · [Capstone Stage 3](#capstone--stage-3--evaluate-gold-set-judge-and-gate) · [Practice](#practice--hands-on-probes) · [Exit check](#exit-check)

---

## 3.1 Gold sets

*Your gold set is the only benchmark that matters. Public leaderboards measure someone else's workload.*

### Anatomy of a case

A gold case is: **input** (the query, plus any fixed context) + **expected** (the answer, the facts it must contain, the citations it should produce) + **metadata** (case type, source, author, date). In practice: one JSONL line per case.

### Coverage design

Design coverage like you design test suites — the happy path is the *minority*:

- **Happy path:** representative real questions.
- **Edge:** ambiguous phrasing, multi-part questions, questions whose answer spans two sections.
- **Adversarial:** questions that *invite* hallucination — plausible-sounding facts not in the corpus, misleading premises ("why does section 5 require X?" when it doesn't).
- **Abstention:** questions whose correct answer is "the documents don't cover this". A gold set without abstention cases cannot catch the most dangerous failure mode.

### Discipline

- **Small-but-clean beats large-but-noisy.** 25 curated, defensible cases outperform 500 scraped ones: a noisy label makes the eval *lie to you*, and you'll tune the system to match the lie. Every case should survive the question "says who?"
- **Version gold sets like code.** A changed case = a new version; results are only comparable within a version. Treat edits like schema migrations — deliberate, logged, reviewed.
- **Source from reality.** Real user queries (from logs, once you have them) beat invented ones. Synthetic cases bootstrap a v1 — but a human verifies every label before it's gold.

> **Systems analogy** — The gold set is your regression suite; noisy labels are flaky tests. You already know what a flaky test does to a team: first it pages you, then you ignore it, then it hides a real regression. Same dynamics, higher stakes.

---

## 3.2 Metrics & judges

*Deterministic checks are free and stable. Spend LLM judgment only where semantics demand it.*

### The core four for grounded QA

```
citation_precision = supported_citations / total_citations     # do cited chunks actually support the claims?
grounding_ratio    = grounded_claims / total_claims            # what share of claims trace to context?
hallucination_rate = unsupported_claims / total_claims         # claims absent from (or contradicting) context
answer_correctness = judge(answer, gold_answer)                # semantic match to the expected answer
```

Citation precision is the one that catches P1's "plausible citation" failure — the answer that *looks* grounded and isn't.

### Deterministic first

Before reaching for a judge, extract everything checkable by code: did it cite at all? Do cited pages exist? Does the answer contain the required number/date/identifier? Does the output parse against the schema? These checks are free, fast, and never drift. A surprising share of eval value is regex.

### LLM-as-judge — a noisy sensor you must calibrate

- **Rubric design:** binary questions ("does the answer state X? yes/no") and anchored scales beat "rate 1–10". Vague rubrics produce confident noise.
- **Known biases:** *position bias* (prefers option A — swap order and re-ask), *verbosity bias* (longer reads as better), *self-preference* (a model grades its own outputs kindly — use a different model as judge where possible).
- **Calibration is mandatory:** hand-label a subset (15–25 cases), measure judge–human agreement. Below ~80%, fix the rubric before trusting any number the judge produces. Re-calibrate when the rubric, judge model, or task changes.
- Also measure the judge's **self-consistency**: run it twice on the same inputs; the disagreement rate is your noise floor. Differences smaller than the noise floor are not signal.

> **Systems analogy** — A judge is an uncalibrated sensor. You wouldn't page on-call off a thermometer you never checked against ice water. Calibrate, note the error bars, and never alert on readings inside them.

---

## 3.3 Gates & promotion

*The eval you don't run automatically is the eval that doesn't exist.*

### CI gates

- Run the eval suite on every change to prompts, retrieval parameters, or models. Compare against a pinned baseline; **fail the build on regression** (non-zero exit — plumbing you already know).
- Handle noise honestly: set thresholds with a tolerance band informed by the judge's noise floor, or run flaky metrics N times. A gate that cries wolf gets deleted; a gate that's too loose is theater.

### Prompt lifecycle

- Prompts flow **draft → staging → production**, promoted only with eval evidence, and live in a registry resolved at runtime by label (P0 §0.3). Rollback = flip the label back — seconds, no deploy.
- The trace (P4) records which prompt version served which request, so a bad rollout is diagnosable and reversible.

### Comparing variants

- **Change one thing at a time.** A new prompt + new top-k + new model is an experiment you can't read.
- Look at **per-case flips**, not just the aggregate: a variant that's +3% on average but breaks 4 previously-passing cases may be a worse ship — those 4 might be your most important queries. Averages hide regressions; diffs expose them.

### Confidence & abstention tuning

- Sweep the confidence threshold and plot the trade-off: answer more (coverage) vs be right more (precision). The curve is engineering; **choosing the operating point is a product decision** — bring the curve, not an opinion.

> **Failure modes to internalize**
>
> - **Eval overfitting** — iterating against the gold set until you've memorized it. Hold out cases, refresh regularly.
> - **Metric gaming** — short, hedgy answers score beautifully on hallucination rate. Balance with correctness/completeness.
> - **Stale baseline** — comparing to a three-week-old run on a different corpus version. Pin baselines to versions of everything.

---

## Capstone · Stage 3 — Evaluate: gold set, judge, and gate

1. **Gold set:** 25 JSONL cases for your QA system — including ≥4 abstention and ≥4 adversarial cases.
2. **Metrics:** implement citation precision, grounding ratio, and hallucination rate — deterministic checks where possible, LLM-as-judge where semantics require.
3. **Calibrate:** hand-label 15 cases; report judge–human agreement; fix the rubric until ≥80%.
4. **Compare:** run two prompt variants through the harness → a promote/reject verdict from per-case diffs.
5. **Gate:** wire it into CI (non-zero exit on regression). Plant a deliberate regression — weaken the grounding instruction — and confirm the gate catches it.

> **Solid when:** the planted regression is caught automatically, and judge–human agreement is ≥80% before you rely on it.

**Tooling →** hand-roll the harness first (JSONL + pytest) — you'll understand every eval tool after · then compare with promptfoo / Ragas

---

## Practice — hands-on probes

1. Write 5 gold cases by hand — including one abstention and one adversarial.
   *Exit: you've felt how much judgment one good case takes (and why scraped sets are noisy).*
2. Implement one fully deterministic metric (citations present + cited pages exist) before any judge.
   *Exit: free-checks-first, internalized.*
3. Build a judge with a binary rubric. Run it twice on identical inputs; measure self-agreement.
   *Exit: you know your judge's noise floor as a number.*
4. Hand-label 15 cases; compute judge–human agreement.
   *Exit: a number, and an explicit trust/don't-trust verdict.*
5. Run two prompt variants; produce a per-case diff table, not just averages.
   *Exit: you can name exactly which cases flipped, and why.*
6. Plant a regression and run the gate.
   *Exit: the gate catches it — or you fix the gate until it does.*

---

## Exit check

*Answer each from memory, out loud. Tick a box only when you could defend the answer to a colleague. All six → start P4.*

- [ ] Why do 25 clean cases beat 500 scraped ones? What exactly does one noisy label do to your workflow?
- [ ] Which checks should never be an LLM judge, and what do you gain by keeping them deterministic?
- [ ] Name three judge biases and one mitigation for each.
- [ ] Your judge agrees with humans 65% of the time. What do you do — and what do you refuse to do until it's fixed?
- [ ] Your new prompt wins on average but flips 4 passing cases to failing. Ship it? Defend the answer.
- [ ] Walk through a prompt rollback when prompts live in a registry — and contrast it with rolling back a hardcoded prompt.

---

*Unit P3 of the [Production AI learning plan](./learning-plan.md) · previous: [P2 — Agents & Orchestration](./p2-agents-orchestration.md) · next: [P4 — Observability & Cost](./p4-observability-cost.md)*
