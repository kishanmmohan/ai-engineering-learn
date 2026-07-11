export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

// The backend `/chat` is stateless: it takes the full `messages` history each turn
// (no server-side memory) and returns an `X-Session-Id` that groups the turns into
// one LangFuse session. We resend the history + reuse that session id every turn.
export function useChat() {
  const messages = useState<ChatMessage[]>('chat-messages', () => [])
  const sessionId = useState<string | null>('chat-session', () => null)
  const isStreaming = useState<boolean>('chat-streaming', () => false)
  const error = useState<string | null>('chat-error', () => null)

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isStreaming.value) return

    error.value = null
    messages.value.push({ role: 'user', content: trimmed })
    // Snapshot the history to send (ends with the new user turn) BEFORE adding the
    // empty assistant placeholder we fill as deltas arrive.
    const payload = messages.value.map((m) => ({ role: m.role, content: m.content }))
    messages.value.push({ role: 'assistant', content: '' })
    const assistantIndex = messages.value.length - 1
    isStreaming.value = true

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ messages: payload, session_id: sessionId.value }),
      })
      if (!res.ok || !res.body) {
        throw new Error(`Request failed (${res.status})`)
      }
      // Reuse this conversation's session id on subsequent turns.
      const sid = res.headers.get('x-session-id')
      if (sid) sessionId.value = sid

      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += value

        // SSE frames are separated by a blank line. Keep the trailing partial
        // frame in the buffer until its terminator arrives.
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          const line = frame.trim()
          if (!line.startsWith('data:')) continue
          const data = line.slice(5).trim()
          if (data === '[DONE]') return
          try {
            const { delta } = JSON.parse(data) as { delta?: string }
            if (delta) messages.value[assistantIndex]!.content += delta
          } catch {
            // Ignore malformed frames (e.g. keep-alive comments).
          }
        }
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Something went wrong.'
      // Drop the empty assistant bubble if nothing streamed in.
      if (!messages.value[assistantIndex]?.content) {
        messages.value.splice(assistantIndex, 1)
      }
    } finally {
      isStreaming.value = false
    }
  }

  function reset() {
    if (isStreaming.value) return
    messages.value = []
    sessionId.value = null
    error.value = null
  }

  return { messages, sessionId, isStreaming, error, send, reset }
}
