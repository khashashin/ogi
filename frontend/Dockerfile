FROM node:24-alpine AS build

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
# Install the pnpm version package.json pins (packageManager), the one CI and the lockfile use,
# rather than whatever is newest on npm.
RUN npm install -g "pnpm@$(node -p "require('./package.json').packageManager.split('@')[1].split('+')[0]")" \
    && pnpm --version
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
