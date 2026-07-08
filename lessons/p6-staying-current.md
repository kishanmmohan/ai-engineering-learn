# P6 · Staying Current

> **Production AI Learning Plan · Unit P6**

The field moves monthly — build a filter, not a feed. This unit is a *practice*, not a phase you finish: a repeatable reading loop and the decision frameworks that turn hype into evidence-based calls.

**Ongoing · 2 lessons · Recurring project · No exit gate — this one never closes**

**On this page:** [6.1 The reading loop](#61-the-reading-loop) · [6.2 Decision frameworks](#62-decision-frameworks) · [Recurring project](#recurring-project--tech-radar-memo) · [Practice](#practice--hands-on-probes) · [The through-line](#the-through-line)

---

## 6.1 The reading loop

*Consumption without a filter is just anxiety. The goal is a system that converts noise into a small number of tested decisions.*

### Triage your sources

- **Tiers, by signal:** model/provider release notes and changelogs (highest — this changes what you can build); a few high-signal engineering blogs and maintainers; papers (lower day-to-day signal, higher for foundations). Everything else is a stream you skim, not a queue you clear.
- **Pull, don't drown:** batch reading (a weekly slot), don't react to every announcement. The half-life of a hot take is short; the half-life of a foundation (P0–P5) is long. Spend most of your attention on foundations.

### Read papers like an engineer, not a student

- **Claims → method → evidence → limitations.** Jump to the limitations and the eval setup first; that's where you learn whether it survives contact with *your* workload.
- **Replicate small before adopting.** A method that wins on the paper's benchmark may lose on your corpus (different data, different distribution). The cheapest way to know is to try the smallest version on your own capstone.

### Benchmark skepticism (the core literacy)

- **Contamination:** the benchmark may be in the training data — inflated scores that won't reproduce on your novel inputs.
- **Cherry-picking:** results shown on the tasks/configs where the method wins; the losses are quietly absent.
- **Apples-to-oranges:** different prompts, context sizes, or model versions across the compared systems — the "win" is a setup artifact.
- **Your gold set (P3) is the benchmark that matters.** It measures *your* workload with labels *you* trust. When a public number and your gold set disagree, your gold set wins.

> **Systems analogy** — You already distrust a vendor benchmark run on their hardware with their workload. Same reflex, pointed at model and technique claims: reproduce on your rig, with your load, before you believe the headline.

---

## 6.2 Decision frameworks

*The recurring questions have durable answers. Learn the decision shape once; re-run it as the options change.*

### RAG vs fine-tuning vs distillation

The most common "should we…?" — and usually a false binary:

- **RAG** injects *knowledge* at inference (facts, freshness, citations, per-tenant data). Default for "the model needs to know things it wasn't trained on" — which is most business problems.
- **Fine-tuning** shapes *behavior* (format, tone, a narrow task, tool-use style). It does **not** reliably teach new facts, and it freezes a snapshot you must re-do as data changes. Reach for it when RAG + prompting have plateaued on *form*, not on knowledge.
- **Distillation** compresses a big model's behavior into a smaller/cheaper one — a *cost/latency* optimization once you have a quality bar (P3) and traffic to justify it.
- Usual order: **prompt → RAG → fine-tune → distill**, escalating only when evals say the cheaper layer has plateaued. Most teams stop at RAG + prompting.

### Build vs adopt

- Adopt (a framework, a managed service) to move fast and offload maintenance; build to control a core differentiator or escape a real limit. The trap is adopting a heavy framework before you understand what it abstracts — which is exactly why this track had you hand-roll the loop (P2) and the eval harness (P3) first. Understand it, *then* choose the abstraction.

### Capability tracking

- **Multimodal / VLMs:** as vision-language models improve, ingestion problems (P1's tables/figures/scanned drawings) become tractable — retest your hard ingestion cases when a materially better VLM ships.
- **Reasoning models & test-time compute:** models that "think longer" trade tokens/latency for accuracy on hard multi-step problems. Worth it for genuinely hard reasoning; wasteful for extraction/classification. Let evals + cost (P3, P4) decide per node — not fashion.
- **Context windows:** bigger windows don't repeal "lost in the middle" (P0) or the cost math. More context is a tool, not a replacement for retrieval.

---

## Recurring project · Tech Radar Memo

Make staying-current a deliverable, not a feeling. Every quarter (or per notable release):

1. **Pick one technique** — a new reranker, late-interaction retrieval (e.g., ColBERT-style), a new judge method, a reasoning model on your hardest node.
2. **Replicate small** on your capstone: wire it into the relevant stage, run it against your P3 gold set.
3. **Write a one-page memo:** the measured numbers (yours, not the paper's), a build-vs-adopt recommendation, and a named **kill-criterion** — the condition under which you'd rip it out.

> **Solid when:** the memo argues from your own measurements, not the paper's claims.

**Sources →** arXiv & model release notes · provider changelogs & engineering blogs · your own capstone as the test bench

---

## Practice — hands-on probes

1. Build your source list, sorted into the three tiers. Delete anything that's pure noise.
   *Exit: a pull-based reading list, not an anxiety feed.*
2. Take one recent paper; extract claims → method → evidence → limitations in five bullets.
   *Exit: engineer-reading, demonstrated on a real paper.*
3. Find one benchmark claim and name which skepticism (contamination / cherry-pick / apples-to-oranges) applies.
   *Exit: reflexive benchmark distrust.*
4. Run one Tech Radar Memo end to end on your capstone.
   *Exit: a decision backed by your own numbers, with a kill-criterion.*
5. Write the RAG-vs-fine-tune-vs-distill decision for a hypothetical feature, in three sentences.
   *Exit: you can wield the framework without re-deriving it.*

---

## The through-line

You don't finish P6 — you run it. But notice what the track built: a system you can *measure* (P3 evals, P4 traces), so every new technique has a test bench and every claim has a check. That's the real graduation — not knowing today's SOTA, but owning the apparatus that tells you whether tomorrow's SOTA is worth adopting.

The [six operating principles](./learning-plan.md#operating-principles-for-production-ai) are the compressed form of everything here. When a new tool or paper lands, run it past them: does it improve an eval, a trace, a prompt's safety, grounding, unit cost, or the system's tolerance for its least reliable component? If it touches none of those, it's news, not work.

---

*Unit P6 of the [Production AI learning plan](./learning-plan.md) · previous: [P5 — Hardening & Scale](./p5-hardening-scale.md) · **end of curriculum** — now build.*
