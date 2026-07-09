# Phase 3 — Orchestration & Agents (LangGraph, Temporal, Model Routing, Agent Context Engineering)

## 1. Outcome Statement

At the end of this phase you can design, build, and operate durable agentic systems: LangGraph state machines with checkpointing and human-in-the-loop interrupts, wrapped in Temporal workflows for real durability, calling your own MCP tools, with model routing that sends each step to the cheapest model that can handle it. You can read LangChain code fluently without depending on it. Most importantly, you can argue — with evidence from your own builds — when an agent is the wrong answer and a plain pipeline is the right one.

## 2. Prerequisites

- Phase 2 exit gate passed. This phase assumes:
  - Your MCP server (`search_knowledge_base` / `ask_knowledge_base`) works — it becomes this phase's primary tool
  - You hand-rolled a tool-calling loop in Phase 1 — LangGraph will be legible as "that loop, with a state machine around it"
  - Hybrid-search RAG with evals exists — agentic RAG here means adding a decision loop *on top of* it, not rebuilding it
- Existing Temporal knowledge — this phase leans on it hard; you're learning the LLM-shaped usage, not Temporal itself
- New setup: LangGraph (Python), Temporal dev server (you likely have this), LiteLLM routing config expanded to at least three models across two price tiers (e.g., one frontier, one mid, one cheap/fast)

## 3. Concepts

### Internalize (reason from first principles)

- **Workflows vs. agents — the central distinction**: predefined DAG with LLM steps (workflow) vs. LLM-decides-the-next-step-in-a-loop (agent). Agents buy flexibility and pay in cost, latency, and variance. Your default should be the *least* agentic design that solves the problem; this phase exists partly to make that instinct evidence-based.
- **Canonical patterns**: prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer, and the ReAct-style tool loop — know each pattern's shape, when it applies, and its failure signature.
- **LangGraph core**: graphs as state machines — state schema (typed, reducers for concurrent updates), nodes, conditional edges, the compiled graph. Map this onto what you know: it's a workflow engine where transitions can be decided by a model.
- **Checkpointing and persistence**: thread-level checkpoints, resuming from a checkpoint, time-travel debugging. What checkpointing does and does not protect you from (spoiler: the process dying mid-node — that's Temporal's job).
- **Human-in-the-loop**: interrupts, breakpoints before sensitive nodes, resuming with injected human decisions. The approval-gate pattern you'll reuse in Phase 4 (security).
- **Temporal + LLM agents — the durable-agent pattern**: LLM calls and tool calls as *activities* (retryable, timeout-bounded, non-deterministic allowed), the agent loop as *workflow* (deterministic replay). Why non-determinism forces LLM calls into activities. Signals for human approval, timers for long waits, `continue-as-new` for long-running loops. This is where your existing expertise compounds — internalize the mapping, and be able to articulate the **LangGraph-vs-Temporal division of labor**: LangGraph structures the *reasoning* loop; Temporal makes the *execution* durable. When to use one, the other, or both.
- **Model routing**: task-complexity routing (cheap model first, escalate on failure/low confidence), cascade patterns, routing by step type within one agent (the planner gets the frontier model; the summarizer gets the cheap one). LiteLLM routing strategies, fallback chains, per-route cost attribution.
- **Context engineering, part 3 — agent context**: the agent's context is an append-only log that grows every step; managing it is the core scaling problem. Compaction/summarization of old turns, what tool results to keep vs. truncate vs. summarize, scratchpad vs. long-term memory, and **sub-agent context isolation** — spawning a sub-agent so 50K tokens of tool output never enters the parent's window (your Phase 2 self-assessment Q8, now made real).
- **Multi-agent shapes**: supervisor/worker, handoffs. Enough to build one; enough skepticism to know most "multi-agent" designs are one agent with extra steps and extra failure modes.
- **Agent failure modes**: loops that never terminate, tool-call thrashing, context poisoning compounding across steps, error cascades where step 3's hallucination becomes step 7's ground truth. Termination conditions and step budgets as circuit breakers.

### Recognize (vocabulary + mental map, no depth)

