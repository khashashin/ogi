Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
OGI Transform Hub — Architecture Document

Context

OGI currently has a local plugin system: transforms live in a plugins/ directory, are discovered via plugin.yaml manifests, and loaded dynamically by PluginEngine. This works for local development but has no mechanism for discovery, distribution,
community contribution, quality signals, or safe execution in a hosted environment.

This document designs two features from the roadmap:

- Transform Hub (Phase 2, Weeks 13–14): CLI tool for installing transforms, package format spec, local registry
- Transform Marketplace (Phase 3, Weeks 34–36): Online transform registry/marketplace, ratings, automated security scanning

Design Principles

- GitHub-native: The registry is a GitHub repo. No custom infrastructure to host or maintain.
- Atomic transforms: Each transform is independently installable, versioned, and rated.
- Tiered trust: Cloud mode only allows official/verified transforms (sandboxed). Self-hosted allows everything.
- Community-driven: Contributions via PRs, reviews via GitHub Discussions reactions.

---

1.  GitHub-based Registry Repository

Inspiration: Homebrew's Formulae Model

A single GitHub repository (opengraphintel/ogi-transforms) serves as the canonical registry. Community contributes via PRs. CI validates submissions. A machine-readable index.json is auto-generated on merge.

Repository Layout

opengraphintel/ogi-transforms/
├── README.md
├── CONTRIBUTING.md
├── LICENSE # AGPLv3
├── .github/
│ ├── workflows/
│ │ ├── validate-pr.yml # CI: lint, security scan, tests
│ │ ├── build-index.yml # Generate index.json on merge to main
│ │ └── create-discussion.yml # Auto-create Discussion for new transforms
│ ├── PULL_REQUEST_TEMPLATE.md
│ └── ISSUE_TEMPLATE/
│ ├── bug_report.yml
│ └── new_transform_request.yml
├── schema/
│ └── plugin-v2.schema.json # JSON Schema for plugin.yaml validation
├── transforms/
│ ├── dns/
│ │ ├── domain-to-ip/
│ │ │ ├── plugin.yaml # v2 manifest
│ │ │ ├── README.md
│ │ │ ├── CHANGELOG.md
│ │ │ └── transforms/
│ │ │ ├── **init**.py
│ │ │ └── domain_to_ip.py
│ │ ├── domain-to-mx/
│ │ │ └── ...
│ │ └── domain-to-ns/
│ │ └── ...
│ ├── email/
│ │ └── email-to-domain/
│ │ └── ...
│ ├── web/
│ │ └── url-to-headers/
│ │ └── ...
│ ├── ip/
│ │ └── ip-to-geolocation/
│ │ └── ...
│ ├── cert/
│ │ └── domain-to-certs/
│ │ └── ...
│ ├── social/
│ │ └── username-search/
│ │ └── ...
│ ├── hash/
│ │ └── hash-lookup/
│ │ └── ...
│ ├── infrastructure/
│ │ └── shodan-host-lookup/ # Community-contributed example
│ │ └── ...
│ └── forensics/
│ └── ...
├── index.json # Auto-generated, machine-readable
└── categories.json # Category taxonomy

Key decision: One transform per directory. This diverges from the current plugin model where a plugin bundles multiple transforms. Atomic transforms are easier to discover, rate, version, and install independently. A transform directory may still
contain multiple .py files in transforms/ if they are tightly coupled, but the unit of installation/versioning/rating is the directory.

Built-in transforms remain in backend/ogi/transforms/. The registry repo contains copies for documentation and discovery, but they ship with OGI itself. The index marks them with "bundled": true.

Contribution Flow

1.  Contributor forks ogi-transforms, creates transforms/<category>/<slug>/ with required files
2.  Opens PR using the template (description, entity types, API keys needed, test evidence)
3.  CI validates (schema, lint, security scan, tests)
4.  Maintainers review code and merge
5.  On merge: build-index.yml regenerates index.json, create-discussion.yml creates a Discussion thread

CI/CD Validation (validate-pr.yml)

Runs on every PR:

