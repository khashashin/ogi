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
[![FastAPI](https://img.shields.io/badge/FastAPI-0.134-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
![Version](https://img.shields.io/github/v/release/khashashin/ogi?display_name=tag&color=green)

[Features](#features) &bull; [Screenshots](#screenshots) &bull; [Quick Start](#quick-start) &bull; [Docker](#docker) &bull; [Transform Hub](#transform-hub) &bull; [Architecture](#architecture) &bull; [Contributing](#contributing)

</div>

---

> **Heads up:** This project is actively evolving. It has solid core capabilities and test coverage, and we continue to improve documentation, hardening, and feature depth with each release. Contributions, bug reports, and feedback are very welcome.

## Features

- **Visual graph investigation** — drag-and-drop entities, explore connections interactively
- **20+ built-in transforms** — DNS, WHOIS, SSL certs, geolocation, web/email/hash/social enrichment, and more
- **Transform Hub** — browse and install community transforms from the [registry](https://github.com/opengraphintel/ogi-transforms)
- **Import / Export** — JSON, CSV, GraphML, and MTGX format import
- **Graph analysis** — centrality, community detection, shortest paths
- **Real-time collaboration** — projects, sharing, and live sync via Supabase Realtime
- **Async transform jobs** — Redis/RQ queue with WebSocket progress updates
- **Plugin system** — directory-based plugin discovery with YAML manifests
- **CLI tool** — search, install, and manage transforms from the terminal
- **Runs anywhere** — local SQLite mode (zero config) or PostgreSQL + Supabase for team/cloud setups
- **Docker ready** — one-command deployment with `docker compose up`

## Screenshots

<div align="center">

|              Graph Investigation              |              Entity Enrichment              |
| :-------------------------------------------: | :-----------------------------------------: |
| ![Graph Investigation](docs/images/demo1.png) | ![Entity Enrichment](docs/images/demo2.png) |

|              Transform Hub              |             Export / Import             |
| :-------------------------------------: | :-------------------------------------: |
| ![Transform Hub](docs/images/demo3.png) | ![Export Import](docs/images/demo4.png) |

</div>

## Quick Start

### Prerequisites

| Tool                             | Version |
| -------------------------------- | ------- |
| [Python](https://www.python.org) | 3.14+   |
| [uv](https://docs.astral.sh/uv/) | latest  |
| [Node.js](https://nodejs.org)    | 20+     |
| [pnpm](https://pnpm.io)          | latest  |

### Backend

```bash
cd backend
uv sync
uv run uvicorn ogi.main:app --reload
```

The API will be available at `http://localhost:8000`.

If you run the backend against PostgreSQL (`OGI_USE_SQLITE=false`), startup will automatically apply Alembic migrations before serving requests. Docker deployments do the same in the backend container entrypoint.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:5173. That's it.

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

### Production

Use the prebuilt GHCR images:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Set `OGI_IMAGE_TAG` in `.env` to pin a specific release image tag (e.g. `v0.2.6`). Defaults to `latest`.

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

<details>
<summary><strong>Services overview</strong></summary>

| Service    | Description                | Port |
| ---------- | -------------------------- | ---- |
| `backend`  | FastAPI application server | 8000 |
| `worker`   | RQ async job worker        | -    |
| `frontend` | React app served via nginx | 80   |
| `db`       | PostgreSQL 16              | 5432 |
| `redis`    | Redis 7 (job queue)        | 6379 |

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
uv run ogi transform install shodan-host-lookup
```

### Built-in Transform Categories

| Category | Examples                              |
| -------- | ------------------------------------- |
| DNS      | A, AAAA, MX, NS, CNAME records        |
| IP & ASN | GeoIP, reverse IP, ASN info           |
| SSL/TLS  | Certificate transparency, SSL labs    |
| Email    | Mailserver validation, breach checks  |
| Web      | WHOIS, domain info, web extraction    |
| Social   | Username enumeration, social profiles |
| Hash     | MD5, SHA1, SHA256 lookups             |
| Location | Geocoding, weather, nearby ASN data   |

### Supported Entity Types

`Person` &bull; `Username` &bull; `Domain` &bull; `IPAddress` &bull; `EmailAddress` &bull; `PhoneNumber` &bull; `Organization` &bull; `URL` &bull; `SocialMedia` &bull; `Hash` &bull; `Document` &bull; `Location` &bull; `ASNumber` &bull; `Network` &bull; `MXRecord` &bull; `NSRecord` &bull; `Nameserver` &bull; `SSLCertificate` &bull; `Subdomain` &bull; `HTTPHeader`

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
permissions:
  network: true
  filesystem: false
  subprocess: false
```

## Architecture

### Tech Stack

| Layer            | Technology                                                               |
| ---------------- | ------------------------------------------------------------------------ |
| Backend          | Python 3.14+, FastAPI, SQLModel, asyncpg / aiosqlite                     |
| Frontend         | React 19, TypeScript 5.9, Sigma.js (graphology), Zustand, Tailwind CSS 4 |
| Database         | PostgreSQL 16 (primary) / SQLite (local fallback)                        |
| Auth & Realtime  | Supabase Auth + JWT + Realtime (optional in local mode)                  |
| Job Queue        | Redis 7 + RQ (async transforms)                                          |
| Package Managers | uv (backend), pnpm (frontend)                                            |
| Deployment       | Docker, nginx, GHCR                                                      |

### Project Structure

```
ogi/
├── backend/
│   └── ogi/
│       ├── api/            # REST API routes
│       ├── cli/            # CLI tool (Typer)
│       ├── db/             # Database layer (asyncpg + aiosqlite)
│       ├── engine/         # Graph engine & transform engine
│       ├── models/         # SQLModel definitions
│       ├── store/          # Data stores
│       ├── transforms/     # Built-in transforms
│       │   ├── dns/        # DNS resolution transforms
│       │   ├── cert/       # SSL certificate transforms
│       │   ├── email/      # Email enrichment
│       │   ├── hash/       # Hash lookups
│       │   ├── ip/         # IP/ASN/geolocation
│       │   ├── org/        # Organization info
│       │   ├── social/     # Social media
│       │   └── web/        # Web scraping/extraction
│       ├── worker/         # Async job queue (RQ)
│       ├── config.py       # Pydantic settings
│       └── main.py         # FastAPI entry point
├── frontend/
│   └── src/
│       ├── api/            # API client
│       ├── components/     # React components
│       ├── hooks/          # Custom hooks (realtime sync, etc.)
│       ├── stores/         # Zustand state management
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
| `OGI_AUTO_RUN_MIGRATIONS`                       | Auto-run Alembic on local non-SQLite app startup                                                                 | `true`                                              |
| `OGI_RUN_DB_MIGRATIONS`                         | Run DB migrations in container entrypoint                                                                        | `false`                                             |
| `OGI_DB_MIGRATION_RETRIES`                      | Entry-point migration retry count                                                                                | `30`                                                |
| `OGI_DB_MIGRATION_DELAY_SECONDS`                | Delay between entry-point migration retries                                                                      | `2`                                                 |
| `OGI_PLUGIN_DIRS`                               | Plugin search directories                                                                                        | `plugins,../plugins`                                |
| `OGI_DEPLOYMENT_MODE`                           | Deployment mode (`self-hosted` or `cloud`)                                                                       | `self-hosted`                                       |
| `OGI_REGISTRY_REPO`                             | Transform registry GitHub repo                                                                                   | `opengraphintel/ogi-transforms`                     |
| `OGI_REGISTRY_CACHE_TTL`                        | Registry cache TTL in seconds                                                                                    | `3600`                                              |
| `OGI_TRANSFORM_SETTING_MAX_OVERRIDES`           | Optional global max override map for transform settings                                                          | empty                                               |
| `OGI_GITHUB_TOKEN`                              | Optional GitHub token for registry/API rate limits                                                               | unset                                               |
| `OGI_SUPABASE_URL`                              | Supabase project URL                                                                                             | unset                                               |
| `OGI_SUPABASE_ANON_KEY`                         | Supabase anon/public key                                                                                         | unset                                               |
| `OGI_SUPABASE_SERVICE_ROLE_KEY`                 | Supabase service-role key                                                                                        | unset                                               |
| `OGI_SUPABASE_JWT_SECRET`                       | Supabase JWT secret                                                                                              | unset                                               |
| `OGI_SUPABASE_REDIRECT_URL`                     | Redirect URL used by frontend auth flows                                                                         | unset                                               |
| `OGI_ADMIN_EMAILS`                              | Admin users for registry/plugin management                                                                       | unset                                               |
| `OGI_API_KEY_ENCRYPTION_KEY`                    | Fernet key for encrypted API key storage                                                                         | unset but strongly recommended                      |
| `OGI_API_KEY_INJECTION_ALLOW_COMMUNITY_PLUGINS` | Allow community plugins to receive stored API keys                                                               | `true`                                              |
| `OGI_API_KEY_INJECTION_TRUSTED_TIERS_ONLY`      | Restrict stored key injection to trusted tiers only                                                              | `false`                                             |
| `OGI_API_KEY_INJECTION_ALLOWED_TIERS`           | Tiers allowed when trusted-only mode is enabled                                                                  | `official,verified`                                 |
| `OGI_API_KEY_SERVICE_ALLOWLIST`                 | Optional allowed services for stored key injection                                                               | empty                                               |
| `OGI_API_KEY_SERVICE_BLOCKLIST`                 | Optional blocked services for stored key injection                                                               | empty                                               |
| `OGI_EXPOSE_ERROR_DETAILS`                      | Include internal details in 500 responses                                                                        | `false`                                             |
| `OGI_SANDBOX_ENABLED`                           | Enable sandbox execution mode                                                                                    | `false`                                             |
| `OGI_SANDBOX_TIMEOUT`                           | Sandbox timeout in seconds                                                                                       | `30`                                                |
| `OGI_SANDBOX_MEMORY_MB`                         | Sandbox memory limit in MB                                                                                       | `256`                                               |
| `OGI_SANDBOX_ALLOWED_TIERS`                     | Allowed tiers in cloud sandbox mode                                                                              | `official,verified`                                 |
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

## Development

### Running Tests

```bash
# Backend
cd backend
OGI_DB_PATH=":memory:" OGI_USE_SQLITE=true uv run pytest

# Frontend
cd frontend
pnpm test
```

### Linting & Type Checking

```bash
# Backend
cd backend
uv run ruff check        # Linting
uv run mypy              # Type checking

# Frontend
cd frontend
pnpm lint                # ESLint
```

### CI Pipeline

The [CI workflow](.github/workflows/ci.yml) runs on every pull request:

- **Backend:** ruff lint, mypy type check, pytest
- **Frontend:** vitest, eslint, vite build

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