- LangChain: LCEL pipe syntax, common abstractions (retrievers, output parsers) — read-fluency only, acquired by reading two real open-source projects that use it, not by building with it
- LangGraph Platform / managed deployment offerings (know they exist; you have Temporal)
- Other frameworks by name and one-line positioning: CrewAI, AutoGen/AG2, OpenAI Agents SDK, Pydantic AI
- Classifier-based routing with a trained router model (vs. the heuristic/cascade routing you'll implement)
- A2A and agent-to-agent protocols (emerging, unstable — name recognition only)
- Streaming intermediate agent state to UIs (matters for product work; defer until needed)

## 4. The Build — "Research Analyst" Agent

One agent, built **three times over the same task**, then extended. The task: *"given a question, research it against the knowledge base (your Phase 2 MCP server) plus one external tool (web search or a stub API), and produce a cited brief."* Building the same behavior three ways is the point — it turns the workflow/agent/durability tradeoffs from prose into experience.

**Stage A — Workflow version (no agent)**
1. A fixed LangGraph DAG: decompose question → parallel retrieval calls → synthesize → cite. No loops, no model-decided control flow. This is your baseline for cost, latency, and quality.

**Stage B — Agent version**
2. A ReAct-style LangGraph agent: the model decides which tools to call and when to stop. Tools: your MCP server's two tools + the external tool. Checkpointing on. A hard step budget (e.g., 10) as circuit breaker.
3. **Human-in-the-loop**: an interrupt before any external-tool call; you approve/deny/edit from a tiny CLI.
4. **Routing wired in**: planner/synthesis steps → frontier model; per-step tool-argument generation and summarization → cheap model; automatic escalation to the frontier model when the cheap model's output fails validation. Per-step cost visible in LangFuse.

**Stage C — Durable version**
5. Wrap Stage B in Temporal: each LLM call and tool call an activity with retry policy; the agent loop a workflow; the human approval becomes a Temporal signal (survives restarts, can wait days); step budget enforced in workflow logic.
6. **Context management**: when the agent's context exceeds a threshold, a compaction node summarizes older turns; one sub-agent spawn for a deliberately verbose tool so its raw output never enters the parent context.

### Acceptance criteria

- [ ] All three stages answer the same 10-question eval set; you have a **cost / latency / quality table comparing Stage A vs. Stage B** and a written verdict on when the agent earns its overhead
- [ ] Stage B agent never exceeds its step budget and always terminates with either an answer or an explicit "couldn't complete" — verified with an adversarial unanswerable question
- [ ] Human interrupt works: agent pauses, resumes correctly with approval, and handles denial gracefully (re-plans rather than crashes)
- [ ] Kill the worker process mid-agent-run in Stage C; the workflow resumes and completes without re-executing completed activities — demonstrate this, don't assume it
- [ ] Routing works: LangFuse traces show different models per step, an observed escalation event, and per-run cost broken down by model
- [ ] Compaction fires on a long run and the agent still answers correctly afterward — proving the summary preserved what mattered
- [ ] The sub-agent isolation demonstrably keeps the parent context small (compare parent context size with and without it)
- [ ] Every run is one coherent LangFuse trace: graph nodes, tool calls, model per step, interrupts, compaction events

## 5. Background Threads Checklist

- [ ] **Evals**: build the 10-question agent eval set (mix: answerable-from-corpus, needs-external-tool, multi-hop, unanswerable). Score with LLM-as-judge on citation faithfulness + completeness. Run it against *every stage* — this is what populates the comparison table. Add trajectory checks: did the agent call a reasonable tool sequence, not just land on a good answer?
- [ ] **Attack — excessive agency**: give the agent a third tool it should rarely use (e.g., a stub `send_email` tool). Craft inputs that manipulate it into calling that tool (instructions hidden in retrieved documents — your Phase 2 poisoned corpus, now with real consequences). Observe whether the human-approval gate catches it. Write down the lesson: *the approval gate is load-bearing, the model's judgment is not*.
- [ ] **Cost & latency**: the Stage A vs. B vs. C table is the deliverable. Additionally measure: routing savings (all-frontier vs. routed, same eval set), and Temporal's latency overhead per step (activity scheduling isn't free — know the number).
- [ ] **Instrumentation**: LangGraph's LangFuse callback for graph structure; Temporal activities wrapped so workflow ID links to trace ID — one click from a Temporal execution to its LangFuse trace and back.

## 6. Break-It Exercises → Failure Demo

