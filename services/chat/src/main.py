import json
import uuid
from collections.abc import Iterator
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .ai_client import stream_complete

app = FastAPI(title="chat-service")

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
