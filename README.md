<div align="center">

<img src="docs/images/mascot.png" alt="OGI Mascot" width="200" />

# OpenGraph Intel (OGI)

**Open-source visual link analysis and OSINT framework.**
**Free, self-hostable, and community-driven.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/khashashin/ogi/actions/workflows/ci.yml/badge.svg)](https://github.com/khashashin/ogi/actions/workflows/ci.yml)
[![Docker](https://github.com/khashashin/ogi/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/khashashin/ogi/actions/workflows/docker-publish.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
![Version](https://img.shields.io/github/v/release/khashashin/ogi?display_name=tag&color=green)

[Features](#features) &bull; [Screenshots](#screenshots) &bull; [Quick Start](#quick-start) &bull; [Docker](#docker) &bull; [Transform Hub](#transform-hub) &bull; [Architecture](#architecture) &bull; [Contributing](#contributing)

</div>

---

> **Heads up:** This project is actively evolving. It has solid core capabilities and test coverage, and we continue to improve documentation, hardening, and feature depth with each release. Contributions, bug reports, and feedback are very welcome.

## Features

- **Visual graph investigation** — drag-and-drop entities, explore connections interactively, 14 layout presets
- **25+ built-in transforms** — DNS, WHOIS, SSL certificates, geolocation, web, email, hash, people, and location enrichment
- **Transform Hub** — browse and install community transforms from the [registry](https://github.com/opengraphintel/ogi-transforms)
- **AI Investigator** — prompt-driven agentic investigations that plan transform runs, stream progress live, and summarize findings with auditability
- **Map view** — geolocated entities on an interactive map, with clustering and routes
- **Timeline and events** — filter the graph by time window and review every transform run in the project's activity log
- **Import / Export** — import JSON, CSV, GraphML, and MTGX; export JSON, CSV, GraphML, and PNG images of the graph
- **Graph analysis** — degree, betweenness, and closeness centrality, PageRank, and connected components
- **Light and dark themes** — pick dark, light, or follow your system setting
- **Real-time collaboration** — projects, sharing, and live sync via Supabase Realtime
- **Async transform jobs** — Redis/RQ queue with WebSocket progress updates
- **Plugin system** — directory-based plugin discovery with YAML manifests
- **CLI tool** — search, install, and manage transforms from the terminal
- **Runs anywhere** — local SQLite mode (zero config) or PostgreSQL + Supabase for team/cloud setups
- **Docker ready** — one-command deployment with `docker compose up`

## Screenshots

The screenshots follow your GitHub theme. They show an investigation of the public `debian.org` infrastructure, built with the built-in transforms.

<table>
  <tr>
    <th width="50%">Graph investigation</th>
    <th width="50%">Map view</th>
  </tr>
  <tr>
    <td>
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/images/graph-dark.png" />
        <img src="docs/images/graph-light.png" alt="Graph of debian.org with its IP addresses, mail and name servers, subdomains, and mirrors, and the output of a DNS transform" />
      </picture>
    </td>
    <td>
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/images/map-dark.png" />
        <img src="docs/images/map-light.png" alt="World map with the geolocated Debian mirror servers" />
      </picture>
    </td>
  </tr>
  <tr>
    <th width="50%">Transform Hub</th>
    <th width="50%">Graph analysis</th>
  </tr>
  <tr>
    <td>
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/images/hub-dark.png" />
        <img src="docs/images/hub-light.png" alt="Transform Hub catalog with official and community transforms, trust tiers, and permissions" />
      </picture>
    </td>
    <td>
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/images/analysis-dark.png" />
        <img src="docs/images/analysis-light.png" alt="PageRank results ranking the most important entities in the graph" />
      </picture>
    </td>
  </tr>
</table>

### Light and dark themes

The toggle in the toolbar switches between dark, light, and your system setting.

<table>
  <tr>
    <th width="50%">Dark</th>
    <th width="50%">Light</th>
  </tr>
  <tr>
    <td><img src="docs/images/graph-dark.png" alt="The graph workspace in the dark theme" /></td>
    <td><img src="docs/images/graph-light.png" alt="The graph workspace in the light theme" /></td>
  </tr>
</table>

## Quick Start

### Prerequisites

| Tool                             | Version                    |
| -------------------------------- | -------------------------- |
| [Python](https://www.python.org) | 3.14+                      |
| [uv](https://docs.astral.sh/uv/) | latest                     |
| [Node.js](https://nodejs.org)    | 24 LTS (22.22+ also works) |
| [pnpm](https://pnpm.io)          | 10.x                       |

### Backend

```bash
cd backend
uv sync
uv run uvicorn ogi.main:app --reload
```

The API will be available at `http://localhost:8000`.

For local transform execution, Redis and the transform worker must also be running. Redis alone is not enough.

Start Redis:

```bash
docker run -d --name ogi-redis -p 6379:6379 redis:7-alpine
```

Start the transform worker in a second terminal:

```bash
cd backend
uv run python -m ogi.worker.run_worker
```

If you see `Job queue not available` or `Redis not available`, verify that:

- `OGI_REDIS_URL` points to `redis://localhost:6379/0` for local host-based runs
- the backend was restarted after Redis came up
- the separate worker process is running
- you are not using the Docker-only hostname `redis` outside Docker Compose

If you run the backend against PostgreSQL (`OGI_USE_SQLITE=false`), startup will automatically apply Alembic migrations before serving requests. Docker deployments do the same in the backend container entrypoint.

Without `OGI_SUPABASE_URL` and `OGI_SUPABASE_ANON_KEY`, OGI runs without sign-in: every request acts as one local user with admin rights, including installing plugins. That suits a single-user machine. For an instance other people can reach, configure Supabase auth.

AI Investigator runs are processed by another separate worker:

```bash
cd backend
uv run python -m ogi.agent.run_worker
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:5173. That's it.

### AI Investigator

AI Investigator is an optional provider-backed workflow that can plan transform sequences, request approvals, and summarize investigation progress inside the workspace.

- Open the `AI Investigator` tab inside a project
- Configure a provider and model in the investigator settings dialog
- Store provider API keys in `API Keys`
- Run the separate `agent-worker` process alongside the backend

The current implementation supports per-user provider configuration and a dedicated worker that executes investigation steps independently from the main API server.

### CLI

Two supported ways to run the CLI:

**Recommended** (no activation required):

```bash
cd backend
uv sync
uv run ogi --help
```

**Activated virtualenv** (plain `ogi` command):

```bash
cd backend
uv venv
# PowerShell:
.\.venv\Scripts\Activate.ps1
uv pip install -e .
ogi --help
```

## Docker

### Development

```bash
cp .env.example .env
docker compose up
```

Open http://localhost:3000 (set `OGI_FRONTEND_PORT` to change the port).

### Production

Use the prebuilt GHCR images.

Important: [docker-compose.prod.yml](https://github.com/khashashin/ogi/blob/main/docker-compose.prod.yml) requires an external PostgreSQL database. It does not include a `db` service.

If you want the all-in-one local Docker stack with built-in Postgres and Redis, use:

```bash
docker compose up -d
```

Use the production compose file only when you already have a reachable PostgreSQL instance and have set `OGI_DATABASE_URL` accordingly:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Set `OGI_IMAGE_TAG` in `.env` to pin a specific release image tag (e.g. `v0.9.1`). Defaults to `latest`, the newest release. The `edge` tag follows the `main` branch.

The production compose file reads `.env` into the backend and both workers, so create it from `.env.example` first. Set at least `OGI_DATABASE_URL`, `OGI_API_KEY_ENCRYPTION_KEY`, and, with sign-in enabled, `OGI_ADMIN_EMAILS`. Values written under a service's `environment:` key take precedence over `.env`, so the in-stack Redis URL and the migration settings stay as the compose file defines them.

### Hetzner Cloud

[![Get Hetzner Cloud credits](https://img.shields.io/badge/Get_Hetzner_Cloud_credits-D50C2D?style=for-the-badge&logo=hetzner&logoColor=white)](https://hetzner.cloud/?ref=LspEGc99USBa)
[![Deploy Docker CE on Hetzner](https://img.shields.io/badge/Deploy_Docker_CE_on_Hetzner-D50C2D?style=for-the-badge&logo=hetzner&logoColor=white)](https://console.hetzner.com/deploy/docker-ce)

New Hetzner users can use the first link to sign up with Hetzner Cloud credits. It is a referral link, so the OGI maintainer may also receive Hetzner Cloud credits if the referral qualifies. After creating a server, use the Docker deployment commands above to run OGI.

### Configurable transform caps

OGI ships with sensible per-transform max values for things like `max_results`, `max_links`, `max_urls`, and `max_content_chars`, but those caps are now centrally overridable so cloud deployments can enforce them without hardcoding local limits.

Use `OGI_TRANSFORM_SETTING_MAX_OVERRIDES` in `.env`:

```env
OGI_TRANSFORM_SETTING_MAX_OVERRIDES=max_results=50,max_urls=25,max_links=40,max_content_chars=20000
```

To remove specific caps in a local-first deployment:

```env
OGI_TRANSFORM_SETTING_MAX_OVERRIDES=max_results=none,max_urls=none,max_links=none,max_content_chars=none
```

The override is keyed by transform setting name and applies to built-in transforms and community plugins that use OGI's shared transform base/runtime.

### Hosted cloud instance and Supporter plan

The hosted cloud version at [ogi.khas.app](https://ogi.khas.app) was initially built so users could try OGI quickly before deciding whether to self-host it. It has since become the most popular way to use the project, with over 350 active cloud users.

That usage also increased the infrastructure costs for this side project. The repository therefore includes a cloud-only Supporter subscription and transformer-run cooldown system. On the public cloud instance, free users may be limited by a timeout between transformer runs, while Supporter users can subscribe for a symbolic USD 3/month to help cover Supabase and VPS costs.

Supporter subscriptions can be cancelled from the profile billing controls or the Stripe billing portal. Cancellation stops future billing, but paid subscription periods are not refunded or prorated.

This billing code is intentionally guarded by configuration: it only has an effect when `OGI_DEPLOYMENT_MODE=cloud` and `OGI_CLOUD_BILLING_ENABLED=true`. Self-hosted deployments should leave billing disabled and should not see any billing or paywall behavior.

### Telemetry

OGI includes installation-level product telemetry intended to help us understand real-world usage, especially across self-hosted deployments.

- `OGI_TELEMETRY_ENABLED=true` enables telemetry collection
- `OGI_TELEMETRY_LEVEL=full` is the default collection level
- set `OGI_TELEMETRY_ENABLED=false` to disable telemetry entirely
- set `OGI_TELEMETRY_LEVEL=basic` to reduce what is sent

`basic` sends:

- OGI version
- a daily active installation ping

`full` additionally sends:

- instance created date
- aggregate counts for projects, entities, edges, transform runs, investigator runs, and active users for the period
- installed transforms with their versions

Telemetry is designed to avoid sending graph contents, entity values, API keys, prompts, or other investigation data. The current policy details are also published in the [Privacy Policy](https://ogi.khas.app/privacy#telemetry).

<details>
<summary><strong>Development Compose Services</strong></summary>

| Service        | Description                | Host port                  |
| -------------- | -------------------------- | -------------------------- |
| `backend`      | FastAPI application server | 8000 (`OGI_PORT`)          |
| `worker`       | RQ async job worker        | -                          |
| `agent-worker` | AI Investigator worker     | -                          |
| `frontend`     | React app served via nginx | 3000 (`OGI_FRONTEND_PORT`) |
| `db`           | PostgreSQL 16              | 5432                       |
| `redis`        | Redis 7 (job queue)        | 6379                       |

</details>

<details>
<summary><strong>Production Compose Services</strong></summary>

| Service        | Description                | Port                                      |
| -------------- | -------------------------- | ----------------------------------------- |
| `backend`      | FastAPI application server | internal only                             |
| `worker`       | RQ async job worker        | -                                         |
| `agent-worker` | AI Investigator worker     | -                                         |
| `frontend`     | React app served via nginx | container port 80, for your reverse proxy |
| `redis`        | Redis 7 (job queue)        | internal only                             |

`docker-compose.prod.yml` expects an external PostgreSQL database via `OGI_DATABASE_URL`. The frontend's nginx proxies `/api` to the backend, so only the frontend needs to be reachable.

</details>

---

<details>
<summary><strong>Boot-time plugin dependencies</strong></summary>

If you use prebuilt images and a plugin needs extra Python libraries, OGI installs plugin dependencies at container startup from:

1. `plugins/requirements.txt` (preferred), or
2. auto-generated requirements derived from `plugins/ogi-lock.json` when `requirements.txt` is missing.

**Environment variables:**

| Variable                          | Default                         | Description                               |
| --------------------------------- | ------------------------------- | ----------------------------------------- |
| `OGI_BOOT_REQUIREMENTS_ENABLE`    | `true`                          | Enable/disable boot-time install          |
| `OGI_BOOT_REQUIREMENTS_FILE`      | `/app/plugins/requirements.txt` | Path to requirements file                 |
| `OGI_BOOT_LOCK_FILE`              | `/app/plugins/ogi-lock.json`    | Path to lock file                         |
| `OGI_BOOT_REQUIREMENTS_STRICT`    | `false`                         | Fail startup if requirements missing      |
| `OGI_BOOT_REQUIREMENTS_CACHE_DIR` | `/tmp/ogi-boot`                 | Temp/cache dir for generated requirements |

</details>

---

## Transform Hub

OpenGraph Intel has a built-in transform marketplace. Browse, install, and manage transforms from the [community registry](https://github.com/opengraphintel/ogi-transforms).

> **Security note:** Plugins that require API keys should be treated as privileged code. If a plugin can access your secrets and make outbound network requests, it can misuse or exfiltrate those secrets. Review trust tier, permissions, and required services before installing or running third-party plugins.

```bash
# Search for transforms
uv run ogi transform search dns

# Install a transform
uv run ogi transform install ip-to-shodan-host
```

### Built-in Transform Categories

| Category     | Transforms                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------------- |
| DNS          | A/AAAA, MX, and NS records, reverse DNS, WHOIS                                                     |
| IP & ASN     | IP geolocation, ASN lookup                                                                         |
| Certificates | Certificate transparency subdomains (crt.sh), the TLS certificate a domain serves                  |
| Email        | Email to domain, common addresses for a domain (after an MX check)                                 |
| Web          | HTTP headers, outbound links, URLs from robots.txt, page content (Playwright), IOCs from documents |
| People       | Likely usernames for a person, username search across platforms, people on a website (OpenAI)     |
| Hash         | VirusTotal hash lookup (API key)                                                                   |
| Location     | Geocoding, reverse geocoding, timezone, sun times, weather snapshot, nearby ASNs                   |

### Supported Entity Types

`Person` &bull; `Username` &bull; `Vulnerability` &bull; `Domain` &bull; `IPAddress` &bull; `EmailAddress` &bull; `PhoneNumber` &bull; `Organization` &bull; `URL` &bull; `SocialMedia` &bull; `Hash` &bull; `Document` &bull; `Location` &bull; `ASNumber` &bull; `Network` &bull; `MXRecord` &bull; `NSRecord` &bull; `Nameserver` &bull; `SSLCertificate` &bull; `Subdomain` &bull; `HTTPHeader`

### Building Your Own Transforms

Want to build your own? See the [contributing guide](https://github.com/opengraphintel/ogi-transforms/blob/main/CONTRIBUTING.md).

If your transform needs external service credentials, declare them in `api_keys_required`. Do not store secrets in transform settings. OGI manages those under `API Keys`, and secret-using plugins are considered privileged code.

If your transform exposes capped settings such as `max_results` or `max_content_chars`, prefer stable setting names over bespoke one-off names where possible. OGI can centrally override max values with `OGI_TRANSFORM_SETTING_MAX_OVERRIDES`, which helps cloud deployments enforce limits while local users can remove them.

Each plugin is a directory with a `plugin.yaml` manifest:

```yaml
name: my-transform
version: "1.0.0"
display_name: My Transform
description: What it does
author: Your Name
license: MIT
category: dns
input_types: [Domain]
output_types: [IPAddress]
min_ogi_version: "0.9.0"
permissions:
  network: true
  filesystem: false
  subprocess: false
```

## Architecture

### Tech Stack

| Layer            | Technology                                                                  |
| ---------------- | --------------------------------------------------------------------------- |
| Backend          | Python 3.14+, FastAPI, SQLModel, asyncpg / aiosqlite                        |
| Frontend         | React 19, TypeScript 5.9, Sigma.js (graphology), Zustand, Tailwind CSS 4    |
| Maps             | MapLibre GL, with keyless Esri and OpenStreetMap basemaps (CARTO optional)  |
| Database         | PostgreSQL 16 (primary) / SQLite (local fallback)                           |
| Auth & Realtime  | Supabase Auth + JWT + Realtime (optional in local mode)                     |
| Job Queue        | Redis 7 + RQ (async transforms)                                             |
| AI Runtime       | Provider-backed AI Investigator worker with audited transform orchestration |
| Package Managers | uv (backend), pnpm (frontend)                                               |
| Deployment       | Docker, nginx, GHCR                                                         |

### Project Structure

```
ogi/
├── backend/
│   ├── alembic/            # PostgreSQL migrations
│   ├── tests/              # pytest suite
│   └── ogi/
│       ├── agent/          # AI Investigator (planner, LLM providers, worker)
│       ├── api/            # REST API routes
│       ├── cli/            # CLI tool (Typer)
│       ├── db/             # Database layer (asyncpg + aiosqlite)
│       ├── engine/         # Graph engine & transform engine
│       ├── models/         # SQLModel definitions
│       ├── store/          # Data stores
│       ├── transforms/     # Built-in transforms
│       │   ├── cert/       # SSL/TLS certificates
│       │   ├── dns/        # DNS records, reverse DNS, WHOIS
│       │   ├── email/      # Email enrichment
│       │   ├── hash/       # Hash lookups
│       │   ├── ip/         # IP geolocation and ASN
│       │   ├── location/   # Geocoding, timezone, weather, nearby ASNs
│       │   ├── person/     # Username generation
│       │   ├── social/     # Username search
│       │   └── web/        # Web scraping/extraction
│       ├── worker/         # Async job queue (RQ)
│       ├── billing.py      # Cloud-only Supporter billing
│       ├── telemetry.py    # Installation telemetry
│       ├── config.py       # Pydantic settings
│       └── main.py         # FastAPI entry point
├── frontend/
│   └── src/
│       ├── api/            # API client
│       ├── components/     # React components
│       ├── hooks/          # Custom hooks (realtime sync, etc.)
│       ├── lib/            # Graph layouts, theming, basemaps, runtime env
│       ├── stores/         # Zustand state management
│       ├── styles/         # Tailwind theme tokens
│       ├── types/          # TypeScript types
│       └── App.tsx         # Main application
├── plugins/                # Community plugins directory
├── docs/                   # Documentation & images
├── docker-compose.yml      # Development deployment
├── docker-compose.prod.yml # Production deployment
└── .env.example            # Environment template
```

### Configuration

OGI uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) with `.env` file support. Runtime/backend variables are prefixed with `OGI_`.

List-style settings accept either:

- JSON arrays, for example `["plugins","../plugins"]`
- comma-separated strings, for example `plugins,../plugins`

<details>
<summary><strong>Key environment variables</strong></summary>

| Variable                                        | Description                                                                                                      | Default                                             |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `OGI_APP_NAME`                                  | Application name                                                                                                 | `OGI`                                               |
| `OGI_HOST`                                      | Backend bind host                                                                                                | `0.0.0.0`                                           |
| `OGI_PORT`                                      | Backend port                                                                                                     | `8000`                                              |
| `OGI_CORS_ORIGINS`                              | Allowed frontend origins                                                                                         | `http://localhost:5173,http://localhost:3000`       |
| `OGI_USE_SQLITE`                                | Use SQLite instead of PostgreSQL                                                                                 | `true`                                              |
| `OGI_DB_PATH`                                   | SQLite database file path                                                                                        | `ogi.db`                                            |
| `OGI_DATABASE_URL`                              | PostgreSQL connection string                                                                                     | `postgresql://postgres:postgres@localhost:5432/ogi` |
| `OGI_REDIS_URL`                                 | Redis connection string for RQ/jobs                                                                              | `redis://localhost:6379/0`                          |
| `OGI_RQ_QUEUE_NAME`                             | Queue name for transform jobs                                                                                    | `transforms`                                        |
| `OGI_TRANSFORM_TIMEOUT`                         | Per-transform job timeout in seconds                                                                             | `300`                                               |
| `OGI_AGENT_WORKER_POLL_INTERVAL_SEC`            | Poll interval for the AI Investigator worker                                                                     | `1.0`                                               |
| `OGI_AGENT_CLAIM_TIMEOUT_SEC`                   | Stale-claim timeout for AI Investigator step recovery                                                            | `300`                                               |
| `OGI_AUTO_RUN_MIGRATIONS`                       | Auto-run Alembic on local non-SQLite app startup                                                                 | `true`                                              |
| `OGI_RUN_DB_MIGRATIONS`                         | Run DB migrations in container entrypoint                                                                        | `false`                                             |
| `OGI_DB_MIGRATION_RETRIES`                      | Entry-point migration retry count                                                                                | `30`                                                |
| `OGI_DB_MIGRATION_DELAY_SECONDS`                | Delay between entry-point migration retries                                                                      | `2`                                                 |
| `OGI_PLUGIN_DIRS`                               | Plugin search directories                                                                                        | `plugins,../plugins`                                |
| `OGI_DEPLOYMENT_MODE`                           | Deployment mode (`self-hosted` or `cloud`)                                                                       | `self-hosted`                                       |
| `OGI_CLOUD_BILLING_ENABLED`                     | Enable cloud-only Supporter billing and transform cooldown enforcement                                           | `false`                                             |
| `OGI_FREE_TRANSFORM_COOLDOWN_SECONDS`           | Cooldown between free cloud-user transformer runs                                                                | `1800`                                              |
| `OGI_PAID_TRANSFORM_COOLDOWN_SECONDS`           | Cooldown between paid cloud-user transformer runs                                                                | `0`                                                 |
| `OGI_STRIPE_SECRET_KEY`                         | Stripe server-side secret key for Checkout and portal sessions                                                   | unset                                               |
| `OGI_STRIPE_WEBHOOK_SECRET`                     | Stripe webhook signing secret                                                                                    | unset                                               |
| `OGI_STRIPE_SUPPORTER_PRICE_ID`                 | Stripe recurring Price ID for the Supporter plan                                                                 | unset                                               |
| `OGI_STRIPE_SUPPORTER_AMOUNT_CENTS`             | Display amount for the Supporter plan                                                                            | `300`                                               |
| `OGI_STRIPE_SUPPORTER_CURRENCY`                 | Display currency for the Supporter plan                                                                          | `usd`                                               |
| `OGI_BILLING_SUCCESS_URL`                       | Optional Stripe Checkout success redirect                                                                        | derived from request                                |
| `OGI_BILLING_CANCEL_URL`                        | Optional Stripe Checkout cancel redirect                                                                         | derived from request                                |
| `OGI_BILLING_PORTAL_RETURN_URL`                 | Optional Stripe billing portal return URL                                                                        | derived from request                                |
| `OGI_REGISTRY_REPO`                             | Transform registry GitHub repo                                                                                   | `opengraphintel/ogi-transforms`                     |
| `OGI_REGISTRY_CACHE_TTL`                        | Registry cache TTL in seconds                                                                                    | `3600`                                              |
| `OGI_TRANSFORM_SETTING_MAX_OVERRIDES`           | Optional global max override map for transform settings                                                          | empty                                               |
| `OGI_GITHUB_TOKEN`                              | Optional GitHub token for registry/API rate limits                                                               | unset                                               |
| `OGI_SUPABASE_URL`                              | Supabase project URL                                                                                             | unset                                               |
| `OGI_SUPABASE_ANON_KEY`                         | Supabase anon/public key                                                                                         | unset                                               |
| `OGI_SUPABASE_SERVICE_ROLE_KEY`                 | Supabase service-role key                                                                                        | unset                                               |
| `OGI_SUPABASE_JWT_SECRET`                       | Supabase JWT secret                                                                                              | unset                                               |
| `OGI_SUPABASE_REDIRECT_URL`                     | Redirect URL for frontend auth flows (compose passes it to the frontend as `VITE_SUPABASE_REDIRECT_URL`)         | unset                                               |
| `OGI_ADMIN_EMAILS`                              | Admin users for registry/plugin management                                                                       | unset                                               |
| `OGI_TELEMETRY_ENABLED`                         | Enable or disable installation-level telemetry                                                                   | `true`                                              |
| `OGI_TELEMETRY_LEVEL`                           | Telemetry level (`basic` or `full`)                                                                              | `full`                                              |
| `OGI_API_KEY_ENCRYPTION_KEY`                    | Fernet key for encrypted API key storage                                                                         | unset but strongly recommended                      |
| `OGI_API_KEY_INJECTION_ALLOW_COMMUNITY_PLUGINS` | Allow community plugins to receive stored API keys                                                               | `true`                                              |
| `OGI_API_KEY_INJECTION_TRUSTED_TIERS_ONLY`      | Restrict stored key injection to trusted tiers only                                                              | `false`                                             |
| `OGI_API_KEY_INJECTION_ALLOWED_TIERS`           | Tiers allowed when trusted-only mode is enabled                                                                  | `official,verified`                                 |
| `OGI_API_KEY_SERVICE_ALLOWLIST`                 | Optional allowed services for stored key injection                                                               | empty                                               |
| `OGI_API_KEY_SERVICE_BLOCKLIST`                 | Optional blocked services for stored key injection                                                               | empty                                               |
| `OGI_LLM_PROVIDER`                              | Fallback AI Investigator provider (`openai`, `anthropic`, or `gemini`) when a user has none saved                | unset                                               |
| `OGI_LLM_MODEL`                                 | Fallback AI Investigator model when a user has none saved                                                        | unset                                               |
| `OGI_LLM_API_KEY`                               | Fallback provider API key for the AI Investigator                                                                | unset                                               |
| `OGI_EXPOSE_ERROR_DETAILS`                      | Include internal details in 500 responses                                                                        | `false`                                             |
| `OGI_SANDBOX_ALLOWED_TIERS`                     | Verification tiers that can be installed from the Transform Hub in cloud mode                                    | `official,verified`                                 |
| `OGI_MEDIA_DIR`                                 | Local directory for uploaded media when Supabase Storage is not used                                             | `media`                                             |
| `OGI_MEDIA_UPLOAD_MAX_BYTES`                    | Maximum size of an uploaded image                                                                                | `5242880`                                           |
| `OGI_BOOT_REQUIREMENTS_ENABLE`                  | Enable boot-time plugin dependency install                                                                       | `true`                                              |
| `OGI_BOOT_REQUIREMENTS_FILE`                    | Boot requirements file path                                                                                      | `/app/plugins/requirements.txt`                     |
| `OGI_BOOT_LOCK_FILE`                            | Boot lock file path                                                                                              | `/app/plugins/ogi-lock.json`                        |
| `OGI_BOOT_REQUIREMENTS_STRICT`                  | Fail startup if plugin requirements are missing                                                                  | `false`                                             |
| `OGI_BOOT_REQUIREMENTS_CACHE_DIR`               | Temp/cache directory for boot requirement generation                                                             | `/tmp/ogi-boot`                                     |
| `OGI_FRONTEND_PORT`                             | Local Docker frontend port mapping                                                                               | `3000`                                              |
| `OGI_IMAGE_TAG`                                 | Prod image tag for compose/Coolify-style deploys                                                                 | `latest`                                            |
| `OGI_BACKEND_IMAGE`                             | Optional backend image override                                                                                  | `ghcr.io/khashashin/ogi-backend`                    |
| `OGI_WORKER_IMAGE`                              | Optional worker image override. Defaults to backend image because worker and backend share the same image build. | `ghcr.io/khashashin/ogi-backend`                    |
| `OGI_FRONTEND_IMAGE`                            | Optional frontend image override                                                                                 | `ghcr.io/khashashin/ogi-frontend`                   |
| `OGI_CLI_BEARER_TOKEN`                          | Optional CLI bearer token for auth-enabled backends                                                              | unset                                               |

See [`.env.example`](.env.example) for the full list.

</details>

<details>
<summary><strong>Frontend runtime variables</strong></summary>

The frontend container writes these into `env.js` when it starts, so changing one needs only a restart, not a rebuild. They reach the browser, so use publishable values only. The compose files fill the Supabase entries from the `OGI_SUPABASE_*` variables.

| Variable                     | Description                                                                                     |
| ---------------------------- | ----------------------------------------------------------------------------------------------- |
| `VITE_SUPABASE_URL`          | Supabase project URL. Leave unset to run without sign-in                                        |
| `VITE_SUPABASE_ANON_KEY`     | Supabase anon/public key                                                                        |
| `VITE_SUPABASE_REDIRECT_URL` | Redirect URL for auth flows                                                                     |
| `VITE_TURNSTILE_SITE_KEY`    | Cloudflare Turnstile site key. Required when the Supabase project has captcha protection on     |
| `VITE_GA_MEASUREMENT_ID`     | Optional Google Analytics measurement ID                                                        |
| `VITE_CARTO_API_KEY`         | Optional CARTO key. Without it the map offers only the keyless Esri and OpenStreetMap basemaps  |

</details>

## Development

### Running Tests

The backend's test and lint tools are in the `dev` extra. The tests configure their own in-memory SQLite database.

```bash
# Backend
cd backend
uv sync --extra dev
uv run pytest

# Frontend
cd frontend
pnpm test -- --run       # single run; plain `pnpm test` starts watch mode
```

### Linting & Type Checking

```bash
# Backend (the files CI checks today)
cd backend
uv run ruff check ogi/api/router.py ogi/main.py ogi/config.py
uv run mypy --follow-imports=skip ogi/api/router.py

# Frontend
cd frontend
pnpm lint                # ESLint
pnpm build               # TypeScript check + production build
```

### CI Pipeline

The [CI workflow](.github/workflows/ci.yml) runs on every pull request:

- **Backend:** `uv sync --locked`, ruff and mypy on the files above, pytest
- **Frontend:** vitest, eslint, `pnpm build` (TypeScript and Vite)

## Contributing

PRs welcome! If you find a bug or have an idea, [open an issue](https://github.com/khashashin/ogi/issues).

For new transforms, contribute to [ogi-transforms](https://github.com/opengraphintel/ogi-transforms).

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Legal & Responsible Use

OGI is a general-purpose OSINT and graph analysis tool. **You are solely responsible for how you use it.** See [LEGAL.md](LEGAL.md) for the full legal notice.

- **Comply with third-party Terms of Service.** Transforms that query external services (DNS, WHOIS, web scraping, username lookups, etc.) must be used in accordance with the ToS of those services. Automated or bulk querying of sites that prohibit it may violate their terms.
- **Respect data protection law.** If you are in the EU or processing data about EU residents, GDPR applies to you as the data controller. Collecting, storing, or processing personal data (names, email addresses, IP addresses, etc.) requires a lawful basis. OGI itself does not store data beyond your local instance — you are responsible for what you collect and retain.
- **Use for lawful purposes only.** OGI is intended for legitimate security research, investigations, threat intelligence, and educational use. Do not use it to harass individuals, conduct unauthorized access, or violate applicable law.
- **File format compatibility.** OGI supports import of the MTGX graph exchange format. This is provided purely for data interoperability and does not imply any affiliation with or endorsement by the makers of tools that use this format.

> **Disclaimer:** OGI is provided "as is" without warranty of any kind. The authors are not liable for any misuse or damages arising from use of this software.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

---

<div align="center">

**[Report Bug](https://github.com/khashashin/ogi/issues) &bull; [Request Feature](https://github.com/khashashin/ogi/issues) &bull; [Discussions](https://github.com/opengraphintel/ogi-transforms/discussions)**

Made with 💜 by the OGI community

</div>