1. **The infinite loop**: remove the step budget, give the agent a task where two tools return mutually unsatisfying results. Watch it thrash. Reinstate the budget; then implement one smarter termination signal (e.g., no-new-information detection) and compare.
2. **Context poisoning cascade**: let the poisoned-corpus document enter the agent's context at step 2; trace how the injected instruction influences steps 3–7. This is Phase 2's attack, now with compounding — measure how far the poison propagates.
3. **Compaction lobotomy**: set the compaction threshold absurdly low so the agent summarizes away its own task constraints mid-run. Watch it drift off-objective. This teaches what compaction must preserve (the task, decisions made, open questions) vs. what it can discard.
4. **Non-determinism meets replay**: put an LLM call directly in Temporal workflow code (not an activity) and watch replay break. You know *that* this fails from Temporal experience — seeing *how* it fails with an LLM cements the durable-agent pattern.
5. **Routing under failure**: take the cheap model offline (bad key). Verify escalation keeps runs succeeding, and measure the cost spike — degraded-but-working, with a number attached.

**Failure demo (exit-gate component #1):** post-mortem format. For #2 especially: blast radius across steps, the detection signal in the trace, and which mitigation layers (approval gate, output validation, compaction hygiene) would have contained it.

## 7. Self-Assessment Questions (exit-gate component #2 — closed book)

1. Workflow vs. agent: state the decision rule you'd give a team, and defend it with the numbers from your own Stage A/B comparison.
2. Why must LLM calls live in Temporal activities rather than workflow code? Explain in terms of deterministic replay, and name what you lose if you get it wrong silently.
3. LangGraph checkpointing vs. Temporal durability: what does each protect against? Give a failure that checkpointing alone survives, one that only Temporal survives, and one that neither does.
4. Design a routing policy for a three-step agent (plan → gather → synthesize) with a frontier and a cheap model. Which steps get which model, what triggers escalation, and how do you *validate* the cheap model's output cheaply?
5. An agent's context is an append-only log. Walk through the full toolkit for keeping it under budget on a 50-step run, and the failure mode of each technique.
6. Your agent called `send_email` when it shouldn't have. Reconstruct the possible causal chains (there are at least three distinct ones) and the control that breaks each chain.
7. When do sub-agents genuinely pay for themselves vs. add coordination failure modes? Use your Stage C isolation experiment as evidence.
8. A human approval must be waitable for 3 days without holding resources. Sketch the Temporal design (signal, timer, timeout path) and what happens to the LangGraph state meanwhile.
9. What's the trajectory-vs-outcome distinction in agent evals, and why does outcome-only scoring let dangerous agents pass?

**Exit-gate component #3:** all acceptance criteria checked. Spaced review: re-answer Phase 1 Q3 and Phase 2 Q7–Q8 from memory (they're the foundations this phase stood on — the gaps will be obvious now if they exist).

## 8. Teach-Back Deliverable

A design doc written as if proposing the architecture for your next real project: **"Durable LLM agents on LangGraph + Temporal"** — the division-of-labor argument, the routing policy, the context-management strategy, and the Stage A/B/C comparison table as the evidence base. Include a "when not to do any of this" section with the plain-workflow decision rule. Of all the teach-backs, this is the one to make genuinely good — it's the closest to what you'll actually present at work.

## 9. Depth Stops

- **LangChain**: read-fluency only, acquired by reading two OSS projects. Do not build anything with LCEL. If you catch yourself doing a LangChain tutorial, stop — that time belongs to LangGraph.
- **Multi-agent**: one supervisor + one sub-agent, built for the isolation experiment. No CrewAI, no agent swarms, no debate patterns. Out of scope for the plan.
- **Routing**: heuristic + cascade routing only. Training a classifier router — out of scope entirely.
- **Temporal**: no new Temporal depth beyond signals/timers/continue-as-new in this context. You know the platform; resist re-studying it as displacement activity.
- **The external tool**: a stub or the simplest real API. Building a polished web-search integration is not the lesson.
- **Memory systems**: scratchpad + compaction only. Long-term memory stores (vector-backed user memory, Zep, Letta et al.) — recognize-level; revisit if the next project needs persistent per-user memory.

## 10. Curated Resources (max 5)

1. **Anthropic — "Building Effective Agents"** *(primary; read first)*: the workflow-vs-agent taxonomy and the "least agentic design" argument this phase is built around.
2. **LangGraph docs — concepts + tutorials (state, checkpointing, human-in-the-loop)**: the how-to backbone for Stages A–B.
3. **Temporal's AI/agent guidance + one reference implementation of the durable-agent pattern** (Temporal docs/blog): map it to what you built before reading, then diff.
4. **LiteLLM docs — Router**: fallbacks, routing strategies, cost tracking per deployment.
5. **One agent-context-engineering deep dive** (e.g., Anthropic's context-engineering post or a comparable practitioner write-up on compaction/sub-agent isolation): pick one, apply it to Stage C.