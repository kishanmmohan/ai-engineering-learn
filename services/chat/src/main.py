import json
import uuid
from collections.abc import Iterator
from typing import Literal

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel

from .ai_client import stream_complete
from .extract import EXTRACT_DEFAULT_MODE, ExtractionError, Mode, extract

app = FastAPI(title="chat-service")

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

# Proxy model_name (from services/proxy/config.yaml) — fixed server-side, not
# client-selectable.
MODEL = "primary"


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    # Full conversation history; the server is stateless, so the client resends it
    # each turn. session_id ties the turns together into one LangFuse session —
    # reuse the X-Session-Id returned on the first turn.
    messages: list[Message]
    session_id: str | None = None


class ExtractRequest(BaseModel):
    # Raw text to pull structure out of, plus the JSON Schema the result must
    # validate against. mode picks the enforcement mechanism (native json_schema
    # vs. prompt-only JSON); unset falls back to EXTRACT_DEFAULT_MODE.
    text: str
    json_schema: dict[str, object]
    mode: Mode | None = None


class ExtractError(BaseModel):
    # The clean, typed error body — returned instead of malformed JSON or a 500.
    error: str
    kind: Literal["parse", "schema", "bad_schema", "upstream"]
    attempts: int
    detail: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    trace_id = uuid.uuid4().hex
    session_id = request.session_id or uuid.uuid4().hex
    messages = [m.model_dump() for m in request.messages]

    # SSE: each token delta is one `data:` event (JSON-wrapped so newlines and
    # special chars survive), terminated by a `[DONE]` sentinel. stream_complete()
    # is a blocking sync generator; Starlette iterates it in a threadpool, so the
    # event loop is never stalled. TTFT + total latency are logged to the trace
    # inside stream_complete once the stream ends.
    def events() -> Iterator[str]:
        for delta in stream_complete(
            messages, trace_id=trace_id, session_id=session_id
        ):
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Trace-Id": trace_id,
            "X-Session-Id": session_id,
        },
    )


@app.post("/extract")
def extract_endpoint(request: ExtractRequest) -> JSONResponse:
    # Sync def (not async): extract() is a blocking sequence of proxy calls, so
    # Starlette runs it in a threadpool and the event loop is never stalled — same
    # reasoning as /chat's blocking generator. Not streamed: the consumer is a
    # machine that must validate the WHOLE payload against the schema before using
    # any of it, so a half-arrived JSON object is unparseable — nothing to stream to.
    trace_id = uuid.uuid4().hex
    headers = {"X-Trace-Id": trace_id}

    # A malformed schema is a client error, not a model-retry case — reject it up
    # front so we never burn attempts trying to satisfy an unsatisfiable schema.
    try:
        Draft202012Validator.check_schema(request.json_schema)
    except SchemaError as exc:
        body = ExtractError(
            error="extraction_failed", kind="bad_schema", attempts=0, detail=exc.message
        )
        return JSONResponse(body.model_dump(), status_code=422, headers=headers)

    mode: Mode = request.mode or EXTRACT_DEFAULT_MODE

    try:
        result = extract(
            text=request.text,
            json_schema=request.json_schema,
            mode=mode,
            trace_id=trace_id,
        )
        return JSONResponse(result, headers=headers)
    except ExtractionError as exc:
        # Retries exhausted: return the typed error, never malformed output.
        body = ExtractError(
            error="extraction_failed",
            kind=exc.kind,
            attempts=exc.attempts,
            detail=exc.detail,
        )
        return JSONResponse(body.model_dump(), status_code=422, headers=headers)
    except Exception as exc:
        # Proxy/provider failure (429, timeout, outage). Don't leak a 500 stack
        # trace — return a typed upstream error the caller can branch on.
        log.warning("extract_upstream_error", trace_id=trace_id, error=str(exc))
        body = ExtractError(
            error="upstream_error", kind="upstream", attempts=0, detail=str(exc)
        )
        return JSONResponse(body.model_dump(), status_code=502, headers=headers)
