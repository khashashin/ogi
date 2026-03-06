# OGI Frontend

React + TypeScript frontend for OpenGraph Intel.

## Requirements

- Node.js 20+
- pnpm
- Backend API running at `http://localhost:8000` (default)

## Setup

```bash
cd frontend
pnpm install
pnpm dev
```

App runs at `http://localhost:5173`.

## Scripts

```bash
pnpm dev      # Start Vite dev server
pnpm build    # Type-check, production build, generate sitemap.xml + robots.txt
pnpm test     # Run Vitest suite
pnpm lint     # Run ESLint
pnpm preview  # Preview production build
```

### SEO Sitemap

- `pnpm build` now auto-generates:
  - `dist/sitemap.xml`
  - `dist/robots.txt`
- Canonical base URL is read from:
  - `OGI_SITE_URL` (preferred), or
  - `SITE_URL`, or defaults to `https://ogi.khas.app`

Example:

```bash
OGI_SITE_URL=https://yourdomain.com pnpm build
```

## Environment and Runtime Config

The frontend can run with or without Supabase auth.

- If Supabase env values are present, auth/session features are enabled.
- If absent, frontend still works in local mode with backend-managed data access.

Supported keys:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_SUPABASE_REDIRECT_URL`

Two configuration modes are supported:

1. Build-time env via Vite (`import.meta.env`).
2. Runtime env via `public/env.js` (`window.__OGI_RUNTIME_CONFIG__`).

Template for runtime injection:

- `env.js.template`

## Key Features

- Sigma.js-based graph canvas and interactions
- Table view and search/filter workflows
- Transform panel with async job updates (WebSocket)
- Transform Hub marketplace integration
- Import/export UI (JSON/CSV/GraphML + cloud signed URL flows)
- Supabase auth UI + protected routes + sharing dialogs

## Project Structure

- `src/components` - UI components
- `src/components/marketplace` - Transform Hub UI
- `src/stores` - Zustand state stores
- `src/hooks` - reusable hooks (realtime, websocket, shortcuts)
- `src/api/client.ts` - typed API client
- `src/types` - shared frontend type models
- `src/lib` - env/supabase utilities

## Troubleshooting

- Blank auth behavior: verify Supabase keys in runtime/build env.
- API errors: ensure backend is running and reachable at `/api/v1`.
- WebSocket job updates missing: verify Redis + worker + backend are up in docker/local stack.
