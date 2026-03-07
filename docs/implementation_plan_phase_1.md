Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
OGI Phase 1 Foundation — Implementation Plan

Context

Building the OpenGraph Intel (OGI) project from scratch — an open source Maltego alternative for visual link analysis and OSINT. The repo is currently empty (just implementation_plan.md). This plan covers the full Phase 1 foundation: monorepo setup,
Python backend, React frontend with Sigma.js, and initial DNS transforms.

User choices: Sigma.js (graph viz), Tauri (desktop), pnpm (package manager), Full Phase 1 scope, shadcn/ui + Tailwind (styling), AGPLv3 (license).

---

1.  Monorepo Structure

ogi/
├── backend/ # Python FastAPI backend
│ ├── pyproject.toml
│ ├── ogi/
│ │ ├── **init**.py
│ │ ├── main.py # FastAPI app entry point
│ │ ├── config.py # App configuration
│ │ ├── models/
│ │ │ ├── **init**.py
│ │ │ ├── entity.py # Entity model + built-in types
│ │ │ ├── edge.py # Edge/link model
│ │ │ ├── graph.py # Graph container model
│ │ │ ├── project.py # Project model
│ │ │ └── transform.py # Transform result/run models
│ │ ├── engine/
│ │ │ ├── **init**.py
│ │ │ ├── graph_engine.py # In-memory graph operations
│ │ │ ├── transform_engine.py # Transform execution engine
│ │ │ └── entity_registry.py # Entity type registry
│ │ ├── api/
│ │ │ ├── **init**.py
│ │ │ ├── router.py # Main API router
│ │ │ ├── projects.py # Project endpoints
│ │ │ ├── entities.py # Entity CRUD endpoints
│ │ │ ├── edges.py # Edge CRUD endpoints
│ │ │ ├── transforms.py # Transform endpoints
│ │ │ └── graph.py # Graph operations endpoints
│ │ ├── transforms/
│ │ │ ├── **init**.py
│ │ │ ├── base.py # BaseTransform ABC
│ │ │ └── dns/
│ │ │ ├── **init**.py
│ │ │ ├── domain_to_ip.py
│ │ │ ├── domain_to_mx.py
│ │ │ ├── domain_to_ns.py
│ │ │ ├── ip_to_domain.py
│ │ │ └── whois_lookup.py
│ │ ├── db/
│ │ │ ├── **init**.py
│ │ │ ├── database.py # SQLite connection + session
│ │ │ └── migrations.py # Schema setup
│ │ └── store/
│ │ ├── **init**.py
│ │ ├── project_store.py
│ │ ├── entity_store.py
│ │ └── edge_store.py
│ ├── tests/
│ │ ├── test_models.py
│ │ ├── test_graph_engine.py
│ │ ├── test_transform_engine.py
│ │ └── test_api.py
│ └── alembic/ # Future migrations
├── frontend/ # React + TypeScript frontend
│ ├── package.json
│ ├── tsconfig.json
│ ├── vite.config.ts
│ ├── index.html
│ ├── src/
│ │ ├── main.tsx
│ │ ├── App.tsx
│ │ ├── api/
│ │ │ └── client.ts # API client for backend
│ │ ├── components/
│ │ │ ├── GraphCanvas.tsx # Sigma.js graph canvas
│ │ │ ├── EntityPalette.tsx # Drag-and-drop entity types
│ │ │ ├── EntityInspector.tsx # Selected entity details
│ │ │ ├── TransformPanel.tsx # Transform runner UI
│ │ │ ├── TransformResults.tsx # Transform results preview
│ │ │ ├── Toolbar.tsx # Top toolbar
│ │ │ └── Layout.tsx # Main app layout
│ │ ├── stores/
│ │ │ ├── graphStore.ts # Zustand store for graph state
│ │ │ └── projectStore.ts # Zustand store for project state
│ │ ├── types/
│ │ │ ├── entity.ts
│ │ │ ├── edge.ts
│ │ │ ├── graph.ts
│ │ │ ├── project.ts
│ │ │ └── transform.ts
│ │ ├── hooks/
│ │ │ ├── useGraph.ts
│ │ │ └── useTransforms.ts
│ │ └── styles/
│ │ └── globals.css
│ └── public/
│ └── icons/ # Entity type icons (SVG)
├── .gitignore
├── README.md
└── implementation_plan.md # Existing

---

2.  Backend Implementation (Python / FastAPI)

2.1 Project Setup

- pyproject.toml with dependencies: fastapi, uvicorn, pydantic, aiosqlite, python-whois, dnspython
- Python 3.11+ required

  2.2 Models (backend/ogi/models/)

entity.py — Pydantic models:

- EntityType enum with 16 built-in types (Person, Domain, IPAddress, EmailAddress, etc.)
- Entity model: id (UUID), type, value, properties (dict), icon, weight, notes, tags, source, timestamps
- EntityCreate / EntityUpdate request schemas

edge.py:

- Edge model: id, source_id, target_id, label, weight, properties, bidirectional, source_transform, timestamp

project.py:

- Project model: id, name, description, timestamps

transform.py:

- TransformResult: entities, edges, messages, ui_messages
- TransformRun: id, project_id, transform_name, input_entity_id, status, timestamps, error
- TransformInfo: display_name, description, input_types, output_types, category

  2.3 Entity Registry (backend/ogi/engine/entity_registry.py)

- Singleton registry mapping entity type names to their schemas/icons
- Pre-registers all 16 built-in entity types
- register_type() / get_type() / list_types() methods

  2.4 Graph Engine (backend/ogi/engine/graph_engine.py)

