# OGI — OpenGraph Intel

An open source visual link analysis and OSINT framework. Think Maltego, but free and community-driven.

![OpenGraph Intel Screenshot](docs/images/image.png)

> **Heads up:** This project is actively evolving. It has solid core capabilities and test coverage, and we continue to improve documentation, hardening, and feature depth with each release. Contributions, bug reports, and feedback are very welcome.

## What it does

- **Visual graph investigation** — drag-and-drop entities, explore connections
- **20+ transforms** — DNS, WHOIS, SSL certs, geolocation, web/email/hash/social enrichment, and more
- **Transform Hub** — browse and install community transforms from the [registry](https://github.com/opengraphintel/ogi-transforms)
- **Import/Export** — JSON, CSV, GraphML, and Maltego MTGX import
- **Graph analysis** — centrality, community detection, shortest paths
- **Collaboration** — projects, sharing, and real-time sync
- **Async transform jobs** — Redis/RQ queue + WebSocket updates
- **Runs anywhere** — local SQLite mode (zero config) or PostgreSQL + Supabase for team/cloud setups

## Quick Start

### Backend

Tested with Python 3.14+.

```bash
cd backend
uv sync
uv run uvicorn ogi.main:app --reload
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:5173. That's it.

### CLI (`ogi`)

Two supported ways to run the CLI:

1. Recommended (no activation required):

```bash
cd backend
uv sync
uv run ogi --help
```

2. Activated virtualenv (plain `ogi` command):

```bash
cd backend
uv venv
# PowerShell:
.\.venv\Scripts\Activate.ps1
uv pip install -e .
ogi --help
```

### Docker

```bash
docker compose up
```

For production deployments, use the prebuilt GHCR images:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Set `OGI_IMAGE_TAG` in `.env` to pin a specific release image tag (for example `v0.1.0`). By default, `latest` is used.

### Boot-Time Plugin Dependencies

If you use prebuilt images and a plugin needs extra Python libraries, add a requirements file mounted into the container:

```bash
plugins/requirements.txt
```

On container start, the backend/worker image will install that file automatically (hash-cached per container lifecycle).

Optional env vars:

- `OGI_BOOT_REQUIREMENTS_ENABLE=true|false` (default: `true`)
- `OGI_BOOT_REQUIREMENTS_FILE=/app/plugins/requirements.txt`
- `OGI_BOOT_REQUIREMENTS_STRICT=true|false` (default: `false`; fail startup if file missing)

## Tech Stack

| Layer            | Tech                                                            |
| ---------------- | --------------------------------------------------------------- |
| Backend          | Python, FastAPI, SQLModel, PostgreSQL/SQLite, Redis/RQ          |
| Frontend         | React, TypeScript, Sigma.js (graphology), Zustand, Tailwind CSS |
| Auth & Realtime  | Supabase + WebSocket events (optional auth in local mode)       |
| Package managers | uv (backend), pnpm (frontend)                                   |

## Transform Hub

OpenGraph Intel has a built-in transform marketplace. Browse, install, and manage transforms from the [community registry](https://github.com/opengraphintel/ogi-transforms).

```bash
cd backend
uv run ogi transform search dns
uv run ogi transform install shodan-host-lookup
```

Want to build your own? See the [contributing guide](https://github.com/opengraphintel/ogi-transforms/blob/main/CONTRIBUTING.md).

## Project Status

This is an early-stage project. Here's what exists:

- Graph engine, entity registry, undo/redo
- 20+ transforms across DNS, email, web, IP, cert, social, hash, and org categories
- Full REST API with project/member management
- Plugin system + Transform Hub integration
- CLI tool (`ogi transform ...`)
- Docker deployment (backend/frontend/db/worker/redis)
- Auth and real-time collaboration (Supabase-backed)
- Cloud export/import signed URL flows

What's missing or incomplete:

- Test coverage is improving but still uneven across features
- No formal security audit
- Limited error handling in some transforms

## Contributing

PRs welcome. If you find a bug or have an idea, open an issue.

For new transforms, contribute to [ogi-transforms](https://github.com/opengraphintel/ogi-transforms).

## License

[AGPLv3](LICENSE)
