# chat-ui

A minimal Claude/ChatGPT-style chat frontend (Nuxt 4) for the stateless FastAPI
`/chat` service in `services/chat/`.

## How it works

- The backend `/chat` endpoint is **stateless**: it takes the full conversation
  `{"messages": [{"role","content"}...], "session_id": null}` each turn and streams
  the reply as Server-Sent Events (`data: {"delta": "..."}` → `data: [DONE]`). It
  keeps no server-side memory and has no CORS.
- **Memory** lives in the browser: `app/composables/useChat.ts` holds the message
  list and resends the whole history every turn. The first response returns an
  `X-Session-Id`; we reuse it on later turns so the backend groups the
  conversation into one LangFuse session. "New chat" clears both.
- **CORS** is avoided with a Nitro proxy (`server/api/chat.post.ts`): the browser
  calls the Nuxt app's own `/api/chat`, which forwards to the backend, streams the
  SSE straight back, and relays the session/trace headers. The Python service is
  untouched.

## Run

1. Start the backend (from the repo root), with the LiteLLM proxy already up:

   ```sh
   set -a; source .env.proxy; set +a
   uv run uvicorn services.chat.src.main:app --reload   # http://localhost:8000
   ```

2. Start this UI:

   ```sh
   cd services/chat-ui
   pnpm install
   pnpm dev            # http://localhost:3000
   ```

If the backend runs somewhere other than `http://localhost:8000`, set
`CHAT_API_URL` before `pnpm dev`.

## Scripts

- `pnpm dev` — dev server with HMR
- `pnpm build` / `pnpm preview` — production build + preview
- `pnpm typecheck` — Vue/TS type check
