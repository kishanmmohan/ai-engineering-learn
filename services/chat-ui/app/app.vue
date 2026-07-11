<script setup lang="ts">
const { messages, isStreaming, error, send, reset } = useChat()
const scrollEl = ref<HTMLElement | null>(null)

useHead({
  title: 'Chat',
  meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
})

// Keep the view pinned to the latest tokens as they stream in.
watch(
  () => messages.value.map((m) => m.content).join(''),
  () => nextTick(() => {
    const el = scrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  }),
)
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>Chat</h1>
      <button class="new-chat" :disabled="isStreaming || !messages.length" @click="reset">
        New chat
      </button>
    </header>

    <main ref="scrollEl" class="messages">
      <div v-if="!messages.length" class="empty">
        <p class="empty-title">How can I help?</p>
        <p class="empty-sub">Ask anything — replies stream in live.</p>
      </div>

      <div class="thread">
        <ChatMessage
          v-for="(m, i) in messages"
          :key="i"
          :message="m"
          :streaming="isStreaming && i === messages.length - 1 && m.role === 'assistant'"
        />
        <p v-if="error" class="error">{{ error }}</p>
      </div>
    </main>

    <footer class="footer">
      <ChatInput :disabled="isStreaming" @send="send" />
      <p class="disclaimer">Stateless backend — conversation context is sent from your browser.</p>
    </footer>
  </div>
</template>

<style>
:root {
  --bg: #ffffff;
  --fg: #1f2328;
  --muted: #8b949e;
  --accent: #d97757;
  --bubble-assistant: #f4f4f2;
  --code-bg: #ececec;
  --border: #e3e3e0;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1c1c1a;
    --fg: #e9e9e4;
    --muted: #8b949e;
    --accent: #d97757;
    --bubble-assistant: #2a2a27;
    --code-bg: #111110;
    --border: #3a3a36;
  }
}
* {
  box-sizing: border-box;
}
html,
body,
#__nuxt {
  height: 100%;
  margin: 0;
}
body {
  background: var(--bg);
  color: var(--fg);
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
</style>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  max-width: 48rem;
  margin: 0 auto;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1rem;
  border-bottom: 1px solid var(--border);
}
.header h1 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}
.new-chat {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--fg);
  padding: 0.4rem 0.8rem;
  border-radius: 0.6rem;
  font-size: 0.85rem;
  cursor: pointer;
}
.new-chat:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}
.thread {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--muted);
}
.empty-title {
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--fg);
  margin: 0 0 0.25rem;
}
.empty-sub {
  margin: 0;
}
.error {
  color: #e5534b;
  font-size: 0.9rem;
}
.footer {
  padding: 0.5rem 1rem 1rem;
}
.disclaimer {
  margin: 0.5rem 0 0;
  text-align: center;
  font-size: 0.72rem;
  color: var(--muted);
}
</style>
