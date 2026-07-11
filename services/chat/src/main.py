import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .ai_client import stream_complete

app = FastAPI(title="chat-service")

# Proxy model_name (from services/proxy/config.yaml) — fixed server-side, not
# client-selectable.
MODEL = "primary"


class ChatRequest(BaseModel):
    prompt: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    # SSE: each token delta is one `data:` event (JSON-wrapped so newlines and
    # special chars survive), terminated by a `[DONE]` sentinel. stream_complete()
    # is a blocking sync generator; Starlette iterates it in a threadpool, so the
    # event loop is never stalled.
    def events() -> Iterator[str]:
        for delta in stream_complete(request.prompt, MODEL):
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
