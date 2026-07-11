<script setup lang="ts">
import { renderMarkdown } from '~/utils/markdown'
import type { ChatMessage } from '~/composables/useChat'

const props = defineProps<{
  message: ChatMessage
  streaming?: boolean
}>()

const isUser = computed(() => props.message.role === 'user')
const rendered = computed(() =>
  isUser.value ? '' : renderMarkdown(props.message.content),
)
</script>

<template>
  <div class="row" :class="isUser ? 'row-user' : 'row-assistant'">
    <div class="bubble" :class="isUser ? 'bubble-user' : 'bubble-assistant'">
      <p v-if="isUser" class="user-text">{{ message.content }}</p>
      <div v-else class="markdown" v-html="rendered" />
      <span v-if="streaming" class="cursor" aria-hidden="true" />
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  width: 100%;
}
.row-user {
  justify-content: flex-end;
}
.row-assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 80%;
  padding: 0.75rem 1rem;
  border-radius: 1rem;
  line-height: 1.6;
  font-size: 0.95rem;
  overflow-wrap: anywhere;
}
.bubble-user {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 0.25rem;
}
.bubble-assistant {
  background: var(--bubble-assistant);
  color: var(--fg);
  border-bottom-left-radius: 0.25rem;
}
.user-text {
  margin: 0;
  white-space: pre-wrap;
}
.cursor {
  display: inline-block;
  width: 0.5rem;
  height: 1rem;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: currentColor;
  animation: blink 1s steps(2, start) infinite;
}
@keyframes blink {
  to {
    visibility: hidden;
  }
}

/* Markdown content */
.markdown :deep(p) {
  margin: 0 0 0.75rem;
}
.markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown :deep(pre) {
  background: var(--code-bg);
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 0.5rem 0;
}
.markdown :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85em;
}
.markdown :deep(:not(pre) > code) {
  background: var(--code-bg);
  padding: 0.1rem 0.35rem;
  border-radius: 0.35rem;
}
.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 0.5rem 0;
  padding-left: 1.4rem;
}
.markdown :deep(a) {
  color: var(--accent);
}
.markdown :deep(pre code) {
  background: none;
  padding: 0;
}
</style>