┌───────────────────┬───────────────┬─────────────────────────────────────────────────────────────────────┐
│ Step │ Tool │ Purpose │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Schema validation │ jsonschema │ Validates plugin.yaml against plugin-v2.schema.json │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Python linting │ ruff │ Code style and common errors │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Type checking │ mypy │ Type safety │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Security scan │ bandit │ Dangerous function calls (eval, exec, os.system) │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Pattern scan │ semgrep │ Custom rules: blocks subprocess, ctypes, raw socket, **import** │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Dependency audit │ Custom script │ Verifies all python_dependencies are from an allowlist │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Structure check │ Custom script │ Verifies required files exist (plugin.yaml, transforms/, README.md) │
├───────────────────┼───────────────┼─────────────────────────────────────────────────────────────────────┤
│ Tests │ pytest │ Runs tests if tests/ directory exists (30s timeout) │
└───────────────────┴───────────────┴─────────────────────────────────────────────────────────────────────┘

Index Generation (build-index.yml)

Triggered on merge to main. Walks transforms/, reads each plugin.yaml, scrapes GitHub Discussions reaction counts via GraphQL API, and produces index.json:

{
"version": 2,
"generated_at": "2026-03-01T12:00:00Z",
"repo": "opengraphintel/ogi-transforms",
"transforms": [
{
"slug": "domain-to-ip",
"name": "domain_to_ip",
"display_name": "Domain to IP Address",
"description": "Resolves A and AAAA records for a domain",
"version": "1.2.0",
"author": "OGI Team",
"author_github": "ogi-hub",
"license": "AGPL-3.0",
"category": "dns",
"input_types": ["Domain"],
"output_types": ["IPAddress"],
"min_ogi_version": "0.3.0",
"python_dependencies": ["dnspython>=2.8.0"],
"api_keys_required": [],
"tags": ["dns", "resolution", "infrastructure"],
"verification_tier": "official",
"bundled": true,
"permissions": { "network": true, "filesystem": false, "subprocess": false },
"download_url": "https://raw.githubusercontent.com/opengraphintel/ogi-transforms/main/transforms/dns/domain-to-ip/",
"readme_url": "https://github.com/opengraphintel/ogi-transforms/blob/main/transforms/dns/domain-to-ip/README.md",
"sha256": "abc123...",
"popularity": {
"thumbs_up": 42,
"thumbs_down": 2,
"total_contributors": 3,
"commits_last_90_days": 7,
"discussion_url": "https://github.com/opengraphintel/ogi-transforms/discussions/17",
"computed_score": 89
},
"created_at": "2026-01-15",
"updated_at": "2026-03-01"
}
]
}

---

2.  Plugin Package Format Spec (v2)

Extended plugin.yaml

Current v1 (at plugins/example-plugin/plugin.yaml):
name: example-plugin
version: "1.0.0"
display_name: "Example Plugin"
description: "A sample plugin"
author: "OGI Team"

Proposed v2:

# Required

schema_version: 2
name: shodan-host-lookup # Slug: lowercase, hyphens only
version: "1.0.0" # Semver required
display_name: "Shodan Host Lookup"
description: "Queries Shodan API for host information"
author: "Jane Smith"
license: "AGPL-3.0"
category: "infrastructure"
input_types: ["IPAddress"]
output_types: ["Document", "Network"]
min_ogi_version: "0.3.0"

# Optional — Discovery & Metadata

tags: ["shodan", "ports", "services"]
author_github: "janesmith"
homepage: "https://github.com/janesmith/ogi-shodan"
repository: "https://github.com/janesmith/ogi-shodan"
max_ogi_version: null
icon: "radio" # Lucide icon name
color: "#dc2626" # Accent color hex

# Optional — Dependencies

python_dependencies:

- "shodan>=1.31.0"
  api_keys_required:
- service: "shodan"
  description: "Shodan API key from https://shodan.io"
  env_var: "SHODAN_API_KEY"

# Optional — Safety (used by cloud sandboxing and CI)

permissions:
network: true
filesystem: false
subprocess: false

# Optional — Defaults

enabled: true

Required Directory Structure

<slug>/
├── plugin.yaml # v2 manifest (REQUIRED)
├── README.md # Human-readable docs (REQUIRED for registry)
├── CHANGELOG.md # Version history (recommended)
├── transforms/
│ ├── **init**.py # REQUIRED
│ └── \_.py # One or more transform implementations
└── tests/ # Recommended
└── test\_\_.py