- GraphEngine class managing in-memory graph per project
- Operations: add_entity, remove_entity, add_edge, remove_edge, merge_entities
- Query: get_neighbors, find_paths (BFS), get_subgraph
- Uses a dict-based adjacency list internally
- Layout coordination (delegates to frontend for visual layout)

  2.5 Transform Engine (backend/ogi/engine/transform_engine.py)

- TransformEngine class
- Auto-discovers transforms via registry pattern
- run_transform(name, entity, config) → async execution
- Tracks run history (TransformRun records)
- Returns TransformResult with discovered entities/edges

  2.6 Base Transform (backend/ogi/transforms/base.py)

- BaseTransform ABC with metadata fields and abstract run() method
- TransformConfig for settings/API keys
- TransformSetting descriptor

  2.7 DNS Transforms (backend/ogi/transforms/dns/)

Five initial transforms using dnspython:

1.  DomainToIP — A/AAAA record resolution
2.  DomainToMX — MX record lookup
3.  DomainToNS — NS record lookup
4.  IPToDomain — Reverse DNS lookup
5.  WhoisLookup — WHOIS query returning registrant/registrar info

2.8 Data Store (backend/ogi/store/)

- SQLite via aiosqlite for persistence
- ProjectStore, EntityStore, EdgeStore — async CRUD operations
- Schema matches the SQL in the implementation plan

  2.9 API Routes (backend/ogi/api/)

REST endpoints matching the spec in implementation_plan.md:

- POST/GET /api/v1/projects — project CRUD
- POST/GET/PATCH/DELETE /api/v1/projects/{id}/entities — entity CRUD
- POST/GET/DELETE /api/v1/projects/{id}/edges — edge CRUD
- GET /api/v1/transforms — list transforms
- POST /api/v1/transforms/{name}/run — execute transform
- GET /api/v1/transforms/runs/{run_id} — run status
- CORS enabled for frontend dev server

---

3.  Frontend Implementation (React + TypeScript + Sigma.js)

3.1 Project Setup

- Vite + React + TypeScript
- pnpm as package manager
- Key dependencies: sigma, graphology, @react-sigma/core, zustand, tailwindcss, react-resizable-panels
- shadcn/ui for component primitives (Button, Dialog, DropdownMenu, Tabs, Input, ScrollArea, etc.)

  3.2 Type Definitions (frontend/src/types/)

- Mirror backend Pydantic models as TypeScript interfaces
- Entity, Edge, Project, TransformInfo, TransformResult types

  3.3 API Client (frontend/src/api/client.ts)

- Typed fetch wrapper for all backend endpoints
- Base URL configurable (defaults to http://localhost:8000)

  3.4 State Management (frontend/src/stores/)

- graphStore (Zustand): manages graphology Graph instance, selected nodes/edges, layout state
- projectStore (Zustand): current project, project list

  3.5 Components

Layout.tsx — Main app shell with resizable panels:

- Left sidebar: EntityPalette
- Center: GraphCanvas
- Right sidebar: EntityInspector
- Bottom panel: TransformPanel + TransformResults

GraphCanvas.tsx — Sigma.js graph renderer:

- Uses @react-sigma/core SigmaContainer
- Node rendering with entity type icons/colors
- Edge rendering with labels
- Click to select, right-click context menu for transforms
- Zoom/pan controls
- Drag nodes to reposition

EntityPalette.tsx — List of available entity types:

- Grouped by category
- Click to add new entity to graph (prompts for value)
- Shows icon + name for each type

EntityInspector.tsx — Detail panel for selected entity:

- Shows all properties in editable form
- Tags, notes, source info
- List of connected edges
- "Run Transform" button

TransformPanel.tsx — Transform execution:

- Lists available transforms for the selected entity type
- Run button with loading state
- Shows transform run history

TransformResults.tsx — Preview results before adding to graph:

- Table of discovered entities
- Checkbox selection
- "Add to Graph" / "Add All" buttons

Toolbar.tsx — Top bar:

- Project name / selector
- Layout algorithm buttons (force-directed, circular)
- Zoom controls
- Export button

  3.6 Styling

- shadcn/ui + Tailwind CSS — pre-built accessible components (buttons, dialogs, dropdowns, tabs, etc.) with Tailwind for custom styling
- Dark theme by default (fits OSINT/security tool aesthetic)
- Responsive panel layout with drag-to-resize (use react-resizable-panels)

---

4.  Implementation Order

Step 1: Project scaffolding

- Initialize git, .gitignore
- Create backend pyproject.toml and package structure
- Create frontend with pnpm create vite
- Install all dependencies

Step 2: Backend models + entity registry

- Implement all Pydantic models
- Implement entity type registry with 16 built-in types

Step 3: Database layer

- SQLite schema creation
- Async store implementations (project, entity, edge)

Step 4: Graph engine

- In-memory graph with adjacency list
- Core operations (add/remove/query)

Step 5: Transform system

- BaseTransform ABC
- TransformEngine with auto-discovery
- 5 DNS transforms

Step 6: API routes

- FastAPI app with all REST endpoints
- CORS configuration
- Wire up stores + engines

Step 7: Frontend types + API client

- TypeScript type definitions
- API client module

Step 8: Frontend state + components

- Zustand stores
- GraphCanvas with Sigma.js
- EntityPalette, EntityInspector
- TransformPanel, TransformResults
- Layout shell + Toolbar

Step 9: Integration + polish

- Connect frontend to backend
- Test full workflow: create project → add entity → run transform → view results on graph
- Basic error handling

---

5.  Verification

1.  Backend: Start with uvicorn ogi.main:app --reload, hit API endpoints with curl/browser
1.  Frontend: Start with pnpm dev, verify graph renders, entities can be added
1.  End-to-end: Create project → add a Domain entity → run "Domain to IP" transform → see IP entities appear on graph with edges
1.  Tests: pytest for backend unit tests (models, graph engine, transform engine)
