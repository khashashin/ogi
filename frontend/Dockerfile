FROM node:20-alpine AS build

WORKDIR /app

RUN npm install -g pnpm

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

# Build args for Supabase config (baked into the static build)
ARG VITE_SUPABASE_URL=${OGI_SUPABASE_URL:-}
ARG VITE_SUPABASE_ANON_KEY=${OGI_SUPABASE_ANON_KEY:-}

RUN pnpm build

# --- Production image ---
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY env.js.template /usr/share/nginx/html/env.js.template
COPY docker-entrypoint.d/40-env.sh /docker-entrypoint.d/40-env.sh

RUN chmod +x /docker-entrypoint.d/40-env.sh

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
