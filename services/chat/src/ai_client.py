"""Minimal LiteLLM SDK client for the chat service.

Every provider call goes through the LiteLLM proxy (never direct to Anthropic /
OpenAI) — a Phase 1 acceptance criterion. The `litellm_proxy/` model prefix +
`api_base` force the SDK onto the proxy's OpenAI-compatible HTTP endpoint. Without
that prefix, `litellm.completion` would dial the provider directly and silently
bypass the gateway (and its LangFuse tracing + cross-provider fallback).

The proxy's LangFuse callback records each generation (tokens + cost) under the
`trace_id` we pass in `metadata`. We then attach TTFT and total latency to that
same trace as NUMERIC scores — LangFuse merges them by trace_id, so no lookup is
needed. `session_id` groups a conversation's turns into one LangFuse session.

Prompt caching: a fixed system prompt (loaded from system_prompt.md) is prepended
as the stable prefix and marked with an Anthropic `cache_control` breakpoint, so its
tokens are cached and re-read at a discount on repeat calls (the growing history
after it is never cached). The prefix must stay byte-identical and clear the
provider's minimum cacheable length — 4096 tokens for Haiku 4.5 — or nothing caches.
Cache hits show up as cache_read tokens in the LangFuse trace.

Run it:
    LITELLM_MASTER_KEY=sk-... uv run python services/chat/src/ai_client.py
"""

import os
import time
import uuid
from collections.abc import Iterator, Mapping
from pathlib import Path

import litellm
import structlog
from langfuse import Langfuse

# Where the proxy listens (docker-compose-proxy.yml) and the bearer key it expects.
PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

# structlog.get_logger() is typed as Any by design; pin a concrete bound-logger type.
log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

# Direct LangFuse client, used only to attach latency scores to the trace the proxy
# creates. No-ops if the keys are unset (e.g. in tests), so import stays cheap. Our
# env var is LANGFUSE_HOST (LiteLLM's name); the SDK also accepts it as `host`.
_langfuse = Langfuse(
    public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
    secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    host=os.environ.get("LANGFUSE_HOST"),
)

# The stable system prefix that gets cached, kept in its own file so it can grow
# without fighting the 88-col lint and so it reads as a versioned prompt asset. It is
# deliberately long: Anthropic only caches a prefix once it clears a minimum token
# count — 4096 tokens for Haiku 4.5 (our `primary`) — so a short prompt would be
# marked cacheable yet never produce a cache hit. It must stay BYTE-IDENTICAL across
# requests; any per-request value (timestamp, user id) baked in here would change the
# prefix and defeat the cache. Every edit is one cache miss for the first call after.
SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text().strip()


def _cached_system_message() -> dict[str, object]:
    """The stable system prefix as an Anthropic cache breakpoint.

    Everything up to and including this block is cached; the variable conversation
    history that follows it is not. The `cache_control` marker is what opts this
    prefix into caching — without it Anthropic caches nothing (unlike OpenAI, which
    caches long prefixes automatically). LiteLLM forwards the marker to the provider.
    """
    return {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
    }


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


def _record_metrics(
    trace_id: str, session_id: str | None, ttft_ms: float | None, total_ms: float
) -> None:
    """Log TTFT + total latency and attach them to the LangFuse trace.

    Never raises: observability must not break the user's stream.
    """
    log.info(
        "chat_stream",
        trace_id=trace_id,
        session_id=session_id,
        ttft_ms=ttft_ms,
        total_latency_ms=total_ms,
    )
    try:
        if ttft_ms is not None:
            _langfuse.create_score(
                trace_id=trace_id, name="ttft_ms", value=ttft_ms, data_type="NUMERIC"
            )
        _langfuse.create_score(
            trace_id=trace_id,
            name="total_latency_ms",
            value=total_ms,
            data_type="NUMERIC",
        )
    except Exception as exc:
        log.warning("langfuse_score_failed", trace_id=trace_id, error=str(exc))


def stream_complete(
    messages: list[dict[str, str]],
    *,
    trace_id: str,
    session_id: str | None = None,
    model: str = "primary",
) -> Iterator[str]:
    """Stream a completion through the proxy, yielding text deltas as they arrive.

    `messages` is the full conversation history (OpenAI role/content dicts). A cached
    system prefix is prepended; TTFT is the wall-clock to the first non-empty delta and
    total latency is the whole stream. Both are logged to the LangFuse trace identified
    by `trace_id` once the stream ends (or the client disconnects, via the finally).
    """
    metadata: dict[str, str] = {"trace_id": trace_id, "trace_name": "chat"}
    if session_id:
        metadata["session_id"] = session_id

    # Cached stable prefix first, then the variable client history. The system block
    # is byte-identical every request, so its tokens are re-read from cache after the
    # first call; the history after it changes every turn and is never cached.
    full_messages: list[Mapping[str, object]] = [_cached_system_message(), *messages]

    start = time.perf_counter()
    # metadata rides in extra_body so it reaches the PROXY request body (where its
    # LangFuse callback reads trace_id/session_id). The litellm SDK's own `metadata=`
    # kwarg is consumed locally in proxy mode and never forwarded.
    # litellm ships incomplete type stubs for completion().
    stream = litellm.completion(  # pyright: ignore[reportUnknownMemberType]
        model=f"litellm_proxy/{model}",
        api_base=PROXY_URL,
        api_key=MASTER_KEY,
        messages=full_messages,
        stream=True,
        extra_body={"metadata": metadata},
    )
    # stream=True always yields a CustomStreamWrapper (not a ModelResponse).
    assert isinstance(stream, litellm.CustomStreamWrapper)

    ttft_ms: float | None = None
    try:
        for chunk in stream:
            # litellm's stub types the delta content as Unknown.
            delta: str | None = chunk.choices[0].delta.content  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if delta:
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - start) * 1000
                yield delta
    finally:
        total_ms = (time.perf_counter() - start) * 1000
        _record_metrics(trace_id, session_id, ttft_ms, total_ms)


if __name__ == "__main__":
    if not MASTER_KEY:
        raise SystemExit("LITELLM_MASTER_KEY is unset — see .env.proxy.")

    history = [{"role": "user", "content": "In one sentence, what is an LLM gateway?"}]
    for token in stream_complete(
        history, trace_id=uuid.uuid4().hex, session_id=uuid.uuid4().hex
    ):
        print(token, end="", flush=True)
    print()
