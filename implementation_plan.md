# Implementation Plan: Open Source Link Analysis & OSINT Framework

## Project Codename: **OpenGraph Intel (OGI)**

---

## 1. Executive Summary

This document outlines the implementation plan for an open source alternative to Maltego — a visual link analysis and OSINT (Open Source Intelligence) framework. The project aims to deliver a modular, extensible platform that enables security researchers, investigators, and analysts to discover relationships between entities (people, organizations, domains, IPs, etc.) through automated data gathering ("transforms") and interactive graph visualization.

---

## 2. Project Vision & Goals

**Vision:** A community-driven, fully open source intelligence platform that democratizes link analysis and OSINT capabilities.

**Core Goals:**

- Provide a rich, interactive graph-based UI for entity relationship exploration
- Support a pluggable transform architecture for automated data enrichment
- Enable community-contributed transform packages (similar to Maltego's "Transform Hub")
- Remain fully open source (e.g., AGPLv3 or Apache 2.0) with no feature gating
- Deliver cross-platform support (Linux, macOS, Windows)
- Support both local and collaborative (server-based) workflows

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (UI)                        │
│  ┌──────────┐ ┌────────────┐ ┌────────────────────────┐ │
│  │  Graph    │ │  Entity    │ │  Transform Runner /    │ │
│  │  Canvas   │ │  Inspector │ │  Results Panel         │ │
│  └──────────┘ └────────────┘ └────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                   API Gateway (REST + WebSocket)         │
├─────────────────────────────────────────────────────────┤
│                     Core Engine                          │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ │
│  │  Graph   │ │  Transform │ │  Entity  │ │  Session │ │
│  │  Engine  │ │  Engine    │ │  Registry│ │  Manager │ │
│  └──────────┘ └────────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────┤
│                  Transform Layer                         │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ │
│  │  Local   │ │  Remote    │ │  Custom  │ │  Plugin  │ │
│  │Transforms│ │ Transform  │ │  Scripts │ │  Manager │ │
│  │          │ │  Servers   │ │ (Py/JS)  │ │          │ │
│  └──────────┘ └────────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────┤
│                   Data Layer                             │
│  ┌──────────┐ ┌────────────┐ ┌──────────────────────┐  │
│  │  Graph   │ │  Cache /   │ │  Export / Import      │  │
│  │  Store   │ │  Rate Limit│ │  (GraphML, CSV, JSON) │  │
│  └──────────┘ └────────────┘ └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack (Recommended)

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | React + TypeScript | Large ecosystem, component-based architecture |
| **Graph Rendering** | Cytoscape.js or Sigma.js | Mature graph viz libraries with layout algorithms |
| **Backend API** | Python (FastAPI) | Fast async framework, strong OSINT ecosystem |
| **Transform Runtime** | Python (primary), JS (secondary) | Python dominates the OSINT tooling space |
| **Graph Database** | Neo4j (optional) or SQLite + in-memory graph | Neo4j for large-scale; SQLite for lightweight local use |
| **Message Queue** | Redis or RabbitMQ | For async transform execution |
| **Desktop Wrapper** | Electron or Tauri | Cross-platform desktop app |
| **Packaging** | Docker, pip, npm | Easy deployment and development |

---

## 5. Core Components — Detailed Design

### 5.1 Entity System

Entities are the fundamental data objects placed on the graph.

**Base Entity Schema:**
```python
class Entity:
    id: UUID
    type: str            # e.g., "Person", "Domain", "IPAddress", "EmailAddress"
    value: str           # Primary display value
    properties: dict     # Arbitrary key-value metadata
    icon: str            # Icon identifier or URL
    weight: int          # Importance/relevance weight
    notes: str           # Analyst notes
    tags: list[str]      # User-defined tags
    source: str          # Origin transform or manual
    created_at: datetime
    updated_at: datetime
```

**Built-in Entity Types (v1.0):**

- Person (name, aliases, DOB, nationality)
- Organization / Company
- Domain
- DNS Name
- IP Address (v4/v6)
- Email Address
- Phone Number
- Social Media Account
- URL / Website
- Document / File
- Location (lat/long, address)
- Hash (MD5, SHA1, SHA256)
- AS Number
- SSL Certificate
- Cryptocurrency Wallet
- CVE / Vulnerability

**Custom Entity Registration:**
Users and plugin authors can register new entity types via a YAML/JSON schema:
```yaml
entity:
  name: "ThreatActor"
  category: "Threat Intelligence"
  icon: "threat_actor.svg"
  properties:
    - name: "aliases"
      type: "list[str]"
    - name: "motivation"
      type: "str"
    - name: "first_seen"
      type: "date"
```

### 5.2 Transform System

Transforms are the automated data enrichment functions — the core intelligence engine.

**Transform Interface:**
```python
class BaseTransform(ABC):
    """Base class for all transforms."""
    
    # Metadata
    display_name: str
    description: str
    input_entity_types: list[str]   # Entity types this transform accepts
    output_entity_types: list[str]  # Entity types this transform produces
    author: str
    version: str
    category: str                   # e.g., "DNS", "Social Media", "OSINT"
    
    @abstractmethod
    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        """Execute the transform on a given entity."""
        pass
    
    def get_settings(self) -> list[TransformSetting]:
        """Return configurable settings (API keys, options)."""
        return []
```

**Transform Result:**
```python
class TransformResult:
    entities: list[Entity]       # New entities discovered
    edges: list[Edge]            # Relationships between entities
    messages: list[str]          # Info/warning/error messages
    ui_messages: list[str]       # Messages to display in the UI
```

**Transform Execution Modes:**

1. **Local transforms** — run in-process (Python functions)
2. **Remote transforms** — call external Transform Distribution Servers (TDS) via HTTP
3. **Script transforms** — execute standalone scripts (Python, Bash, JS)
4. **Container transforms** — run in isolated Docker containers for security

**Transform Hub / Registry:**
A community registry (similar to PyPI or npm) where authors publish transforms:

```
ogi install-transform ogi-dns-transforms
ogi install-transform ogi-shodan
ogi install-transform ogi-social-media
```

### 5.3 Graph Engine

**Responsibilities:**
- Manage the in-memory graph structure (nodes + edges)
- Handle layout algorithms (force-directed, hierarchical, circular, organic)
- Support graph operations: merge, group, filter, shortest path, clustering
- Maintain undo/redo history

**Edge (Link) Schema:**
```python
class Edge:
    id: UUID
    source_id: UUID         # Source entity
    target_id: UUID         # Target entity
    label: str              # Relationship type (e.g., "resolves_to", "owns", "works_at")
    weight: float           # Relationship strength
    properties: dict        # Additional metadata
    bidirectional: bool     # Directed vs undirected
    source_transform: str   # Which transform created this edge
```

**Built-in Graph Algorithms:**
- Shortest path (Dijkstra / BFS)
- Centrality analysis (betweenness, degree, closeness)
- Community detection (Louvain, label propagation)
- Connected components
- PageRank
- Subgraph extraction

### 5.4 Frontend / UI

**Key UI Panels:**

1. **Graph Canvas** — interactive graph with zoom, pan, drag, selection
2. **Entity Palette** — drag-and-drop entity types onto the canvas
3. **Entity Detail Inspector** — view/edit properties of the selected entity
4. **Transform Runner** — select and run transforms, view progress
5. **Transform Output Panel** — preview results before adding to graph
6. **Search / Filter Bar** — filter graph by entity type, property, tag
7. **Timeline View** — display entities along a temporal axis
8. **Table / List View** — tabular view of all entities and properties
9. **Notebook / Notes Panel** — attach analyst notes to entities or the session

**Graph Interaction Features:**
- Right-click context menu → "Run Transform" on selected entity
- Multi-select → run transforms on multiple entities in batch
- Bookmarking / pinning entities
- Grouping entities into named collections
- Expand / collapse entity neighborhoods
- Link analysis path highlighting
- Export selected subgraph

### 5.5 Session & Project Management

- **Projects** — top-level container for an investigation
- **Sessions/Graphs** — multiple graph views within a project
- **Snapshots** — save and restore graph state at any point
- **Collaboration** — multi-user support with WebSocket-based real-time sync (Phase 3)

---

## 6. Built-in Transform Packages (v1.0)

| Package | Transforms | Data Sources |
|---|---|---|
| **DNS & Infrastructure** | DNS lookup, reverse DNS, WHOIS, subdomain enumeration, zone transfer, MX/NS/TXT records | Public DNS, WHOIS databases |
| **IP Intelligence** | Geolocation, ASN lookup, port scan summary, reverse IP | MaxMind, RDAP, Shodan (API key) |
| **Web / URL** | Screenshot, technology detection, robots.txt, sitemap parsing, link extraction | Direct HTTP requests |
| **Email** | Email to domain, email verification, breach lookup, email header analysis | HIBP API, DNS |
| **Social Media** | Username search, profile scraping, social connections | Public APIs and scraping |
| **Search Engines** | Google dorking, Bing search, cached page retrieval | Search APIs |
| **Threat Intelligence** | VirusTotal lookup, AbuseIPDB, OTX AlienVault, MITRE ATT&CK mapping | Public TI APIs |
| **File / Hash** | Hash lookup, malware analysis summary, file metadata extraction | VirusTotal, MalwareBazaar |
| **Certificate** | SSL cert details, cert chain, crt.sh transparency log search | crt.sh, Censys |
| **Cryptocurrency** | Wallet balance, transaction history, cluster analysis | Blockchain APIs |

---

## 7. Implementation Phases

### Phase 1: Foundation (Months 1–3)

**Goal:** Core engine with basic UI and a handful of transforms.

| Week | Milestone | Deliverables |
|---|---|---|
| 1–2 | Project setup | Monorepo structure, CI/CD pipeline, contribution guidelines, license selection |
| 3–4 | Entity system | Base entity model, built-in entity types, entity registry, YAML schema loader |
| 5–6 | Transform engine | Base transform interface, local transform runner, async execution, settings/config |
| 7–8 | Graph engine | In-memory graph model, add/remove/merge operations, basic layout algorithms |
| 9–10 | Basic UI | React app scaffold, graph canvas (Cytoscape.js), entity palette, detail inspector |
| 11–12 | First transforms | DNS transforms (5–8), IP geolocation, WHOIS, email-to-domain |
| 12 | **Alpha Release** | Functional local app with basic transforms and graph visualization |

### Phase 2: Enrichment (Months 4–6)

**Goal:** Full-featured UI, extensive transform library, import/export.

| Week | Milestone | Deliverables |
|---|---|---|
| 13–14 | Transform Hub | CLI tool for installing transforms, package format spec, local registry |
| 15–16 | Advanced UI | Search/filter, table view, right-click context menus, undo/redo, multi-select |
| 17–18 | More transforms | Social media, web analysis, threat intelligence, certificate, search engine transforms |
| 19–20 | Import / Export | GraphML, CSV, JSON, Maltego MTGX import, PDF/PNG graph export |
| 21–22 | Graph analysis | Shortest path, centrality, community detection, link analysis tools |
| 23–24 | Desktop packaging | Electron/Tauri wrapper, auto-update, system tray, cross-platform builds |
| 24 | **Beta Release** | Full-featured desktop app with 30+ transforms and graph analysis |

### Phase 3: Scale & Collaborate (Months 7–9)

**Goal:** Server mode, multi-user collaboration, plugin marketplace.

| Week | Milestone | Deliverables |
|---|---|---|
| 25–27 | Server mode | Backend API server, user authentication, project sharing, PostgreSQL/Neo4j persistence |
| 28–30 | Real-time collaboration | WebSocket sync, conflict resolution, user cursors, shared graph editing |
| 31–33 | Transform Distribution Server | Remote TDS protocol, public TDS hosting, transform sandboxing |
| 34–36 | Plugin ecosystem | Online transform registry/marketplace, ratings, automated security scanning |
| 36 | **v1.0 Stable Release** | Production-ready platform with collaboration features |

### Phase 4: Advanced Features (Months 10–12+)

**Goal:** Advanced intelligence capabilities and enterprise features.

- **Timeline analysis** — temporal visualization of entity relationships
- **Geospatial view** — plot entities with location data on a map
- **Machine learning integration** — entity resolution, anomaly detection, pattern recognition
- **Report generation** — automated investigation report builder
- **API / headless mode** — scriptable graph operations without UI
- **Notebook integration** — Jupyter notebook bridge for custom analysis
- **Mobile companion app** — view and annotate graphs on mobile
- **RBAC & audit logging** — enterprise access control and compliance

---

## 8. Data Model — Database Schema

### Graph Storage (SQLite for local, PostgreSQL for server)

```sql
-- Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    owner_id UUID REFERENCES users(id)
);

-- Entities (Nodes)
CREATE TABLE entities (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    properties JSONB,
    icon TEXT,
    weight INTEGER DEFAULT 1,
    notes TEXT,
    tags TEXT[],
    source TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Edges (Links)
CREATE TABLE edges (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    source_entity_id UUID REFERENCES entities(id),
    target_entity_id UUID REFERENCES entities(id),
    label TEXT NOT NULL,
    weight FLOAT DEFAULT 1.0,
    properties JSONB,
    bidirectional BOOLEAN DEFAULT FALSE,
    source_transform TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Transform Results (Audit Trail)
CREATE TABLE transform_runs (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    transform_name TEXT NOT NULL,
    input_entity_id UUID REFERENCES entities(id),
    status TEXT,  -- 'running', 'completed', 'failed'
    result_summary JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Graph Snapshots
CREATE TABLE snapshots (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    name TEXT,
    graph_state JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 9. API Specification (Key Endpoints)

```
# Projects
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{id}

# Entities
POST   /api/v1/projects/{id}/entities
GET    /api/v1/projects/{id}/entities
PATCH  /api/v1/projects/{id}/entities/{entity_id}
DELETE /api/v1/projects/{id}/entities/{entity_id}

# Edges
POST   /api/v1/projects/{id}/edges
GET    /api/v1/projects/{id}/edges
DELETE /api/v1/projects/{id}/edges/{edge_id}

# Transforms
GET    /api/v1/transforms                          # List available transforms
GET    /api/v1/transforms/{name}/settings           # Get transform settings schema
POST   /api/v1/transforms/{name}/run                # Execute a transform
GET    /api/v1/transforms/runs/{run_id}             # Get transform run status

# Graph Operations
POST   /api/v1/projects/{id}/graph/layout           # Run layout algorithm
POST   /api/v1/projects/{id}/graph/analyze           # Run graph analysis
POST   /api/v1/projects/{id}/graph/export            # Export graph
POST   /api/v1/projects/{id}/graph/import            # Import graph

# WebSocket
WS     /ws/v1/projects/{id}/sync                     # Real-time collaboration
```

---

## 10. Transform SDK — Developer Guide Outline

```python
# Example: Creating a custom transform

from ogi_sdk import BaseTransform, Entity, Edge, TransformResult

class DomainToIP(BaseTransform):
    display_name = "Domain to IP Address"
    description = "Resolves a domain name to its IP addresses"
    input_entity_types = ["Domain"]
    output_entity_types = ["IPAddress"]
    category = "DNS"
    
    async def run(self, entity, config):
        import socket
        result = TransformResult()
        
        try:
            ips = socket.getaddrinfo(entity.value, None)
            seen = set()
            for ip_info in ips:
                ip = ip_info[4][0]
                if ip not in seen:
                    seen.add(ip)
                    ip_entity = Entity(
                        type="IPAddress",
                        value=ip,
                        properties={"resolved_from": entity.value}
                    )
                    result.entities.append(ip_entity)
                    result.edges.append(Edge(
                        source_id=entity.id,
                        target_id=ip_entity.id,
                        label="resolves_to"
                    ))
        except socket.gaierror as e:
            result.messages.append(f"DNS resolution failed: {e}")
        
        return result
```

**Transform Package Structure:**
```
ogi-dns-transforms/
├── ogi_transform.yaml        # Package metadata
├── transforms/
│   ├── __init__.py
│   ├── domain_to_ip.py
│   ├── domain_to_mx.py
│   ├── domain_to_ns.py
│   ├── ip_to_domain.py
│   └── whois_lookup.py
├── entities/
│   └── custom_entities.yaml   # Any custom entity types
├── icons/
│   └── dns.svg
├── tests/
│   ├── test_domain_to_ip.py
│   └── fixtures/
├── requirements.txt
└── README.md
```

---

## 11. Security Considerations

- **Transform Sandboxing** — run untrusted transforms in isolated containers with limited network and filesystem access
- **API Key Management** — encrypted local vault for storing third-party API keys (e.g., Shodan, VirusTotal); never transmitted to the OGI project
- **Rate Limiting** — per-API-source rate limiting to prevent abuse and account bans
- **Data Sensitivity** — all investigation data stored locally by default; optional encrypted storage
- **Input Validation** — strict validation on all entity properties and transform inputs to prevent injection attacks
- **Dependency Scanning** — automated CVE scanning on all transform packages in the registry
- **RBAC (Server Mode)** — role-based access control for collaborative deployments (admin, analyst, viewer)

---

## 12. Community & Contribution Strategy

- **License:** AGPLv3 (strong copyleft to keep derivatives open) or Apache 2.0 (permissive, broader adoption)
- **Contribution Model:** Fork → Branch → PR with code review; CLA for significant contributions
- **Transform Bounties:** Incentivize community transform development via bounty programs
- **Documentation:** Comprehensive docs site with guides for users, transform developers, and core contributors
- **Governance:** Initial benevolent dictator model → transition to a steering committee once community grows
- **Community Channels:** GitHub Discussions, Discord server, monthly community calls

---

## 13. Comparable / Related Open Source Projects

| Project | Relationship | Notes |
|---|---|---|
| **SpiderFoot** | Complementary / inspiration | Python-based OSINT automation — lacks rich graph UI |
| **TheHive / Cortex** | Complementary | Incident response + analyzers — can be integrated as transform source |
| **Gephi** | Inspiration (graph viz) | Powerful graph analysis but not OSINT-focused |
| **Recon-ng** | Complementary | CLI-based recon framework — transforms could wrap recon-ng modules |
| **OSRFramework** | Complementary | Username enumeration toolset |
| **Obsidian (graph view)** | UI inspiration | Beautiful graph rendering in a knowledge tool |

---

## 14. Success Metrics

| Metric | 6-Month Target | 12-Month Target |
|---|---|---|
| GitHub Stars | 1,000 | 5,000 |
| Active Contributors | 15 | 50 |
| Published Transforms | 30 | 100+ |
| Monthly Active Users (estimated) | 500 | 5,000 |
| Community Transform Packages | 5 | 25 |

---

## 15. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Third-party API changes/deprecation | High | Medium | Abstraction layer; community-maintained adapters |
| Low contributor engagement | Medium | High | Good docs, easy onboarding, bounty programs |
| Legal issues (scraping, OSINT ethics) | Medium | High | Clear usage policies, ethical guidelines, responsible disclosure |
| Performance with large graphs (10K+ nodes) | Medium | Medium | Lazy rendering, pagination, WebGL canvas option |
| Feature creep / scope bloat | Medium | Medium | Strict phase gating, MVP focus, community voting on features |

---

## 16. Estimated Resource Requirements

| Role | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| Core Backend Developer | 2 | 2 | 2 | 1 |
| Frontend Developer | 1 | 2 | 2 | 1 |
| Transform Developer / OSINT Specialist | 1 | 2 | 1 | 1 |
| DevOps / Infrastructure | 0.5 | 0.5 | 1 | 0.5 |
| Technical Writer / Docs | 0.5 | 0.5 | 1 | 0.5 |
| Community Manager | 0 | 0.5 | 1 | 1 |

---

## 17. Quick Start Roadmap

```
Month 1:  Repo setup → Entity system → Transform interface
Month 2:  Graph engine → Basic UI canvas → First 5 DNS transforms
Month 3:  Alpha release → Entity inspector → Transform runner UI
Month 4:  Transform Hub CLI → 15 more transforms → Import/Export
Month 5:  Advanced graph analysis → Desktop packaging → Table view
Month 6:  Beta release → Documentation site → Community launch
Month 7:  Server mode → User auth → PostgreSQL persistence
Month 8:  WebSocket collaboration → Shared projects
Month 9:  v1.0 stable → Transform marketplace → TDS protocol
Month 10+: Timeline view → Geo view → ML features → Report builder
```

---

*This plan is a living document. All timelines and technology choices should be validated with the core team and adjusted based on contributor availability and community feedback.*