Versioning Strategy

- Semver required for all registry transforms
- min_ogi_version is mandatory — specifies the oldest OGI version this transform works with
- max_ogi_version optional — only set when OGI ships a breaking change to the transform API
- Version history accessible via git log in the registry repo
- Lock file pins exact installed versions

Backward Compatibility

The PluginEngine at backend/ogi/engine/plugin_engine.py continues to support v1 manifests (no schema_version field = v1). V2 fields have sensible defaults. Existing local plugins work unchanged.

---

3.  CLI Tool

Framework & Entry Point

Built with https://typer.tiangolo.com/ (already idiomatic for FastAPI projects). Entry point in pyproject.toml:

[project.scripts]
ogi = "ogi.cli.main:app"

File Structure

backend/ogi/cli/
├── **init**.py
├── main.py # Typer app, top-level command groups
├── commands/
│ ├── **init**.py
│ ├── transform.py # `ogi transform ...` sub-commands
│ └── config.py # `ogi config ...` sub-commands
├── registry.py # GitHub registry client (fetch index, download)
├── installer.py # Download, verify, install, dependency resolution
└── lockfile.py # Lock file read/write

Commands

ogi transform search <query>

Fetches index.json from registry (cached locally for 1 hour), filters by name/description/tags/category.

$ ogi transform search shodan

NAME CATEGORY AUTHOR VERSION TIER
shodan-host-lookup infrastructure janesmith 1.0.0 community
shodan-domain-search dns janesmith 0.9.1 community

2 transforms found. Use `ogi transform install <name>` to install.

ogi transform install <slug>

1.  Fetch/cache index.json
2.  Find transform by slug, check OGI version compatibility
3.  Download files from GitHub raw content (via GitHub Contents API — list files, download each)
4.  Verify SHA256 checksum against index
5.  Install Python dependencies: uv pip install <deps>
6.  Copy to plugins/<slug>/
7.  Update plugins/ogi-lock.json
8.  If OGI server is running, call POST /api/v1/plugins/<slug>/reload to hot-load

$ ogi transform install shodan-host-lookup

Installing shodan-host-lookup v1.0.0...
Downloading from opengraphintel/ogi-transforms... done
Verifying checksum... ok
Installing dependencies: shodan>=1.31.0... done
Writing to plugins/shodan-host-lookup/... done
Updated ogi-lock.json.

⚠ Requires API key: SHODAN_API_KEY
Configure via: Settings > API Keys in the UI

ogi transform list

$ ogi transform list

INSTALLED:
domain-to-ip 1.2.0 dns official bundled
shodan-host-lookup 1.0.0 infra community registry

AVAILABLE (not installed):
virustotal-hash 0.8.0 hash verified registry
censys-search 1.1.0 infra community registry
...

15 installed, 42 available.

ogi transform update [slug]

Without args: checks all installed transforms for updates. With slug: updates specific one.

1.  Fetch fresh index.json
2.  Compare installed versions (from lock file) against latest
3.  Download, verify, replace
4.  Update lock file

ogi transform remove <slug>

1.  Refuse if bundled transform
2.  Remove plugins/<slug>/ directory
3.  Remove from lock file
4.  Call disable/unload API if server running

ogi transform info <slug>

Shows detailed info for any transform (installed or available).

Registry Client (backend/ogi/cli/registry.py)

REGISTRY_REPO = "opengraphintel/ogi-transforms"
INDEX_URL = f"https://raw.githubusercontent.com/{REGISTRY_REPO}/main/index.json"
CACHE_TTL = timedelta(hours=1)

class RegistryClient:
def **init**(self, cache_dir: Path):
...

     async def fetch_index(self, force: bool = False) -> RegistryIndex:
         """Fetch index.json, using local cache if fresh."""
         ...

     async def download_transform(self, slug: str, category: str, target_dir: Path) -> None:
         """Download transform files from GitHub raw content API."""
         # Uses: GET /repos/{owner}/{repo}/contents/transforms/{category}/{slug}
         # Downloads each file via raw URL
         ...

     def search(self, query: str, category: str | None = None) -> list[RegistryTransform]:
         """Filter cached index by query string."""
         ...

---

