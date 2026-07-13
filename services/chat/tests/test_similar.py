"""Tests for POST /similar — embeddings + cosine-by-hand ranking (M3).

Like test_extract.py, these drive the FastAPI app through httpx's ASGITransport
and patch `litellm.embedding` so no provider call is made. Embedding vectors are
scripted so ranking is deterministic: the corpus is embedded as 50-dim one-hot
vectors, except the trap pair (docs 48/49) which share a direction — so a query
aimed at that direction ranks BOTH of them top, which is the point of the trap.
"""

from collections.abc import AsyncIterator, Iterator
from types import SimpleNamespace
from typing import cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pytest_mock import MockerFixture

from services.chat.src.corpus import CORPUS, TRAP_PAIR
from services.chat.src.main import app
from services.chat.src.similar import SIMILAR_MAX_K, cosine_similarity, reset_index

N = len(CORPUS)


def _one_hot(i: int) -> list[float]:
    v = [0.0] * N
    v[i] = 1.0
    return v


# Corpus vectors: one-hot per doc, except the trap pair shares one direction so
# nothing but each other (and a query pointed there) sits close to them.
_CORPUS_VECTORS: list[list[float]] = [_one_hot(i) for i in range(N)]
_TRAP_DIRECTION = [0.0] * N
_TRAP_DIRECTION[TRAP_PAIR[0]] = 1.0
_TRAP_DIRECTION[TRAP_PAIR[1]] = 1.0
_CORPUS_VECTORS[TRAP_PAIR[0]] = list(_TRAP_DIRECTION)
_CORPUS_VECTORS[TRAP_PAIR[1]] = list(_TRAP_DIRECTION)


def _embed_reply(vectors: list[list[float]], tokens: int) -> SimpleNamespace:
    """Stand-in for a litellm EmbeddingResponse: only the fields _embed reads.

    Through the proxy path, data items arrive as plain dicts (not objects), and
    _embed reads them via subscript — mirror that real shape here. usage stays a
    real object (litellm Usage), so attribute access is correct.
    """
    data = [{"index": i, "embedding": v} for i, v in enumerate(vectors)]
    return SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=tokens))


def _embedder(query_vec: list[float]):
    """A litellm.embedding side_effect: corpus batch vs. single-query call."""

    def _side_effect(*_args: object, **kwargs: object) -> SimpleNamespace:
        texts = cast(list[object], kwargs["input"])
        if len(texts) == 1:
            return _embed_reply([query_vec], tokens=7)
        return _embed_reply(_CORPUS_VECTORS, tokens=1000)

    return _side_effect


@pytest.fixture(autouse=True)
def _fresh_index() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    reset_index()
    yield
    reset_index()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_cosine_similarity_is_computed_by_hand() -> None:
    assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero-norm guard


async def test_top_k_ranks_nearest_doc_first(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    _ = mocker.patch("litellm.embedding", side_effect=_embedder(_one_hot(5)))

    resp = await client.post("/similar", json={"query": "anything", "k": 3})

    assert resp.status_code == 200
    body = cast(dict[str, object], resp.json())
    matches = cast(list[dict[str, object]], body["matches"])
    assert len(matches) == 3
    assert matches[0]["index"] == 5
    assert matches[0]["score"] == pytest.approx(1.0)
    assert body["query_tokens"] == 7
    assert body["corpus_tokens"] == 1000
    assert "X-Trace-Id" in resp.headers


async def test_trap_pair_both_rank_high(
    client: AsyncClient, mocker: MockerFixture
) -> None:
    # A query pointed at the trap direction is equally close to BOTH trap docs:
    # cosine can't tell the positive-sentiment doc from the negative one.
    _ = mocker.patch("litellm.embedding", side_effect=_embedder(list(_TRAP_DIRECTION)))

    resp = await client.post(
        "/similar", json={"query": "battery life after the firmware update", "k": 2}
    )

    assert resp.status_code == 200
    body = cast(dict[str, object], resp.json())
    matches = cast(list[dict[str, object]], body["matches"])
    assert {cast(int, m["index"]) for m in matches} == set(TRAP_PAIR)
    for m in matches:
        assert m["score"] == pytest.approx(1.0)


async def test_k_is_clamped_to_max(client: AsyncClient, mocker: MockerFixture) -> None:
    _ = mocker.patch("litellm.embedding", side_effect=_embedder(_one_hot(0)))

    resp = await client.post("/similar", json={"query": "x", "k": 999})

    assert resp.status_code == 200
    body = cast(dict[str, object], resp.json())
    matches = cast(list[dict[str, object]], body["matches"])
    assert len(matches) == SIMILAR_MAX_K
