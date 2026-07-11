<script setup lang="ts">
const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')
const textarea = ref<HTMLTextAreaElement | null>(null)

function autoGrow() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`
}

function submit() {
  const value = text.value.trim()
  if (!value || props.disabled) return
  emit('send', value)
  text.value = ''
  nextTick(autoGrow)
}

function onKeydown(e: KeyboardEvent) {
  // Enter sends; Shift+Enter inserts a newline.
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <form class="input-bar" @submit.prevent="submit">
    <textarea
      ref="textarea"
      v-model="text"
      rows="1"
      placeholder="Message… (Enter to send, Shift+Enter for newline)"
      :disabled="disabled"
      @input="autoGrow"
      @keydown="onKeydown"
    />
    <button type="submit" :disabled="disabled || !text.trim()" aria-label="Send">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 2 11 13" />
        <path d="M22 2 15 22l-4-9-9-4Z" />
      </svg>
    </button>
  </form>
</template>

<style scoped>
.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  padding: 0.6rem 0.75rem;
  background: var(--bubble-assistant);
  border: 1px solid var(--border);
  border-radius: 1rem;
}
textarea {
  flex: 1;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--fg);
  font: inherit;
  line-height: 1.5;
  max-height: 200px;
}
textarea::placeholder {
  color: var(--muted);
}
button {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  flex-shrink: 0;
  border: none;
  border-radius: 0.75rem;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  transition: opacity 0.15s;
}
button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