4.  Local Registry & Cache

Directory Layout

~/.ogi/ # User-level OGI config
├── config.toml # CLI configuration
└── cache/
├── index.json # Cached registry index
└── index_etag # HTTP ETag for conditional requests

<project>/plugins/ # Per-project installed transforms
├── shodan-host-lookup/
│ ├── plugin.yaml
│ ├── transforms/
│ │ ├── **init**.py
│ │ └── shodan_lookup.py
│ └── README.md
└── ogi-lock.json # Lock file

Lock File Format (plugins/ogi-lock.json)

Tracks installed transforms, their versions, and integrity hashes. Analogous to package-lock.json.

{
"lock_version": 1,
"ogi_version": "0.3.0",
"generated_at": "2026-03-01T14:30:00Z",
"registry_repo": "opengraphintel/ogi-transforms",
"transforms": {
"shodan-host-lookup": {
"version": "1.0.0",
"category": "infrastructure",
"verification_tier": "community",
"installed_at": "2026-03-01T14:30:00Z",
"sha256": "abc123def456...",
"source": "registry",
"python_dependencies": ["shodan>=1.31.0"],
"files": [
"plugin.yaml",
"transforms/__init__.py",
"transforms/shodan_lookup.py",
"README.md"
]
}
}
}

CLI Config (~/.ogi/config.toml)

[registry]
repo = "opengraphintel/ogi-transforms"
cache_ttl_hours = 1

[plugins]
dirs = ["plugins"]

[cli]
auto_confirm = false

---

5.  Cloud Mode Safety — Tiered Trust Model

Trust Tiers

┌──────┬──────────────┬───────────────────────────────┬─────────────────────────────────────┬────────────────────────────────┐
│ Tier │ Label │ Who assigns │ Cloud behavior │ Self-hosted behavior │
├──────┼──────────────┼───────────────────────────────┼─────────────────────────────────────┼────────────────────────────────┤
│ 1 │ Official │ OGI core team │ Pre-installed, runs in-process │ Pre-installed, runs in-process │
├──────┼──────────────┼───────────────────────────────┼─────────────────────────────────────┼────────────────────────────────┤
│ 2 │ Verified │ Maintainers after deep review │ Installable, runs in Docker sandbox │ Installable, runs in-process │
├──────┼──────────────┼───────────────────────────────┼─────────────────────────────────────┼────────────────────────────────┤
│ 3 │ Community │ Auto-assigned on merge │ Browse-only, not installable │ Installable, runs in-process │
├──────┼──────────────┼───────────────────────────────┼─────────────────────────────────────┼────────────────────────────────┤
│ 4 │ Experimental │ Auto-assigned on merge │ Not visible │ Installable with warning │
└──────┴──────────────┴───────────────────────────────┴─────────────────────────────────────┴────────────────────────────────┘

Verification Promotion Path

PR merged → Experimental (untested/new)
→ Community (has tests, passes CI, has README)
→ Verified (manual maintainer review, security audit, 30-day stability)
→ Official (maintained by OGI core team)

Tier is set in the transform's plugin.yaml by maintainers (not self-assigned by contributors). CI validates that contributors don't set verification_tier to anything above community.

Sandbox Architecture for Cloud Verified Transforms

User clicks "Run Transform" (cloud mode)
│
▼
┌──────────────────┐ ┌─────────────────────────────┐
│ OGI Backend │──────▶│ Sandbox Runner │
│ (FastAPI) │ HTTP │ (separate service/container) │
└──────────────────┘ └─────────────────────────────┘
│ Receives: entity JSON, │
│ transform code (read-only) │
│ API keys (injected env) │
│ Constraints: │
│ - Read-only filesystem │
│ - Network: HTTPS only to │
│ declared allowed_hosts │
│ - CPU: 1 core │
│ - Memory: 256MB │
│ - Timeout: 30 seconds │
│ - No volume mounts │
│ Returns: TransformResult JSON│
└─────────────────────────────┘

Implementation: Ephemeral Docker containers with a minimal Python image. Transform code mounted read-only. Entity data passed via stdin. Result collected from stdout.

New file: backend/ogi/engine/sandbox_runner.py

