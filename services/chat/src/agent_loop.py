"""Hand-rolled tool-calling loop for the /agent-loop endpoint.

This is the raw orchestrator every agent framework (Phase 3's LangGraph, etc.) is
sugar over. There is NO framework here. We:

  1. define tool schemas and send them with the request,
  2. detect when the model wants a tool (it emits a tool call — through the LiteLLM
     proxy, Anthropic's `stop_reason: tool_use` is normalized to the OpenAI shape, so
     we read `message.tool_calls`, not a raw `stop_reason` string),
  3. execute the tool IN OUR OWN CODE — the model executes nothing; it only asks,
  4. append the result to the transcript and resend the whole thing,
  5. repeat until the model stops asking for tools and emits a final answer.

Two things the exercise deliberately stresses (Phase 1 concepts #4 tool loop and
#7 failure handling):

- A tool request is just sampled text, so it can hallucinate a tool name or malformed
  args. We VALIDATE the request before executing (unknown name / un-parseable args) and
  feed a structured error back as the tool result instead of trusting it.
- One tool (`calculator`) can THROW (division by zero, unsupported expression). The
  conversation must SURVIVE that: we catch any exception, feed the error back as the
  tool result, and let the model recover. A throwing tool must never crash the loop.

The loop is CAPPED (AGENT_LOOP_MAX_ITERATIONS) so a model that keeps calling tools
forever is turned into a typed error, not an infinite spend.

Provider calls go through the LiteLLM proxy via the `litellm_proxy/` prefix +
`api_base`, reusing the same wiring as ai_client (see its module docstring). Every
iteration carries the same `trace_id`, so the whole multi-call sequence is one
coherent LangFuse trace.
"""

import ast
import json
import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast, final

import litellm
import structlog

# _langfuse is module-private in ai_client but deliberately shared here, exactly as
# /extract does: every endpoint attaches scores to the same LangFuse instance.
from .ai_client import (
    MASTER_KEY,
    PROXY_URL,
    _langfuse,  # pyright: ignore[reportPrivateUsage]
)

# Hard cap on tool-calling rounds. Without it a model that keeps asking for tools
# (or two tools that ping-pong) would loop until it exhausts spend — the #4 guard.
AGENT_LOOP_MAX_ITERATIONS = int(os.environ.get("AGENT_LOOP_MAX_ITERATIONS", "6"))

# Greedy decoding (temperature 0): this is a task endpoint, not a chat, so we want
# the mode of the next-token distribution, not variety — same reasoning as /extract.
AGENT_LOOP_TEMPERATURE = float(os.environ.get("AGENT_LOOP_TEMPERATURE", "0"))

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


# --- The two tools ------------------------------------------------------------
#
# Each tool is (a) a plain Python callable we run ourselves and (b) an OpenAI-shaped
# JSON schema we hand to the model so it knows the tool exists and how to call it.


