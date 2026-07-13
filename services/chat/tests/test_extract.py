"""Tests for POST /extract — the structured-extraction endpoint.

These are the first tests in the repo. They drive the FastAPI app through httpx's
ASGITransport (no network, no server) and patch `litellm.completion` so no provider
call is made — every LLM reply is scripted, which is what lets us assert the retry
loop fires and the typed error is returned deterministically.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pytest_mock import MockerFixture

from services.chat.src.main import app

# A small, well-formed schema and a value that satisfies it.
SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
    "additionalProperties": False,
}
VALID_JSON = '{"name": "Ada", "age": 36}'


def _reply(content: str) -> SimpleNamespace:
    """A stand-in for a litellm ModelResponse: only the fields extract() reads."""
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_valid_input_returns_schema_valid_json(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    completion = mocker.patch("litellm.completion", return_value=_reply(VALID_JSON))

    resp = await client.post(
        "/extract", json={"text": "Ada is 36.", "json_schema": SCHEMA, "mode": "native"}
    )

    assert resp.status_code == 200
    assert resp.json() == {"name": "Ada", "age": 36}
    assert completion.call_count == 1
    assert "X-Trace-Id" in resp.headers


async def test_retry_fires_then_succeeds(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # First reply is not JSON at all -> parse failure -> re-prompt -> valid.
    completion = mocker.patch(
        "litellm.completion",
        side_effect=[_reply("here you go: not json"), _reply(VALID_JSON)],
    )

    resp = await client.post(
        "/extract", json={"text": "Ada is 36.", "json_schema": SCHEMA}
    )

    assert resp.status_code == 200
    assert resp.json() == {"name": "Ada", "age": 36}
    assert completion.call_count == 2  # the retry loop fired exactly once


async def test_exhausted_retries_return_typed_error(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    _ = mocker.patch("services.chat.src.extract.EXTRACT_MAX_RETRIES", 1)  # 2 attempts
    # Valid JSON but always missing a required field -> schema failure every time.
    completion = mocker.patch(
        "litellm.completion", return_value=_reply('{"name": "Ada"}')
    )

    resp = await client.post(
        "/extract", json={"text": "Ada.", "json_schema": SCHEMA, "mode": "native"}
    )

    assert resp.status_code == 422
    body = cast(dict[str, object], resp.json())
    assert body["error"] == "extraction_failed"
    assert body["kind"] == "schema"
    assert body["attempts"] == 2
    assert completion.call_count == 2  # N+1 attempts, then the typed error
    assert "X-Trace-Id" in resp.headers  # trace still exists for the failed run


async def test_malformed_schema_is_rejected_without_calling_model(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    completion = mocker.patch("litellm.completion")

    resp = await client.post(
        "/extract",
        json={"text": "anything", "json_schema": {"type": "not-a-real-type"}},
    )

    assert resp.status_code == 422
    assert resp.json()["kind"] == "bad_schema"
    completion.assert_not_called()  # rejected before any provider call


async def test_native_mode_enforces_schema_prompt_mode_does_not(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # Both modes are sent response_format=..., but only native carries a json_schema
    # block; prompt mode passes None (enforcement is prompt-only). This is the knob
    # Break-It #2 flips to compare native vs. prompt failure rates.
    completion = mocker.patch("litellm.completion", return_value=_reply(VALID_JSON))

    _ = await client.post(
        "/extract", json={"text": "Ada is 36.", "json_schema": SCHEMA, "mode": "native"}
    )
    native_rf = cast(dict[str, object], completion.call_args.kwargs["response_format"])
    assert native_rf["type"] == "json_schema"

    completion.reset_mock()
    _ = await client.post(
        "/extract", json={"text": "Ada is 36.", "json_schema": SCHEMA, "mode": "prompt"}
    )
    assert completion.call_args.kwargs["response_format"] is None