class SandboxRunner:
"""Executes transforms in isolated Docker containers (cloud mode)."""

     async def run_sandboxed(
         self,
         transform_path: Path,
         entity: Entity,
         config: TransformConfig,
         api_keys: dict[str, str],
         permissions: TransformPermissions,
         timeout: float = 30.0,
     ) -> TransformResult:
         # 1. Serialize entity + config to JSON
         # 2. Build/select Docker image with transform's dependencies
         # 3. Run container with restrictions
         # 4. Collect stdout (TransformResult JSON)
         # 5. Enforce timeout, kill if exceeded
         ...

Config Additions (backend/ogi/config.py)

class Settings(BaseSettings): # ... existing ...
deployment_mode: str = "self-hosted" # "cloud" | "self-hosted"
registry_repo: str = "opengraphintel/ogi-transforms"
registry_cache_ttl: int = 3600
sandbox_enabled: bool = False # Auto-enabled in cloud mode
sandbox_timeout: int = 30
sandbox_memory_mb: int = 256
sandbox_allowed_tiers: list[str] = ["official", "verified"]

Cloud API Enforcement

The install endpoint checks the trust tier:

@router.post("/install/{slug}")
async def install_transform(slug: str, ...):
if settings.deployment_mode == "cloud":
meta = registry.get(slug)
if meta.verification_tier not in settings.sandbox_allowed_tiers:
raise HTTPException(403, f"'{slug}' is tier '{meta.verification_tier}'. Cloud allows: {settings.sandbox_allowed_tiers}")
...

---

6.  Rating & Communication System

Per-Transform Ratings via GitHub Discussions

Since GitHub Stars are repo-level, per-transform popularity uses GitHub Discussions reactions:

1.  When a new transform is merged, create-discussion.yml auto-creates a Discussion in the "Transform Reviews" category
2.  The Discussion body contains the transform's README, version, input/output types
3.  Users react with 👍/👎 and leave comments (reviews, questions, bug reports)
4.  The build-index.yml workflow scrapes reaction counts via GitHub GraphQL API and includes them in index.json

Popularity Score Formula

score = (thumbs_up × 2) + (contributors × 3) + (recent_commits × 1) - (thumbs_down × 1)

Included in index.json per transform:

"popularity": {
"thumbs_up": 42,
"thumbs_down": 2,
"total_contributors": 3,
"commits_last_90_days": 7,
"discussion_url": "https://github.com/opengraphintel/ogi-transforms/discussions/17",
"computed_score": 89
}

GitHub Discussions Structure

opengraphintel/ogi-transforms Discussions
├── Announcements (maintainers only — pinned updates)
├── Transform Reviews (one auto-created discussion per transform)
├── Help & Support (Q&A format)
├── Transform Ideas (proposals for new transforms)
└── Show & Tell (users share investigation workflows)

---

7.  Backend Model & API Changes

Extended PluginInfo Model (backend/ogi/models/plugin.py)

class PluginInfo(SQLModel, table=True):
**tablename** = "plugins"

     # Existing fields
     id: UUID = Field(default_factory=uuid4, primary_key=True)
     name: str
     version: str = ""
     display_name: str = ""
     description: str = ""
     author: str = ""
     enabled: bool = True
     installed_at: datetime = Field(...)

     # v2 additions
     schema_version: int = 1
     category: str = ""
     license: str = ""
     author_github: str = ""
     homepage: str = ""
     repository: str = ""
     tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
     input_types: list[str] = Field(default_factory=list, sa_column=Column(JSON))
     output_types: list[str] = Field(default_factory=list, sa_column=Column(JSON))
     min_ogi_version: str = ""
     verification_tier: str = "community"    # official | verified | community | experimental
     api_keys_required: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
     python_dependencies: list[str] = Field(default_factory=list, sa_column=Column(JSON))
     permissions: dict[str, bool] = Field(default_factory=dict, sa_column=Column(JSON))
     source: str = "local"                   # local | registry | bundled
     registry_sha256: str = ""
     icon: str = ""
     color: str = ""

     # Runtime (not persisted in DB)
     transform_count: int = 0
     transform_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))

New API Router (backend/ogi/api/registry.py)

