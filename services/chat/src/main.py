from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .ai_client import complete

app = FastAPI(title="chat-service")


class ChatRequest(BaseModel):
    prompt: str
    model: str = "primary"  # a model_name from services/proxy/config.yaml


class ChatResponse(BaseModel):
    reply: str
    model: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    # complete() wraps the blocking litellm.completion call, so offload it to a
    # threadpool rather than stalling the event loop.
    reply = await run_in_threadpool(complete, request.prompt, request.model)
    return ChatResponse(reply=reply, model=request.model)
