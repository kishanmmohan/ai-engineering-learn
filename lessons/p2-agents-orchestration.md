# P2 · Agents & Orchestration

> **Production AI Learning Plan · Unit P2**

An agent is a state machine with a probabilistic core — design for the loop, not the demo. This unit covers agent architectures, tool design, and the control surfaces (guards, degradation, streaming) that separate a demo from a service.

**~1 week · Core · 3 lessons · Capstone Stage 2 · Exit check gates P3**

**On this page:** [2.1 Agent architectures](#21-agent-architectures) · [2.2 Tools & protocols](#22-tools--protocols) · [2.3 Control & streaming](#23-control--streaming) · [Capstone Stage 2](#capstone--stage-2--agentify-two-tool-streaming-agent) · [Practice](#practice--hands-on-probes) · [Exit check](#exit-check)

---

## 2.1 Agent architectures

*The whole thing is a loop. Everything else is scaffolding around the loop.*

### The loop, made explicit

P0 §0.4 gave you the tool-calling protocol. An agent is that protocol run in a loop, plus state, plus stop conditions:

```
while not done and iterations < MAX:
    response = model(state)                    # returns text or tool requests
    if response.tool_calls:
        results = [execute(validate(c)) for c in response.tool_calls]
        state.append(results)                  # observe
    else:
        done = True                            # final answer
```

Hand-roll this once before touching a framework — you'll know exactly what the framework abstracts, and what it hides.

### The workflow-vs-agent spectrum

- **Workflow:** you fix the control flow (a DAG of steps); the model fills in the steps. Predictable, testable, debuggable.
- **Agent:** the model chooses the control flow (which tool, when, how many times). Flexible, and unpredictable in proportion.
- The design rule: **use the least autonomy that solves the task.** A pipeline that's always retrieve → answer should be a workflow, not an agent deciding to retrieve. Reserve model-driven control flow for genuinely dynamic tasks.

### State machines, checkpoints, persistence

- Model the agent as an explicit **state machine** (frameworks like LangGraph formalize this): a typed state schema, nodes as functions that read/write state, edges as routing — conditional on state, not vibes.
- **Checkpointing:** persist state after every step. This buys you: resume after crash, replay for debugging, time-travel to inspect where a run went wrong, and pause-for-human-approval.
- Keep state lean. Every step's output that lands in state lands in the *context* of every later model call — state accretion is a token bill and a lost-in-the-middle problem (P0 §0.1).

> **Systems analogy** — This is a distributed saga: a sequence of steps with retries, compensation, and persisted progress — where one participant (the model) is flaky in a novel way: it returns HTTP 200 with wrong decisions. Checkpointing is event sourcing for that saga.

> **Failure modes to internalize**
>
> - Hidden state — anything the loop depends on that isn't in the state schema can't be resumed or replayed.
> - Unbounded loops — no iteration cap means the failure mode is your API bill.
> - State accretion — turn 9 costs multiples of turn 1 and answers get *worse* as context bloats.

---

## 2.2 Tools & protocols

*The model chooses tools by reading descriptions. Your tool surface is a prompt.*

### Tool design rules

- **Small, typed, single-purpose.** One tool that does one thing beats a Swiss-army tool with a `mode` argument. Typed arguments (schema) let you validate at the boundary.
- **Descriptions are prompts.** The model picks a tool by its name and description — vague or overlapping descriptions produce wrong tool choices. Write them like API docs for a hurried junior engineer.
- **Idempotent where possible.** The loop retries; a re-run tool call must be safe (you know this discipline already).
- **Return structured errors the model can act on.** `{"error": "date_range_invalid", "hint": "use YYYY-MM-DD"}` lets the model correct and retry. A stack trace teaches it nothing — and often leaks internals.
- **Bound tool output size.** A tool that returns 40k tokens of JSON just detonated your context budget. Truncate, summarize, or paginate at the tool boundary.

### Tool surface discipline

- More tools ≠ more capable. Past a dozen-ish tools, wrong-tool choices climb. Group related operations, namespace clearly, and cut tools the agent never uses.
- **Least privilege:** the agent gets exactly the tools the task needs — an allow-list per agent, not a global toolbox. (P5 makes this a security control; here it's also a quality control.)

### MCP — tools as a protocol

- MCP (Model Context Protocol) standardizes the tool interface: tool servers expose typed tools with descriptions; any compliant agent/client can discover and call them.
- The concept matters beyond the spec: **decouple tool providers from agents.** Tools become infrastructure — versioned, shared, independently testable — instead of code welded into one agent.

> **Failure modes to internalize**
>
> - Two tools with overlapping descriptions — the model alternates between them unpredictably.
> - Tools returning prose — the model paraphrases the paraphrase; data degrades per hop.
> - A "helpful" tool that hides failures (returns empty list on error) — the agent confidently reports "no results".

---

## 2.3 Control & streaming

*Guards are not optional extras. They are the difference between an agent and an incident.*

### The guard set

Every production agent carries, minimum:

- **Iteration cap** — hard stop on the loop (start ~5–10).
- **Per-tool timeout** — a hung tool must not hang the run.
- **Token/spend budget** — a run that exceeds its budget stops and reports, rather than burning on.
- **Terminal behavior** — when a guard trips, the agent produces an honest partial answer or a clean failure — never silence.

### Graceful degradation

- Design the dependency-down path explicitly: vector store unreachable → the agent says "I can't search the documents right now" — it must **not** answer from parametric memory as if it had searched. That's the agent-flavored version of P0's "specify the failure path".
- Degradation is code you must test. An untested fallback path is dark code that fails the first time it matters (drill it — the capstone does).

### Streaming

- Long generations demand streaming (P0 §0.1: perceived latency collapses to TTFT). For agents, stream **events, not just tokens**: `tool_started("search")`, `tool_finished`, then answer tokens. Users trust a system they can watch thinking; a 20-second silent spinner reads as broken.
- SSE (server-sent events) is the plain-HTTP workhorse. Always terminate the stream with an explicit final event — a stream that just stops leaves the client guessing whether it's done or dead.

### Human-in-the-loop

- For irreversible or expensive actions, checkpoint and pause *before* the action; a human approves, edits, or rejects; the run resumes from the checkpoint. This is checkpointing earning its keep — approval gates are just a pause at a node.

> **Systems analogy** — Guards are circuit breakers and bulkheads; degradation paths are your fallback handlers; streaming events are progress heartbeats. The novelty is only *why*: the unreliable component fails by confidently doing the wrong thing, so the guards must bound blast radius, not just detect crashes.

---

## Capstone · Stage 2 — Agentify: two-tool streaming agent

Upgrade your Stage-1 QA system into an agent:

1. **Tools:** wrap Stage-1 search as a typed tool (`query`, `top_k`, optional filters); add a second tool — a calculator or unit converter (cheap, and forces multi-tool routing).
2. **Graph:** plan → tool → observe → answer, with conditional routing and an iteration cap of 5.
3. **Failure drill:** stop the vector store mid-run. The agent must degrade honestly — visible message, no fabricated search results.
4. **Streaming:** an HTTP endpoint streaming tool events + answer tokens over SSE, with a terminal event.
5. **Checkpointing:** kill the process after the first tool call; resume from the checkpoint and complete the run.

> **Solid when:** it streams, survives a dead dependency honestly, and resumes from a checkpoint.

**Tooling →** LangGraph (or the hand-rolled loop first — worth doing once) · FastAPI + SSE · MCP SDK optional

---

## Practice — hands-on probes

1. Hand-roll the agent loop with no framework: while-loop, parse tool calls, validate, execute, append.
   *Exit: you know exactly what a framework abstracts — and what it hides.*
2. Give the agent two deliberately overlapping tools. Watch it choose wrong. Fix it by editing **descriptions only**.
   *Exit: descriptions-are-prompts, felt in your own transcript.*
3. Make a tool throw. Compare agent behavior when it receives a raw exception vs a structured error with a hint.
   *Exit: error-shape design changes agent behavior, demonstrated.*
4. Remove the iteration cap and give an impossible task — with a hard spend budget as your safety net. Watch the loop not converge.
   *Exit: you've seen a runaway with your own eyes; caps become non-negotiable.*
5. Add SSE streaming; consume it with `curl`. Kill the server mid-stream.
   *Exit: the client sees a terminal event — or you now know why it must.*
6. Checkpoint + resume: kill the process after tool call #1, restart, resume to completion.
   *Exit: durable agent state, demonstrated.*

---

## Exit check

*Answer each from memory, out loud. Tick a box only when you could defend the answer to a colleague. All six → start P3.*

- [ ] When do you build a workflow instead of an agent? State the deciding test in one sentence.
- [ ] Your agent called the wrong tool. Name the three most likely causes, in order of likelihood.
- [ ] What belongs in a tool's error response, and why is a stack trace worse than useless?
- [ ] Name the four guards every production agent carries, and what each does when it trips.
- [ ] Why stream events and not just tokens — and why must every stream end with a terminal event?
- [ ] A dependency dies mid-run. Walk through, step by step, what your agent does — and what it must never do.

---

*Unit P2 of the [Production AI learning plan](./learning-plan.md) · previous: [P1 — Production RAG](./p1-production-rag.md) · next: [P3 — Evals](./p3-evals.md)*
