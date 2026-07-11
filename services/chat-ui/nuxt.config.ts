// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },
  runtimeConfig: {
    // Server-only: where the FastAPI chat service listens. The Nitro proxy
    // (server/api/chat.post.ts) forwards to `${chatApiUrl}/chat`, so the browser
    // never talks to :8000 directly and CORS is a non-issue.
    chatApiUrl: process.env.CHAT_API_URL || 'http://localhost:8000',
  },
})
