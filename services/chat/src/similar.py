"""Similarity search for the /similar endpoint (M3).

Embeds a query, ranks a small in-memory corpus (~50 docs, see corpus.py) by
cosine similarity computed BY HAND, and returns the top-k. No vector DB — doing
the cosine once, by hand, is the whole point (concept #10 embeddings). Every
embedding call's token usage is logged with an estimated cost (concept #1
tokens); the proxy's LangFuse callback records the authoritative cost.

Design:
- The corpus is embedded ONCE, in a single batched call, into a module-level
  index cached in `_index`. Warmed at startup by the app's lifespan handler;
  built lazily on first use otherwise, so importing this module (tests,
  type-checking) never touches the network.
- The query is embedded per request. Cosine is `dot(a,b) / (||a|| * ||b||)`,
  written out explicitly — no scipy/sklearn one-liner that hides it.

The trap (M3 self-check): the corpus seeds two docs on the same topic with
opposite sentiment (corpus.TRAP_PAIR). A query about that topic scores BOTH near
the top, because the embedding encodes topical/lexical proximity, not truth or
sentiment — a high-similarity result that is the wrong answer. The fix is a
second stage (rerank / stance filter / LLM-judge over the candidates), not a
better cosine. See the README.

Provider calls go through the LiteLLM proxy via the `litellm_proxy/` prefix +
`api_base`, reusing ai_client's wiring (see its module docstring).
"""

import math
import os
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import litellm
import structlog

# Shared with ai_client / extract: same proxy endpoint + key, same LangFuse client.
from .ai_client import (
    MASTER_KEY,
    PROXY_URL,
    _langfuse,  # pyright: ignore[reportPrivateUsage]
)
from .corpus import CORPUS

# Proxy model group (services/proxy/config.yaml) — OpenAI text-embedding-3-small.
EMBEDDING_MODEL = os.environ.get("SIMILAR_EMBEDDING_MODEL", "embeddings")

# Default / max results per request (a request may ask for fewer; more is clamped).
SIMILAR_DEFAULT_K = int(os.environ.get("SIMILAR_DEFAULT_K", "5"))
SIMILAR_MAX_K = int(os.environ.get("SIMILAR_MAX_K", "20"))

# text-embedding-3-small list price, USD per 1M tokens — used only for the LOCAL
# estimate we log beside each call. LangFuse holds the authoritative cost (its
# configured model pricing). Keep in sync with the provider's price sheet.
EMBEDDING_COST_PER_1M_TOKENS = float(
    os.environ.get("SIMILAR_EMBEDDING_COST_PER_1M_TOKENS", "0.02")
)

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


@dataclass(frozen=True)
class Match:
    index: int
    score: float
    text: str


@dataclass(frozen=True)
class RankResult:
    matches: list[Match]
    query_tokens: int
    estimated_cost_usd: float
    corpus_tokens: int


@dataclass(frozen=True)
class CorpusIndex:
    docs: list[str]
    vectors: list[list[float]]
    token_count: int


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity computed by hand: dot(a, b) / (||a|| * ||b||).

    Written out on purpose (no scipy/sklearn one-liner) — doing this once is the
    whole point of M3. Returns 0.0 when either vector has zero magnitude.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _estimated_cost(tokens: int) -> float:
    return tokens / 1_000_000 * EMBEDDING_COST_PER_1M_TOKENS


def _embed(
    texts: list[str], *, trace_id: str, trace_name: str
) -> tuple[list[list[float]], int]:
    """Embed `texts` in one proxy call; return vectors (aligned to `texts`) + tokens.

    Goes through the LiteLLM proxy (never the provider directly) via the
    `litellm_proxy/` prefix + api_base, same wiring as ai_client. `metadata` rides
    in extra_body so the proxy's LangFuse callback records tokens + cost under
    trace_id.
    """
    metadata = {"trace_id": trace_id, "trace_name": trace_name}
    # litellm ships incomplete type stubs for embedding(); the call is flagged as a
    # partially-unknown member but its return is already typed EmbeddingResponse.
    response: litellm.EmbeddingResponse = litellm.embedding(  # pyright: ignore[reportUnknownMemberType]
        model=f"litellm_proxy/{EMBEDDING_MODEL}",
        api_base=PROXY_URL,
        api_key=MASTER_KEY,
        input=texts,
        extra_body={"metadata": metadata},
    )
    # data items may be plain dicts (proxy path) or Embedding objects — both
    # support subscript, so read ["index"]/["embedding"], not attributes. They
    # can arrive out of order; sort by index so vectors line up with `texts`.
    items = sorted(
        cast("list[Mapping[str, object]]", response.data),
        key=lambda it: cast(int, it["index"]),
    )
    vectors = [[float(x) for x in cast("list[float]", it["embedding"])] for it in items]
    usage = response.usage
    tokens = usage.prompt_tokens if usage is not None else 0
    return vectors, tokens


def build_index() -> CorpusIndex:
    """Embed the whole corpus once. Logs the token count + estimated cost so the
    paper estimate can be compared against the LangFuse trace (#1 tokens)."""
    trace_id = uuid.uuid4().hex
    vectors, tokens = _embed(
        list(CORPUS), trace_id=trace_id, trace_name="similar_corpus_index"
    )
    log.info(
        "corpus_embedded",
        trace_id=trace_id,
        docs=len(CORPUS),
        tokens=tokens,
        estimated_cost_usd=_estimated_cost(tokens),
    )
    return CorpusIndex(docs=list(CORPUS), vectors=vectors, token_count=tokens)


_index: CorpusIndex | None = None


def get_index() -> CorpusIndex:
    """Return the corpus index, building (and caching) it on first use.

    Warmed at startup by the app's lifespan handler; lazy so imports and tests
    stay network-free until the index is actually needed.
    """
    global _index
    if _index is None:
        _index = build_index()
    return _index


def reset_index() -> None:
    """Drop the cached index (test hook)."""
    global _index
    _index = None


def _record(trace_id: str, *, query_tokens: int) -> None:
    """Attach the query token count to the LangFuse trace. Never raises —
    observability must not break the response."""
    try:
        _langfuse.create_score(
            trace_id=trace_id,
            name="query_tokens",
            value=query_tokens,
            data_type="NUMERIC",
        )
    except Exception as exc:
        log.warning("langfuse_score_failed", trace_id=trace_id, error=str(exc))


def rank(query: str, k: int, *, trace_id: str) -> RankResult:
    """Embed the query, score it against every corpus doc by hand, return top-k."""
    index = get_index()
    vectors, tokens = _embed([query], trace_id=trace_id, trace_name="similar")
    query_vec = vectors[0]
    log.info(
        "query_embedded",
        trace_id=trace_id,
        tokens=tokens,
        estimated_cost_usd=_estimated_cost(tokens),
    )
    _record(trace_id, query_tokens=tokens)

    scored = [
        Match(index=i, score=cosine_similarity(query_vec, vec), text=index.docs[i])
        for i, vec in enumerate(index.vectors)
    ]
    scored.sort(key=lambda m: m.score, reverse=True)
    return RankResult(
        matches=scored[:k],
        query_tokens=tokens,
        estimated_cost_usd=_estimated_cost(tokens),
        corpus_tokens=index.token_count,
    )