def _eval_node(node: ast.expr) -> float:
    """Recursively evaluate a whitelisted arithmetic AST node.

    Only numeric literals, the binary ops + - * / // % **, and unary +/- are allowed.
    Anything else (names, calls, attribute access, subscripts — whatever a hallucinated
    or hostile expression might smuggle in) raises ValueError. This is why we parse an
    AST instead of using the builtin eval(), which would happily run
    `__import__('os').system(...)`.
    """
    if isinstance(node, ast.Constant):
        value = node.value
        # bool subclasses int; reject it so `True + 1` isn't silently "arithmetic".
        if isinstance(value, bool):
            raise ValueError("booleans are not valid numbers")
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError(f"unsupported constant: {value!r}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right  # ZeroDivisionError propagates — the tool CAN throw
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        if isinstance(op, ast.Pow):
            # math.pow returns a real float (the `**` operator is typed Any because a
            # fractional power of a negative base is complex); a domain error like
            # (-8) ** 0.5 raises ValueError, which the loop catches as a tool error.
            return math.pow(left, right)
        raise ValueError(f"unsupported operator: {type(op).__name__}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        op = node.op
        if isinstance(op, ast.UAdd):
            return +operand
        if isinstance(op, ast.USub):
            return -operand
        raise ValueError(f"unsupported unary operator: {type(op).__name__}")
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def _calculator(expression: str) -> float:
    """Evaluate a basic arithmetic expression safely (never eval()).

    Supports + - * / // % ** and parentheses over numeric literals. This is the tool
    that CAN throw: a malformed expression raises (SyntaxError from ast.parse or
    ValueError from the whitelist walk) and `10 / 0` raises ZeroDivisionError. The
    loop must catch these and let the model recover — it must not crash.
    """
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body)


# A deterministic stub — no network, no keys, never throws. The point of /agent-loop
# is the LOOP, not real weather; a canned lookup keeps the demo reproducible.
_WEATHER: dict[str, str] = {
    "paris": "18°C, light rain",
    "tokyo": "26°C, humid",
    "london": "14°C, overcast",
    "san francisco": "15°C, foggy",
    "new york": "21°C, clear",
}


def _weather(city: str) -> dict[str, str]:
    """Stub weather tool. Deterministic canned data; unknown cities get a default."""
    conditions = _WEATHER.get(city.strip().lower(), "22°C, clear")
    return {"city": city, "conditions": conditions}


# Registry: name -> callable. The model names a tool; we look it up here. If the name
# isn't in this dict, the request is a hallucination and we reject it (see the loop).
TOOL_FNS: dict[str, Callable[..., object]] = {
    "calculator": _calculator,
    "weather": _weather,
}

# The schemas we advertise to the model. Kept in the OpenAI function-calling shape;
# the proxy translates this per provider (for Anthropic `primary` it becomes native
# tool use). Descriptions matter — they're how the model decides when to call each.
TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate a basic arithmetic expression and return the numeric result. "
                "Supports + - * / // % ** and parentheses over numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The arithmetic expression, e.g. '47 * 89'.",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get the current weather conditions for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city name, e.g. 'Paris'.",
                    }
                },
                "required": ["city"],
            },
        },
    },
]


# --- Typed results ------------------------------------------------------------


@final
@dataclass
class AgentStep:
    """One tool call the model made and what our code did with it.

    Captured so the endpoint can return a trace of the loop — the whole point of a
    learning workbench is being able to SEE who executed what.
    """

    tool: str
    arguments: str  # the raw JSON args string as the model produced it
    ok: bool  # did the tool run cleanly?
    result: str | None = None  # JSON-serialized return value on success
    error: str | None = None  # structured error (validation or exception) on failure


@final
@dataclass
class AgentLoopResult:
    final_answer: str
    iterations: int
    steps: list[AgentStep] = field(default_factory=list)


@final
class AgentLoopError(Exception):
    """Raised when the loop hits its iteration cap without a final answer.

    Carries structured fields so the endpoint can render a typed error body — the
    same contract as extract.ExtractionError.
    """

    def __init__(
        self,
        *,
        iterations: int,
        reason: Literal["max_iterations"],
        detail: str,
    ) -> None:
        self.iterations: int = iterations
        self.reason: Literal["max_iterations"] = reason
        self.detail: str = detail
        super().__init__(
            f"agent loop failed after {iterations} iteration(s) ({detail})"
        )


def _record(trace_id: str, *, iterations: int, outcome: str) -> None:
    """Attach iteration count + outcome to the LangFuse trace. Never raises —
    observability must not turn a working loop into an error."""
    try:
        _langfuse.create_score(
            trace_id=trace_id,
            name="agent_loop_iterations",
            value=iterations,
            data_type="NUMERIC",
        )
        _langfuse.create_score(
            trace_id=trace_id,
            name="agent_loop_outcome",
            value=outcome,
            data_type="CATEGORICAL",
        )
    except Exception as exc:
        log.warning("langfuse_score_failed", trace_id=trace_id, error=str(exc))


_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools. Use a tool when it helps you "
    "answer; otherwise just answer directly. When you have enough information, give a "
    "concise final answer to the user with no tool call."
)


