import type { ChatMessage } from '~/composables/useChat'

interface ChatBody {
  messages?: ChatMessage[]
  session_id?: string | null
}

// Nitro proxy: the browser POSTs here, we forward to the stateless FastAPI
// `/chat` service and stream its Server-Sent Events straight back. This keeps the
// browser on the Nuxt origin (no CORS) and leaves the Python backend untouched.
// We also relay the X-Session-Id / X-Trace-Id headers so the client can group a
// conversation's turns into one LangFuse session on later requests.
export default defineEventHandler(async (event) => {
  const { chatApiUrl } = useRuntimeConfig()
  const body = await readBody<ChatBody>(event)

  if (!Array.isArray(body?.messages) || body.messages.length === 0) {
    throw createError({ statusCode: 400, statusMessage: 'Missing "messages"' })
  }

  const upstream = await fetch(`${chatApiUrl}/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      messages: body.messages,
      session_id: body.session_id ?? null,
    }),
  })

  if (!upstream.ok || !upstream.body) {
    throw createError({
      statusCode: upstream.status || 502,
      statusMessage: `Chat service error (${upstream.status})`,
    })
  }

  // Pass the SSE stream through unchanged, relaying the session/trace headers.
  setResponseHeaders(event, {
    'content-type': 'text/event-stream',
    'cache-control': 'no-cache',
    'x-accel-buffering': 'no',
    'x-session-id': upstream.headers.get('x-session-id') ?? '',
    'x-trace-id': upstream.headers.get('x-trace-id') ?? '',
  })
  return upstream.body
})