GET /api/v1/registry/index # Proxy cached index.json
GET /api/v1/registry/search?q=&category= # Search transforms
POST /api/v1/registry/install/{slug} # Download & install from registry
DELETE /api/v1/registry/remove/{slug} # Uninstall
POST /api/v1/registry/update/{slug} # Update to latest version
GET /api/v1/registry/check-updates # List transforms with available updates

These endpoints proxy the registry client so the frontend can install/manage transforms without the CLI.

---

8.  Frontend Changes

Component Architecture

frontend/src/
├── components/
│ └── marketplace/
│ ├── TransformHub.tsx # Main modal (replaces PluginManager)
│ ├── InstalledTab.tsx # Installed transforms + enable/disable
│ ├── BrowseTab.tsx # Registry browsing with search/filter
│ ├── UpdatesTab.tsx # Available updates
│ ├── TransformCard.tsx # Reusable card for a transform
│ ├── TransformDetail.tsx # Expanded view with README
│ ├── CategoryFilter.tsx # Category sidebar/pills
│ ├── VerificationBadge.tsx # Official/Verified/Community badge
│ └── InstallButton.tsx # Install/uninstall with progress
├── types/
│ └── registry.ts # New registry types
├── stores/
│ └── registryStore.ts # Zustand store for registry state
└── api/
└── client.ts # Extended with registry endpoints

UI Layout (TransformHub modal)

┌──────────────────────────────────────────────────────────┐
│ Transform Hub [X] │
├──────────────────────────────────────────────────────────┤
│ [Installed (12)] [Browse Registry (47)] [Updates (2)] │
├──────────────────────────────────────────────────────────┤
│ │
│ ┌──────────────┐ ┌──────────────────────────────────┐ │
│ │ Categories │ │ [🔍 Search transforms...] │ │
│ │ │ ├──────────────────────────────────┤ │
│ │ All │ │ ┌──────────────────────────────┐ │ │
│ │ DNS (8) │ │ │ 🔵 Official Domain to IP │ │ │
│ │ Email (4) │ │ │ Resolves A/AAAA records │ │ │
│ │ Web (3) │ │ │ by OGI Team Score: 94 │ │ │
│ │ IP (5) │ │ │ [Installed ✓] │ │ │
│ │ Cert (2) │ │ └──────────────────────────────┘ │ │
│ │ Social (3) │ │ ┌──────────────────────────────┐ │ │
│ │ Hash (2) │ │ │ 🟢 Verified Shodan Lookup │ │ │
│ │ Infra (6) │ │ │ Host info from Shodan API │ │ │
│ │ Forensic(4) │ │ │ by @janesmith Score: 42 │ │ │
│ │ │ │ │ [Install] 🔑 API key needed │ │ │
│ │ ── Tier ── │ │ └──────────────────────────────┘ │ │
│ │ ☑ Official │ │ ┌──────────────────────────────┐ │ │
│ │ ☑ Verified │ │ │ ⚪ Community VirusTotal │ │ │
│ │ ☑ Community │ │ │ Hash lookup via VT API │ │ │
│ │ ☐ Experiment │ │ │ by @secresearcher Score: 31 │ │ │
│ └──────────────┘ │ │ [Install] │ │ │
│ │ └──────────────────────────────┘ │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘

New Types (frontend/src/types/registry.ts)

Following the project convention (erasableSyntaxOnly — use const objects, not enum):

const VERIFICATION_TIERS = {
OFFICIAL: "official",
VERIFIED: "verified",
COMMUNITY: "community",
EXPERIMENTAL: "experimental",
} as const;
type VerificationTier = typeof VERIFICATION_TIERS[keyof typeof VERIFICATION_TIERS];

const TRANSFORM_SOURCES = {
BUNDLED: "bundled",
REGISTRY: "registry",
LOCAL: "local",
} as const;
type TransformSource = typeof TRANSFORM_SOURCES[keyof typeof TRANSFORM_SOURCES];

interface ApiKeyRequirement {
service: string;
description: string;
env_var: string;
}

interface TransformPermissions {
network: boolean;
filesystem: boolean;
subprocess: boolean;
}

interface TransformPopularity {
thumbs_up: number;
thumbs_down: number;
total_contributors: number;
commits_last_90_days: number;
discussion_url: string;
computed_score: number;
}

