"""Minimal LiteLLM SDK client for the chat service.

Every provider call goes through the LiteLLM proxy (never direct to Anthropic /
OpenAI) — a Phase 1 acceptance criterion. The `litellm_proxy/` model prefix +
`api_base` force the SDK onto the proxy's OpenAI-compatible HTTP endpoint. Without
that prefix, `litellm.completion` would dial the provider directly and silently
bypass the gateway (and its LangFuse tracing + cross-provider fallback).

Run it:
    LITELLM_MASTER_KEY=sk-... uv run python services/chat/src/ai_client.py
"""

import os
from collections.abc import Iterator

import litellm

# Where the proxy listens (docker-compose-proxy.yml) and the bearer key it expects.
PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")


def complete(prompt: str, model: str = "primary") -> str:
    """Send a single-turn chat completion through the proxy and return the text.

    `model` is a model_name from services/proxy/config.yaml (primary / fallback),
    not a raw provider model id — the proxy resolves it and handles fallback.
    """
    # litellm ships incomplete type stubs for completion().
    response = litellm.completion(  # pyright: ignore[reportUnknownMemberType]
        model=f"litellm_proxy/{model}",
        api_base=PROXY_URL,
        api_key=MASTER_KEY,
        messages=[{"role": "user", "content": prompt}],
    )
    # Not streaming, so this is always a ModelResponse (not a CustomStreamWrapper).
    assert isinstance(response, litellm.ModelResponse)
    return response.choices[0].message.content or ""


def stream_complete(prompt: str, model: str = "primary") -> Iterator[str]:
    """Stream a single-turn completion through the proxy, yielding text deltas.

    Same routing contract as complete(); `stream=True` returns an iterator of
    chunks and each non-empty `delta.content` is yielded as it arrives.
    """
    # litellm ships incomplete type stubs for completion().
    stream = litellm.completion(  # pyright: ignore[reportUnknownMemberType]
        model=f"litellm_proxy/{model}",
        api_base=PROXY_URL,
        api_key=MASTER_KEY,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    # stream=True always yields a CustomStreamWrapper (not a ModelResponse).
    assert isinstance(stream, litellm.CustomStreamWrapper)
    for chunk in stream:
        # litellm's stub types the delta content as Unknown.
        delta: str | None = chunk.choices[0].delta.content  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if delta:
            yield delta


if __name__ == "__main__":
    if not MASTER_KEY:
        raise SystemExit("LITELLM_MASTER_KEY is unset — see .env.proxy.")

    reply = complete("In one sentence, what is an LLM gateway?")
    print(reply)