def _execute_tool(name: str, raw_args: str) -> tuple[bool, str]:
    """Validate then run one tool request. Returns (ok, content_for_model).

    `content_for_model` is a JSON string that goes back to the model as the tool
    result — on success `{"result": ...}`, on any failure `{"error": ...}`. Both the
    validation failures (hallucinated name, un-parseable args) and a real exception
    from the tool land here as a structured error the model can read and recover from.
    Nothing in here raises: that is the guarantee the loop depends on.
    """
    fn = TOOL_FNS.get(name)
    if fn is None:
        # The model invented a tool that doesn't exist — it's just sampled text.
        available = ", ".join(sorted(TOOL_FNS))
        return False, json.dumps(
            {"error": f"unknown tool '{name}'; available tools: {available}"}
        )

    try:
        loaded = cast(object, json.loads(raw_args or "{}"))
    except json.JSONDecodeError as exc:
        return False, json.dumps({"error": f"arguments were not valid JSON: {exc}"})
    if not isinstance(loaded, dict):
        return False, json.dumps(
            {"error": "arguments must be a JSON object of named parameters"}
        )
    args = cast(dict[str, object], loaded)

    try:
        result = fn(**args)
    except Exception as exc:
        # The tool threw (e.g. calculator on 10/0 or a bad expression, or a wrong
        # arg name). Feed the error back as the tool result; the conversation
        # survives and the model gets a chance to fix its request or explain.
        return False, json.dumps({"error": f"{type(exc).__name__}: {exc}"})

    return True, json.dumps({"result": result})


def run_agent_loop(
    *,
    query: str,
    trace_id: str,
    model: str = "primary",
) -> AgentLoopResult:
    """Run the tool-calling loop until the model emits a final answer.

    Each iteration is one proxy call carrying the same `trace_id`, so the whole
    sequence shows up as multiple generations under one LangFuse trace. Raises
    AgentLoopError once AGENT_LOOP_MAX_ITERATIONS is spent without a final answer.
    """
    messages: list[dict[str, object]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    steps: list[AgentStep] = []

    for iteration in range(1, AGENT_LOOP_MAX_ITERATIONS + 1):
        metadata = {
            "trace_id": trace_id,
            "trace_name": "agent_loop",
            "agent_loop_iteration": str(iteration),
        }
        # metadata rides in extra_body so the proxy's LangFuse callback sees it (the
        # SDK's own metadata= kwarg is consumed locally in proxy mode). cast() narrows
        # the non-streaming return to ModelResponse — litellm ships incomplete stubs.
        response = cast(
            litellm.ModelResponse,
            litellm.completion(  # pyright: ignore[reportUnknownMemberType]
                model=f"litellm_proxy/{model}",
                api_base=PROXY_URL,
                api_key=MASTER_KEY,
                messages=messages,
                temperature=AGENT_LOOP_TEMPERATURE,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                extra_body={"metadata": metadata},
            ),
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        # No tool calls -> the model is done and this is the final answer.
        if not tool_calls:
            final_answer = message.content or ""
            log.info(
                "agent_loop_success",
                trace_id=trace_id,
                iterations=iteration,
                tool_calls=len(steps),
            )
            _record(trace_id, iterations=iteration, outcome="success")
            return AgentLoopResult(
                final_answer=final_answer, iterations=iteration, steps=steps
            )

        # The model wants tools. Append the assistant turn EXACTLY as it must be
        # replayed (content may be None alongside tool_calls), built explicitly so
        # it's provider-agnostic and testable, then execute each requested call.
        assistant_tool_calls: list[dict[str, object]] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ]
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": assistant_tool_calls,
            }
        )

        for tc in tool_calls:
            name = tc.function.name or ""
            raw_args = tc.function.arguments or ""
            ok, content = _execute_tool(name, raw_args)
            log.info(
                "agent_loop_tool_call",
                trace_id=trace_id,
                iteration=iteration,
                tool=name,
                ok=ok,
            )
            steps.append(
                AgentStep(
                    tool=name,
                    arguments=raw_args,
                    ok=ok,
                    result=content if ok else None,
                    error=None if ok else content,
                )
            )
            # The tool result goes back as a `tool` message keyed to the call id, so
            # the model can read what our code produced and continue the conversation.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content,
                }
            )

    # Fell out of the loop: the model never stopped asking for tools.
    log.warning(
        "agent_loop_exhausted",
        trace_id=trace_id,
        iterations=AGENT_LOOP_MAX_ITERATIONS,
    )
    _record(trace_id, iterations=AGENT_LOOP_MAX_ITERATIONS, outcome="max_iterations")
    raise AgentLoopError(
        iterations=AGENT_LOOP_MAX_ITERATIONS,
        reason="max_iterations",
        detail="tool-call loop did not converge within the iteration cap",
    )