interface RegistryTransform {
slug: string;
name: string;
display_name: string;
description: string;
version: string;
author: string;
author_github: string;
license: string;
category: string;
input_types: string[];
output_types: string[];
min_ogi_version: string;
max_ogi_version: string | null;
python_dependencies: string[];
api_keys_required: ApiKeyRequirement[];
tags: string[];
verification_tier: VerificationTier;
bundled: boolean;
download_url: string;
readme_url: string;
sha256: string;
permissions: TransformPermissions;
popularity: TransformPopularity;
icon: string;
color: string;
created_at: string;
updated_at: string;
}

interface RegistryIndex {
version: number;
generated_at: string;
repo: string;
transforms: RegistryTransform[];
}

Integration Points in Existing UI

1.  Toolbar.tsx: "Plugins" button opens TransformHub instead of PluginManager
2.  Entity Inspector / Context Menu: When no transforms available for an entity type, show CTA linking to the Hub filtered by that input type
3.  Dashboard: Add "Transform Hub" link in navigation

---

9.  Implementation Sequencing

┌───────────────────────────┬───────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Phase │ Duration │ Deliverables │
├───────────────────────────┼───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Registry Repo │ 1 week │ Create opengraphintel/ogi-transforms repo, JSON schema, CI workflows, migrate built-in transforms as documentation copies, write CONTRIBUTING.md │
├───────────────────────────┼───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. Package Format v2 │ 3 days │ Extend plugin.yaml spec, update PluginEngine to parse v2 fields with v1 backward compat, extend PluginInfo model │
├───────────────────────────┼───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. CLI Tool │ 1–2 weeks │ ogi transform search/install/list/update/remove/info, registry client, installer, lock file management │
├───────────────────────────┼───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. Backend Registry API │ 1 week │ /api/v1/registry/\* endpoints, index caching/proxy, install/remove via API │
├───────────────────────────┼───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5. Frontend Transform Hub │ 1–2 weeks │ New components, registryStore, API client extensions, replace PluginManager │
├───────────────────────────┼───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6. Ratings & Discussions │ 3 days │ GitHub Discussions setup, auto-create workflow, GraphQL scraper for reaction counts │
├───────────────────────────┼───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 7. Cloud Sandbox │ 2 weeks │ SandboxRunner, Docker isolation, tier enforcement, config additions │
└───────────────────────────┴───────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Critical Existing Files to Modify

┌───────────────────────────────────────────┬──────────────────────────────────────────────────────────┐
│ File │ Changes │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ backend/ogi/engine/plugin_engine.py │ Parse v2 manifests, read lock file, support source field │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ backend/ogi/models/plugin.py │ Extend PluginInfo with v2 fields │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ backend/ogi/config.py │ Add deployment_mode, registry_repo, sandbox settings │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ backend/ogi/main.py │ Initialize registry client at startup │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ backend/ogi/api/router.py │ Include new registry router │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ backend/pyproject.toml │ Add ogi CLI entry point, add typer + httpx dependencies │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ frontend/src/api/client.ts │ Add registry API methods │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ frontend/src/components/PluginManager.tsx │ Replace with TransformHub │
├───────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ frontend/src/components/Toolbar.tsx │ Update to open TransformHub │
└───────────────────────────────────────────┴──────────────────────────────────────────────────────────┘

New Files

┌───────────────────────────────────────────┬──────────────────────────────────┐
│ File │ Purpose │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ backend/ogi/cli/main.py │ Typer CLI app │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ backend/ogi/cli/commands/transform.py │ Transform sub-commands │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ backend/ogi/cli/registry.py │ GitHub registry client │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ backend/ogi/cli/installer.py │ Download/verify/install logic │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ backend/ogi/cli/lockfile.py │ Lock file management │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ backend/ogi/api/registry.py │ Registry proxy API routes │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ backend/ogi/engine/sandbox_runner.py │ Cloud-mode sandboxed execution │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ frontend/src/types/registry.ts │ Registry TypeScript types │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ frontend/src/stores/registryStore.ts │ Zustand store for registry state │
├───────────────────────────────────────────┼──────────────────────────────────┤
│ frontend/src/components/marketplace/\*.tsx │ TransformHub UI components │
└───────────────────────────────────────────┴──────────────────────────────────┘
