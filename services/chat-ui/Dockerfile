# syntax=docker/dockerfile:1
# Nuxt chat UI. Build context is this directory (services/chat-ui).

# ---- build stage: install deps + produce the Nitro node-server output ----
FROM node:26-bookworm-slim AS build
WORKDIR /app
# Node 26 slim no longer bundles corepack; install the pinned pnpm directly.
RUN npm install -g pnpm@11.10.0

# Deps first (cached until the lockfile changes). pnpm-workspace.yaml carries the
# allowBuilds entries that let esbuild build its native binary for the Vite build.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# ---- runtime stage: just Node + the self-contained .output ----
FROM node:26-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000
# NUXT_CHAT_API_URL (set in compose) overrides runtimeConfig.chatApiUrl at startup.

COPY --from=build /app/.output ./.output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
