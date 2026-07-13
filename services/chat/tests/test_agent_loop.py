"""Tests for POST /agent-loop — the hand-rolled tool-calling loop.

Same approach as test_extract: drive the app through httpx's ASGITransport (no
network, no server) and patch `litellm.completion` so every model turn is scripted.
Scripting the replies is what lets us prove the loop's behaviour deterministically —
that a tool round-trips, that a throwing tool is survived, that a hallucinated tool
or bad args are validated and fed back, that the iteration cap fires, and that an
upstream failure is masked.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pytest_mock import MockerFixture

from services.chat.src.agent_loop import (
    _calculator,  # pyright: ignore[reportPrivateUsage]
)
from services.chat.src.main import app


def _tool_call(name: str, arguments: str, call_id: str = "call_1") -> SimpleNamespace:
    """A stand-in for one litellm tool_call: only the fields the loop reads."""
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _reply(*tool_calls: SimpleNamespace, content: str | None = None) -> SimpleNamespace:
    """A model turn that requests one or more tools (stand-in ModelResponse)."""
    message = SimpleNamespace(content=content, tool_calls=list(tool_calls))
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _final(content: str) -> SimpleNamespace:
    """A terminal model turn: no tool calls, just the final answer."""
    message = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_tool_round_trips_then_final_answer(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # Turn 1: model asks for the calculator. Turn 2: model gives the final answer.
    completion = mocker.patch(
        "litellm.completion",
        side_effect=[
            _reply(_tool_call("calculator", '{"expression": "2 + 2"}')),
            _final("The answer is 4."),
        ],
    )

    resp = await client.post("/agent-loop", json={"query": "what is 2 + 2?"})

    assert resp.status_code == 200
    body = cast(dict[str, object], resp.json())
    assert body["answer"] == "The answer is 4."
    assert body["iterations"] == 2
    assert completion.call_count == 2  # tool turn + final turn
    steps = cast(list[dict[str, object]], body["steps"])
    assert len(steps) == 1
    assert steps[0]["tool"] == "calculator"
    assert steps[0]["ok"] is True
    assert steps[0]["result"] == '{"result": 4.0}'
    assert "X-Trace-Id" in resp.headers


async def test_throwing_tool_is_survived(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # The calculator throws on 10 / 0. The loop must catch it, feed the error back,
    # and still let the model produce a graceful final answer — never crash.
    _ = mocker.patch(
        "litellm.completion",
        side_effect=[
            _reply(_tool_call("calculator", '{"expression": "10 / 0"}')),
            _final("I can't divide by zero, sorry."),
        ],
    )

    resp = await client.post("/agent-loop", json={"query": "what is 10 / 0?"})

    assert resp.status_code == 200
    body = cast(dict[str, object], resp.json())
    assert body["answer"] == "I can't divide by zero, sorry."
    steps = cast(list[dict[str, object]], body["steps"])
    assert steps[0]["ok"] is False
    assert "ZeroDivisionError" in cast(str, steps[0]["error"])


async def test_hallucinated_tool_name_is_validated(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # The model can invent a tool that doesn't exist — it's just sampled text. The
    # loop rejects it before executing and feeds a structured error back to recover.
    _ = mocker.patch(
        "litellm.completion",
        side_effect=[
            _reply(_tool_call("teleport", '{"destination": "moon"}')),
            _final("I don't have a teleport tool."),
        ],
    )

    resp = await client.post("/agent-loop", json={"query": "teleport me"})

    assert resp.status_code == 200
    body = cast(dict[str, object], resp.json())
    steps = cast(list[dict[str, object]], body["steps"])
    assert steps[0]["ok"] is False
    assert "unknown tool 'teleport'" in cast(str, steps[0]["error"])


async def test_bad_tool_arguments_are_validated(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # Malformed JSON in the tool args must not blow up json.loads inside the loop.
    _ = mocker.patch(
        "litellm.completion",
        side_effect=[
            _reply(_tool_call("calculator", "{not valid json")),
            _final("Let me try again differently."),
        ],
    )

    resp = await client.post("/agent-loop", json={"query": "compute something"})

    assert resp.status_code == 200
    body = cast(dict[str, object], resp.json())
    steps = cast(list[dict[str, object]], body["steps"])
    assert steps[0]["ok"] is False
    assert "not valid JSON" in cast(str, steps[0]["error"])


async def test_iteration_cap_returns_typed_error(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # A model that never stops asking for tools must be capped, not run forever.
    _ = mocker.patch("services.chat.src.agent_loop.AGENT_LOOP_MAX_ITERATIONS", 2)
    completion = mocker.patch(
        "litellm.completion",
        return_value=_reply(_tool_call("calculator", '{"expression": "1 + 1"}')),
    )

    resp = await client.post("/agent-loop", json={"query": "loop forever"})

    assert resp.status_code == 422
    body = cast(dict[str, object], resp.json())
    assert body["error"] == "agent_loop_failed"
    assert body["kind"] == "max_iterations"
    assert body["iterations"] == 2
    assert completion.call_count == 2  # capped exactly at the limit
    assert "X-Trace-Id" in resp.headers


async def test_upstream_error_is_masked(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # A proxy/provider failure returns a generic 502 — the raw exception text (which
    # could leak topology) must never reach the client.
    _ = mocker.patch("litellm.completion", side_effect=Exception("boom: secret host"))

    resp = await client.post("/agent-loop", json={"query": "anything"})

    assert resp.status_code == 502
    body = cast(dict[str, object], resp.json())
    assert body["kind"] == "upstream"
    assert "boom" not in cast(str, body["detail"])
    assert "secret host" not in cast(str, body["detail"])


def test_calculator_evaluates_and_rejects_unsafe_input() -> None:
    assert _calculator("2 + 2") == 4
    assert _calculator("47 * 89") == 4183
    with pytest.raises(ZeroDivisionError):
        _ = _calculator("10 / 0")
    # Anything outside the arithmetic whitelist is rejected, never executed.
    with pytest.raises((ValueError, SyntaxError)):
        _ = _calculator("__import__('os').system('echo hi')")
