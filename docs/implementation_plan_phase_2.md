# OGI Phase 2 Enrichment — Implementation Plan

## Context

Phase 1 is complete: monorepo structure, FastAPI backend with 5 DNS transforms, React + Sigma.js frontend with basic graph visualization. The core loop works (create project → add entity → run transform → see results on graph).

Phase 2 transforms OGI from a functional prototype into a full-featured desktop OSINT tool with advanced graph interactions, a broad transform library, import/export, graph analysis algorithms, and Tauri desktop packaging.

**Constraints carried forward:** Sigma.js, Tauri, pnpm, Tailwind + shadcn/ui, AGPLv3, uv (Python).

---

## 0. Phase 1 Bug Fixes & Gap Fills (Pre-requisites)

Before building new features, fix the issues identified in the Phase 1 audit.

### 0.1 Backend Fixes

**Fix entity deduplication on transform re-run:**
- `EntityStore.save()` currently uses bare `INSERT` — fails with UNIQUE constraint if the same transform runs twice
- Change to `INSERT OR REPLACE` (upsert) so re-running a transform updates existing entities rather than crashing
- Add similar upsert logic for `EdgeStore.create()` — add a composite uniqueness check (`source_id + target_id + label`) to skip duplicate edges

**Fix WhoisLookup enrichment:**
- The `whois_lookup.py` transform assembles `whois_props` (creation_date, expiration_date) but only logs them as a message
- Update the transform to also set these as properties on a returned entity or include them in the result's ui_messages in a structured way
- Better: create a copy of the input domain entity with enriched properties and include it in the result

**Persist transform run history:**
- Add `transform_runs` table to the SQLite schema (migrations.py)
- Store completed TransformRun records in the DB via a new `TransformRunStore`
- Wire `GET /api/v1/transforms/runs/{run_id}` and add `GET /api/v1/projects/{project_id}/transforms/runs` to list run history per project

**Add missing CRUD endpoints:**
- `PATCH /api/v1/projects/{id}` — rename/edit project description
- `PATCH /api/v1/projects/{project_id}/edges/{edge_id}` — update edge label/weight/properties

**Fix graph engine empty-project reload:**
- Track whether a project's graph has been loaded from DB with a `_loaded` flag per project, rather than checking `if not engine.entities`
- Prevents unnecessary DB queries on legitimately empty projects

### 0.2 Frontend Fixes

**Fix panel sizes in Layout.tsx:**
- `react-resizable-panels` v4 uses percentage-based sizes, not pixels
- Change `defaultSize`/`minSize`/`maxSize` to percentage values (e.g., left: default 15%, min 8%, max 25%; right: default 20%, min 12%, max 30%)

**Add error display:**
- Create a `<Toast />` notification component (or use sonner/react-hot-toast)
- Surface store errors and API failures as dismissible toast notifications
- Display inline errors for form validation (e.g., empty entity value)

**Add loading indicators:**
- Show a spinner/skeleton in GraphCanvas while `loading` is true
- Show loading state in EntityPalette while creating an entity
- Show loading state in Toolbar while creating/switching projects

**Fix transform result flow:**
- After running a transform in `TransformPanel`, incrementally add the new entities/edges to the graphology instance instead of requiring a full graph reload
- Remove the "Reload Graph" button — replace with automatic graph update
- Remove duplicate transform execution from `EntityInspector` — keep transforms only in the bottom `TransformPanel` (or delegate from inspector to panel)

**Persist node positions:**
- Store `x`/`y` coordinates in entity properties (e.g., `_pos_x`, `_pos_y`) or in a separate localStorage cache keyed by `project_id`
- On `loadGraph`, restore positions from cache instead of randomizing
- After layout algorithms run, save new positions

**Remove dead dependencies:**
- Remove `@react-sigma/core` from package.json (unused — we use raw `Sigma`)
- Remove unused `Graph` model from `backend/ogi/models/graph.py` or start using it

---

## 1. Advanced Graph Interactions

### 1.1 Node Dragging

**File:** `frontend/src/components/GraphCanvas.tsx`

Enable drag-to-reposition nodes using Sigma's built-in event system:
- Listen to `downNode`, `mousemovebody`, `mouseup` events on the Sigma renderer
- On `downNode`: capture the node being dragged, set a `dragging` flag
- On `mousemovebody` while dragging: update the node's `x`/`y` in the graphology graph using `graph.setNodeAttribute(node, 'x', ...)` with the Sigma viewport-to-graph coordinate transform (`sigma.viewportToGraph()`)
- On `mouseup`: clear the dragging flag, persist the new position
- Prevent `clickNode` from firing after a drag (use a distance threshold)

### 1.2 Right-Click Context Menu

**New file:** `frontend/src/components/ContextMenu.tsx`

A floating context menu that appears on right-click:
- **On node right-click:** Show menu with options:
  - "Run Transform →" submenu listing applicable transforms
  - "Expand Neighbors" — load all connected entities
  - "Delete Entity"
  - "Copy Value"
  - "Edit Properties..."
  - "Add Note..."
  - Divider
  - "Select Neighbors"
  - "Hide from Graph" (visual only, doesn't delete)
- **On edge right-click:** Show menu with:
  - "Edit Label"
  - "Delete Edge"
- **On canvas right-click:** Show menu with:
  - "Add Entity →" submenu of entity types
  - "Paste" (if an entity value was copied)
  - "Fit to Screen"
  - "Run Layout →" (ForceAtlas2, Circular)

Implementation:
- Sigma fires `rightClickNode`, `rightClickEdge`, `rightClickStage` events
- Render a positioned `<div>` at the mouse coordinates with menu items
- Close on click outside or Escape key
- Use Zustand or local state in GraphCanvas to manage menu visibility/position/items

### 1.3 Multi-Select

**Updates to:** `graphStore.ts`, `GraphCanvas.tsx`, `EntityInspector.tsx`, `TransformPanel.tsx`

- Change `selectedNodeId: string | null` to `selectedNodeIds: Set<string>`
- **Shift+click** to add/remove a node from the selection
- **Ctrl+A** to select all visible nodes
- **Click empty canvas** to clear selection
- **Box select:** Hold Shift and drag on empty canvas to draw a selection rectangle; select all nodes within it
- Update `EntityInspector` to show a multi-entity summary when multiple nodes are selected (count by type, bulk actions: delete all, tag all, run transform on all)
- Update `TransformPanel` to support batch transform execution: run a transform on each selected entity sequentially, aggregating results

### 1.4 Edge Selection & Inspection

**Updates to:** `GraphCanvas.tsx`, `EntityInspector.tsx`

- Register `clickEdge` event on Sigma renderer → call `selectEdge(edgeId)` in the store
- When an edge is selected, show edge details in the Inspector panel:
  - Source entity → Target entity
  - Label (editable)
  - Weight (editable)
  - Properties (editable)
  - Source transform
  - Delete button

### 1.5 Zoom Controls

**Updates to:** `Toolbar.tsx`

Add zoom buttons to the toolbar:
- Zoom In (`sigma.getCamera().animatedZoom()`)
- Zoom Out (`sigma.getCamera().animatedUnzoom()`)
- Fit to Screen (`sigma.getCamera().animatedReset()`)
- Access the Sigma instance via a ref exposed from GraphCanvas (or a Zustand ref)

### 1.6 Keyboard Shortcuts

**New file:** `frontend/src/hooks/useKeyboardShortcuts.ts`

Global keyboard shortcuts:
- `Delete` / `Backspace` — delete selected entities/edges
- `Ctrl+A` — select all
- `Escape` — deselect all, close context menu
- `Ctrl+Z` — undo
- `Ctrl+Shift+Z` / `Ctrl+Y` — redo
- `Ctrl+F` — focus search bar
- `+` / `-` — zoom in/out
- `0` — fit to screen
- `Ctrl+N` — new project
- `Ctrl+E` — export graph

---

## 2. Undo/Redo System

### 2.1 Backend: Operation History

**New file:** `backend/ogi/engine/history.py`

```
class OperationType(str, Enum):
    ADD_ENTITY = "add_entity"
    REMOVE_ENTITY = "remove_entity"
    UPDATE_ENTITY = "update_entity"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    UPDATE_EDGE = "update_edge"

class Operation:
    type: OperationType
    data: dict          # serialized entity/edge before the change
    inverse_data: dict  # serialized entity/edge after the change (for redo)
```

- `HistoryEngine` class per project: maintains a stack of `Operation` objects
- `push(operation)` — add to undo stack, clear redo stack
- `undo()` → returns the inverse operation to apply
- `redo()` → returns the forward operation to apply
- Max history depth: 100 operations

### 2.2 Backend: Undo/Redo API

**New endpoints in** `api/graph.py`:
- `POST /api/v1/projects/{id}/undo` — undo the last operation, returns the reversed change
- `POST /api/v1/projects/{id}/redo` — redo the last undone operation

### 2.3 Frontend: Undo/Redo Integration

**New store:** `frontend/src/stores/historyStore.ts`

- Tracks local undo/redo state (canUndo, canRedo)
- On Ctrl+Z, calls the undo API endpoint and applies the change to the graph
- On Ctrl+Shift+Z, calls the redo API endpoint
- Toolbar shows undo/redo buttons with disabled state

---

## 3. Search, Filter & Table View

### 3.1 Search Bar

**New component:** `frontend/src/components/SearchBar.tsx`

A search bar that appears at the top of the graph canvas (below toolbar) or as a floating overlay:
- Text input that filters entities by value, type, notes, tags, or property values
- As the user types, matching nodes are highlighted on the graph (non-matching nodes dimmed)
- Clicking a search result selects and centers the camera on that node
- Support search syntax: `type:Domain`, `tag:important`, `source:whois_lookup`
- Clear button to remove filter and restore full graph

### 3.2 Filter Panel

**New component:** `frontend/src/components/FilterPanel.tsx`

A collapsible filter panel (in the toolbar or as a dropdown):
- Filter by entity type (checkboxes for each type, with color indicators)
- Filter by tag (multi-select)
- Filter by source/transform origin
- Filter by date range (created_at)
- "Show/Hide" toggle — filtered entities are visually hidden on the graph (not deleted)
- Filter state managed in `graphStore` with a `hiddenNodeIds: Set<string>`
- Sigma's `nodeReducer` checks `hiddenNodeIds` and returns `{ hidden: true }` for filtered nodes

### 3.3 Table View

**New component:** `frontend/src/components/TableView.tsx`

A tabular view of all entities in the current project, shown as an alternative to (or alongside) the graph:
- Sortable columns: Type, Value, Source, Weight, Created At, Tags
- Click a row to select the entity (syncs with graph selection)
- Inline editing for value, notes, tags
- Multi-select rows with checkboxes for bulk operations (delete, tag, run transform)
- Search/filter bar at the top (shared state with the graph search)
- Toggle between Graph view and Table view using tabs in the center panel

**Backend support:**
- `GET /api/v1/projects/{id}/entities?sort=value&order=asc&type=Domain&search=example` — add query parameters for server-side filtering/sorting

### 3.4 Entity Property Editor

**Updates to:** `EntityInspector.tsx`

Make the inspector's properties section editable:
- Each property key/value pair gets inline edit inputs
- "Add Property" button to add new key/value pairs
- "Remove" button (×) next to each property
- Notes field becomes a textarea
- Tags become editable chips with an "Add Tag" input
- All changes call `PATCH /api/v1/projects/{id}/entities/{entity_id}` on blur/submit

---

## 4. Import / Export

### 4.1 Backend: Export Endpoints

**New file:** `backend/ogi/api/export.py`

- `GET /api/v1/projects/{id}/export/json` — full project export as OGI JSON format (entities + edges + project metadata)
- `GET /api/v1/projects/{id}/export/csv` — entities as CSV + edges as CSV (zip file)
- `GET /api/v1/projects/{id}/export/graphml` — standard GraphML XML format (compatible with Gephi, yEd, etc.)

**OGI JSON format:**
```json
{
  "version": "1.0",
  "project": { "name": "...", "description": "..." },
  "entities": [ { "id": "...", "type": "...", "value": "...", ... } ],
  "edges": [ { "id": "...", "source_id": "...", "target_id": "...", ... } ]
}
```

**GraphML export:**
- Map entity types, values, properties to GraphML node attributes
- Map edge labels, weights to GraphML edge attributes
- Include OGI-specific metadata as GraphML `<data>` elements with a custom namespace

**CSV export:**
- `entities.csv`: id, type, value, properties (JSON string), weight, notes, tags (comma-separated), source, created_at
- `edges.csv`: id, source_id, target_id, label, weight, source_transform, created_at

### 4.2 Backend: Import Endpoints

**New file:** `backend/ogi/api/import_.py`

- `POST /api/v1/projects/{id}/import/json` — import OGI JSON format into existing project
- `POST /api/v1/projects/{id}/import/csv` — import entities CSV + edges CSV
- `POST /api/v1/projects/{id}/import/graphml` — import GraphML file
- `POST /api/v1/projects/{id}/import/maltego` — import Maltego `.mtgx` files (MTGX is a zip containing XML graph data)

Import behavior:
- Entities are matched by `type + value` to avoid duplicates (merge properties if duplicate found)
- New entities get new UUIDs
- Edge references are remapped from import IDs to new UUIDs
- Returns a summary: entities added/merged/skipped, edges added/skipped

**Maltego MTGX import** (`backend/ogi/transforms/importers/maltego.py`):
- Parse the MTGX zip → extract `Graphs/Graph1.graphml`
- Map Maltego entity types to OGI entity types (e.g., `maltego.Domain` → `Domain`)
- Map Maltego link labels to OGI edge labels
- Preserve Maltego entity properties as OGI properties

### 4.3 Frontend: Export/Import UI

**New component:** `frontend/src/components/ExportImportDialog.tsx`

- Modal dialog accessible from Toolbar "Export" / "Import" buttons
- **Export tab:**
  - Format selector: OGI JSON, GraphML, CSV
  - "Export All" or "Export Selected" (if nodes are selected)
  - Download triggers a file save dialog
  - PNG/SVG graph screenshot: capture the Sigma canvas via `sigma.getCanvasDataURL()` or `sigma.getGraphImage()`
- **Import tab:**
  - File upload dropzone
  - Auto-detect format from file extension
  - Preview: show count of entities/edges to be imported
  - "Import" button → calls backend, then reloads graph

### 4.4 Backend: Graph Screenshot

- `GET /api/v1/projects/{id}/export/png` — not practical server-side (Sigma runs in browser)
- Instead, implement PNG/SVG export purely in the frontend using Sigma's canvas export API
- `sigma.getCanvasDataURL("image/png")` → create a download link

---

## 5. Graph Analysis Algorithms

### 5.1 Backend: Analysis Engine

**New file:** `backend/ogi/engine/analysis.py`

Implement the following algorithms operating on the `GraphEngine`'s in-memory graph:

**Centrality Measures:**
- `degree_centrality(project_id)` — node degree / (n-1). Returns dict of entity_id → score
- `betweenness_centrality(project_id)` — fraction of shortest paths passing through each node (Brandes' algorithm)
- `closeness_centrality(project_id)` — inverse of average shortest path length to all other nodes

**Community Detection:**
- `connected_components(project_id)` — returns list of sets of entity IDs
- `louvain_communities(project_id)` — Louvain modularity-based community detection. Returns list of sets of entity IDs. Use a pure-Python implementation or port the algorithm.

**Other:**
- `pagerank(project_id, damping=0.85, iterations=100)` — PageRank scores for all nodes
- `shortest_path(project_id, source_id, target_id)` — already exists as `find_paths` in GraphEngine, expose via API
- `graph_stats(project_id)` — returns entity count, edge count, density, avg degree, connected component count, diameter

### 5.2 Backend: Analysis API

**New endpoints in** `api/graph.py`:
- `POST /api/v1/projects/{id}/graph/analyze` — body: `{ "algorithm": "degree_centrality" | "betweenness_centrality" | ... }` → returns results as `{ "scores": { "entity_id": score } }` or `{ "communities": [["id1", "id2"], ...] }`
- `GET /api/v1/projects/{id}/graph/stats` — returns graph statistics

### 5.3 Frontend: Analysis UI

**New component:** `frontend/src/components/AnalysisPanel.tsx`

A panel (tab in the bottom section alongside TransformPanel) for running graph analysis:
- Dropdown to select algorithm
- "Run" button
- Results display:
  - **Centrality:** Resize nodes by centrality score (higher score = bigger node). Show a ranked list of top entities.
  - **Communities:** Color nodes by community. Show a legend mapping colors to community IDs.
  - **Shortest Path:** Highlight the path on the graph (colored edges + nodes). Show the path as a breadcrumb list.
  - **Stats:** Show a summary card with graph metrics.
- "Reset" button to restore original node sizes/colors

---

## 6. Additional Transforms

### 6.1 Transform Package Structure

Organize transforms into category directories under `backend/ogi/transforms/`:

```
backend/ogi/transforms/
├── base.py
├── dns/                    # Phase 1 (existing)
│   ├── domain_to_ip.py
│   ├── domain_to_mx.py
│   ├── domain_to_ns.py
│   ├── ip_to_domain.py
│   └── whois_lookup.py
├── ip/                     # Phase 2
│   ├── ip_to_geolocation.py
│   └── ip_to_asn.py
├── web/                    # Phase 2
│   ├── url_to_links.py
│   ├── domain_to_urls.py
│   └── url_to_headers.py
├── email/                  # Phase 2
│   ├── email_to_domain.py
│   └── domain_to_emails.py
├── cert/                   # Phase 2
│   ├── domain_to_certs.py
│   └── cert_transparency.py
├── hash/                   # Phase 2
│   └── hash_lookup.py
└── social/                 # Phase 2
    └── username_search.py
```

### 6.2 New Entity Types

Add to `EntityType` enum and `ENTITY_TYPE_META`:
- `SSLCertificate` — icon: "shield", color: "#10b981", category: "Infrastructure"
- `Subdomain` — icon: "globe", color: "#06b6d4", category: "Infrastructure"
- `HTTPHeader` — icon: "file-code", color: "#8b5cf6", category: "Forensics"

### 6.3 IP Intelligence Transforms

**`ip/ip_to_geolocation.py` — IP to Geolocation**
- Input: IPAddress → Output: Location
- Use a free GeoIP database (ip-api.com free tier, or bundled GeoLite2 if MaxMind key configured)
- Creates a Location entity with properties: country, city, region, latitude, longitude, ISP, org
- Edge label: "located in"
- New dependency: `geoip2` (optional, for MaxMind) or use `httpx` to query ip-api.com

**`ip/ip_to_asn.py` — IP to ASN**
- Input: IPAddress → Output: ASNumber, Organization
- Use Team Cymru ASN lookup via DNS (TXT query on `{reversed_ip}.origin.asn.cymru.com`)
- Creates ASNumber entity (e.g., "AS13335") and Organization entity (e.g., "Cloudflare, Inc.")
- Edge labels: "belongs to ASN", "operated by"

### 6.4 Web/URL Transforms

**`web/url_to_links.py` — URL to Outbound Links**
- Input: URL → Output: URL, Domain
- Fetch the URL, parse HTML, extract all `<a href>` links
- Creates URL entities for each unique outbound link
- Creates Domain entities for unique domains found
- Edge label: "links to"
- New dependency: `beautifulsoup4`, `httpx`

**`web/domain_to_urls.py` — Domain to URLs (robots.txt / sitemap)**
- Input: Domain → Output: URL
- Fetch `robots.txt` and `sitemap.xml` for the domain
- Extract all URLs from sitemap entries and robots.txt paths
- Edge label: "hosts"

**`web/url_to_headers.py` — URL to HTTP Headers**
- Input: URL → Output: enriched properties on the URL entity
- Perform HEAD request, capture response headers (Server, X-Powered-By, Content-Type, etc.)
- Store headers as properties on the URL entity
- If `Server` header found, add it as a message (e.g., "Server: nginx/1.19")

### 6.5 Email Transforms

**`email/email_to_domain.py` — Email to Domain**
- Input: EmailAddress → Output: Domain
- Extract the domain portion from the email address
- Create a Domain entity
- Edge label: "email hosted at"

**`email/domain_to_emails.py` — Domain to Emails (from WHOIS + MX heuristics)**
- Input: Domain → Output: EmailAddress
- Check common email patterns: admin@, info@, postmaster@, hostmaster@, webmaster@, abuse@
- Verify via MX record existence (if MX exists, emails are plausible)
- Edge label: "email at"

### 6.6 Certificate Transforms

**`cert/domain_to_certs.py` — Domain to SSL Certificate**
- Input: Domain → Output: SSLCertificate, Organization
- Connect to the domain on port 443, retrieve the SSL certificate
- Create SSLCertificate entity with properties: issuer, subject, serial, not_before, not_after, SANs
- If the issuer org is identified, create an Organization entity
- Edge labels: "secured by", "issued by"
- New dependency: `ssl` (stdlib), `cryptography` (for cert parsing)

**`cert/cert_transparency.py` — Domain to Subdomains (via crt.sh)**
- Input: Domain → Output: Subdomain
- Query `https://crt.sh/?q=%.{domain}&output=json` for certificate transparency logs
- Extract unique subdomain names from the results
- Create Subdomain entities for each
- Edge label: "subdomain of"
- Rate limit: max 1 request per 2 seconds to crt.sh

### 6.7 Hash Transforms

**`hash/hash_lookup.py` — Hash Lookup (VirusTotal)**
- Input: Hash → Output: enriched properties
- If VirusTotal API key is configured, query `/api/v3/files/{hash}`
- Enrich the Hash entity properties with: detection ratio, file type, file size, first_seen, last_seen
- Add messages with detection details
- Transform setting: `virustotal_api_key` (optional)

### 6.8 Social Media Transforms

**`social/username_search.py` — Username Search**
- Input: SocialMedia or Person → Output: SocialMedia, URL
- Check a list of popular platforms for username existence by HTTP HEAD requests to profile URLs:
  - GitHub: `https://github.com/{username}`
  - Twitter/X: `https://x.com/{username}`
  - Reddit: `https://www.reddit.com/user/{username}`
  - Instagram: `https://www.instagram.com/{username}`
  - LinkedIn: `https://www.linkedin.com/in/{username}`
  - Keybase: `https://keybase.io/{username}`
- For each hit (HTTP 200), create a SocialMedia entity and a URL entity
- Edge labels: "has account", "profile URL"
- Rate limit: 0.5s delay between requests to avoid bans

### 6.9 Transform Auto-Discovery Update

Update `TransformEngine.auto_discover()` to register all new transforms:
```python
def auto_discover(self) -> None:
    from ogi.transforms.dns.domain_to_ip import DomainToIP
    # ... existing DNS transforms ...
    from ogi.transforms.ip.ip_to_geolocation import IPToGeolocation
    from ogi.transforms.ip.ip_to_asn import IPToASN
    from ogi.transforms.web.url_to_links import URLToLinks
    # ... etc ...
    for cls in [DomainToIP, ..., IPToGeolocation, IPToASN, URLToLinks, ...]:
        self.register(cls())
```

### 6.10 Transform Settings UI

**Backend:** `GET /api/v1/transforms/{name}/settings` — returns the transform's `settings` list (name, display_name, description, required, default)

**New file:** `frontend/src/components/TransformSettings.tsx`
- Global settings dialog (accessible from Toolbar) for configuring API keys per transform
- Settings are stored in localStorage on the frontend and sent with each transform run via `TransformConfig.settings`
- Shows which transforms require API keys and whether they're configured

---

## 7. Tauri Desktop Packaging

### 7.1 Tauri Setup

**New directory:** `src-tauri/`

```
src-tauri/
├── Cargo.toml
├── tauri.conf.json
├── src/
│   └── main.rs
├── icons/                   # App icons (PNG, ICO, ICNS)
└── build.rs
```

- Install Tauri CLI: `pnpm add -D @tauri-apps/cli @tauri-apps/api`
- Initialize with `pnpm tauri init`
- Configure `tauri.conf.json`:
  - `build.devUrl`: `http://localhost:5173` (Vite dev server)
  - `build.frontendDist`: `../frontend/dist`
  - `app.windows[0].title`: "OGI — OpenGraph Intel"
  - `app.windows[0].width`: 1400, `height`: 900
  - `bundle.identifier`: "com.ogi.app"
  - `bundle.active`: true (enable bundling)

### 7.2 Sidecar: Bundle Python Backend

Tauri supports "sidecar" binaries — bundle the Python backend as a standalone executable:
- Use `PyInstaller` or `Nuitka` to compile the FastAPI backend into a single executable
- Configure Tauri sidecar in `tauri.conf.json` to start/stop the backend process
- The Tauri app starts the backend sidecar on launch and kills it on exit
- Frontend connects to `http://localhost:8000` (backend sidecar)

Alternative (simpler for now): Document the two-process workflow (run backend separately) and package Tauri as a frontend-only wrapper. The sidecar approach can be refined later.

### 7.3 Build Scripts

Add to root `package.json` (or create one):
```json
{
  "scripts": {
    "dev": "concurrently \"cd backend && uv run uvicorn ogi.main:app --reload\" \"cd frontend && pnpm dev\"",
    "build:frontend": "cd frontend && pnpm build",
    "build:desktop": "cd frontend && pnpm tauri build",
    "build:backend": "cd backend && pyinstaller --onefile ogi/main.py"
  }
}
```

### 7.4 Cross-Platform Builds

- Windows: `.msi` installer via Tauri's WiX integration
- macOS: `.dmg` via Tauri's bundler
- Linux: `.deb` and `.AppImage` via Tauri's bundler
- CI/CD: GitHub Actions workflow to build for all three platforms on tag push

---

## 8. UI Polish & Quality of Life

### 8.1 Onboarding / Empty States

- **No projects:** Show a welcome screen with "Create your first project" button and a brief description of OGI
- **Empty project:** Show a prompt in the graph canvas: "Add entities from the left panel or import a graph"
- **No transforms available:** Show a message explaining why (entity type has no applicable transforms)

### 8.2 Project Management

- **Delete project:** Add a delete button in the project dropdown with a confirmation dialog
- **Rename project:** Double-click the project name in the toolbar to edit inline
- **Project description:** Show in a tooltip or expandable section

### 8.3 Improved Transform Results Flow

After a transform completes:
- Automatically add discovered entities/edges to the graphology instance (already persisted by backend)
- Run a quick ForceAtlas2 pass (50 iterations) to position new nodes near the source entity
- Flash/animate new nodes briefly (pulse animation) so the user can see what was added
- Show a toast: "Domain to IP: found 3 new entities"

### 8.4 Graph Visual Improvements

- **Edge labels:** Show edge labels on hover (not always, to reduce clutter). Use Sigma's `edgeLabelRenderedSizeThreshold`
- **Node labels:** Always show labels for selected nodes and their neighbors; hide others at low zoom levels
- **Entity type icons:** Render entity type icons inside nodes instead of plain circles (use Sigma's custom node rendering or `@sigma/node-image`)
- **Minimap:** Add a small minimap in the corner of the graph canvas showing the full graph with a viewport rectangle (Sigma has no built-in minimap, but one can be rendered from the graphology data into a small canvas)

### 8.5 Toolbar Enhancements

- **Graph stats badge:** Show entity count + edge count in the toolbar
- **View toggle:** Switch between Graph view and Table view
- **Layout dropdown:** Replace individual layout buttons with a dropdown (ForceAtlas2, Circular, Random, Grid)

---

## 9. New File Manifest

### Backend — New Files
```
backend/ogi/
├── engine/
│   ├── analysis.py              # Graph analysis algorithms
│   └── history.py               # Undo/redo operation history
├── api/
│   ├── export.py                # Export endpoints (JSON, CSV, GraphML)
│   └── import_.py               # Import endpoints (JSON, CSV, GraphML, Maltego)
├── store/
│   └── transform_run_store.py   # Persistent transform run storage
├── transforms/
│   ├── ip/
│   │   ├── __init__.py
│   │   ├── ip_to_geolocation.py
│   │   └── ip_to_asn.py
│   ├── web/
│   │   ├── __init__.py
│   │   ├── url_to_links.py
│   │   ├── domain_to_urls.py
│   │   └── url_to_headers.py
│   ├── email/
│   │   ├── __init__.py
│   │   ├── email_to_domain.py
│   │   └── domain_to_emails.py
│   ├── cert/
│   │   ├── __init__.py
│   │   ├── domain_to_certs.py
│   │   └── cert_transparency.py
│   ├── hash/
│   │   ├── __init__.py
│   │   └── hash_lookup.py
│   └── social/
│       ├── __init__.py
│       └── username_search.py
└── tests/
    ├── test_analysis.py
    ├── test_history.py
    ├── test_export.py
    ├── test_import.py
    └── test_transforms_phase2.py
```

### Frontend — New Files
```
frontend/src/
├── components/
│   ├── ContextMenu.tsx          # Right-click context menu
│   ├── SearchBar.tsx            # Graph search/filter bar
│   ├── FilterPanel.tsx          # Entity type/tag filter panel
│   ├── TableView.tsx            # Tabular entity list view
│   ├── AnalysisPanel.tsx        # Graph analysis algorithm runner
│   ├── ExportImportDialog.tsx   # Export/Import modal
│   ├── TransformSettings.tsx    # Transform API key configuration
│   ├── Toast.tsx                # Toast notification system
│   └── EmptyState.tsx           # Empty state / onboarding prompts
├── stores/
│   └── historyStore.ts          # Undo/redo state
└── hooks/
    ├── useKeyboardShortcuts.ts  # Global keyboard shortcut handler
    └── useTransforms.ts         # Transform execution hook
```

### Desktop — New Files
```
src-tauri/
├── Cargo.toml
├── tauri.conf.json
├── src/
│   └── main.rs
└── icons/
```

---

## 10. New Dependencies

### Backend (add to pyproject.toml)
```
beautifulsoup4>=4.12.0     # HTML parsing for web transforms
httpx>=0.27.0              # Already in dev deps, move to main deps for web transforms
cryptography>=42.0.0       # SSL certificate parsing
geoip2>=4.8.0              # Optional: MaxMind GeoIP (if API key available)
lxml>=5.0.0                # Fast XML parsing for GraphML and Maltego import
```

### Frontend (add to package.json)
```
sonner                     # Toast notifications
@sigma/node-image          # Optional: render images inside Sigma nodes
```

### Desktop
```
@tauri-apps/cli            # Tauri CLI (devDependency)
@tauri-apps/api            # Tauri JS API
```

---

## 11. Implementation Order

### Step 1: Phase 1 bug fixes (Section 0)
- Fix entity upsert, WhoisLookup enrichment, panel sizes, error display
- Fix transform result flow (auto-add to graph, no manual reload)
- Persist node positions in localStorage

### Step 2: Advanced graph interactions (Section 1)
- Node dragging
- Right-click context menu
- Edge selection & inspection
- Zoom controls in toolbar

### Step 3: Property editing & search (Section 3)
- Make EntityInspector properties/notes/tags editable
- Search bar with graph highlighting
- Entity type filter panel

### Step 4: Undo/redo (Section 2)
- Backend history engine + API
- Frontend undo/redo store + keyboard shortcuts

### Step 5: Additional transforms (Section 6)
- IP Intelligence (geolocation, ASN)
- Email transforms (email→domain, domain→emails)
- Certificate transforms (SSL cert, crt.sh subdomains)
- Web transforms (URL links, HTTP headers, robots/sitemap)
- Social media (username search)
- Hash lookup (VirusTotal, optional)

### Step 6: Import/Export (Section 4)
- Backend export endpoints (JSON, CSV, GraphML)
- Backend import endpoints (JSON, CSV, GraphML, Maltego MTGX)
- Frontend Export/Import dialog
- PNG/SVG screenshot export from Sigma canvas

### Step 7: Graph analysis (Section 5)
- Centrality measures (degree, betweenness, closeness)
- Community detection (connected components, Louvain)
- PageRank
- Analysis panel UI with visual feedback (node sizing, community coloring)

### Step 8: Table view & multi-select (Sections 1.3, 3.3)
- Table view component with sorting/filtering
- Multi-select on graph (Shift+click, box select)
- Batch operations (delete, tag, transform)

### Step 9: Keyboard shortcuts & polish (Sections 1.6, 8)
- Global keyboard shortcut handler
- Empty states / onboarding
- Toast notifications for all operations
- Graph visual improvements (hover labels, node icons)
- Toolbar enhancements (stats badge, view toggle, layout dropdown)

### Step 10: Tauri desktop packaging (Section 7)
- Tauri project initialization
- Configure build for Windows/macOS/Linux
- Sidecar setup for Python backend
- GitHub Actions CI for cross-platform builds

---

## 12. Verification

### Per-step verification:
1. **Bug fixes:** Re-run all 27 existing tests. Manually verify: re-run same transform twice → no crash. Panel sizes look correct. Transform results auto-appear on graph.
2. **Graph interactions:** Drag a node → it stays. Right-click node → menu appears with transforms. Click edge → inspector shows edge details. Zoom buttons work.
3. **Property editing:** Select entity → edit value in inspector → value updates on graph node label. Add a tag → it persists.
4. **Undo/redo:** Add entity → Ctrl+Z → entity removed. Ctrl+Shift+Z → entity restored.
5. **Transforms:** Run each new transform on appropriate entity types. Verify entities/edges are created correctly.
6. **Import/Export:** Export project as JSON → import into new project → verify all entities/edges match. Import a Maltego .mtgx file → entities appear on graph.
7. **Graph analysis:** Run degree centrality → nodes resize proportionally. Run community detection → nodes color by community.
8. **Table view:** Switch to table → all entities visible. Sort by type. Click row → node selected on graph.
9. **Keyboard shortcuts:** Delete key removes selected. Ctrl+A selects all. Ctrl+Z undoes.
10. **Tauri:** `pnpm tauri dev` launches desktop window. App functions identically to browser version. `pnpm tauri build` produces installer.

### End-to-end scenario:
1. Launch OGI → create project "ACME Investigation"
2. Add Domain entity "acme-corp.com"
3. Right-click → Run "Domain to IP" → IP nodes appear with edges
4. Right-click IP → Run "IP to Geolocation" → Location node appears
5. Right-click domain → Run "Certificate Transparency" → subdomain nodes appear
6. Ctrl+A → select all → run graph analysis (degree centrality) → hub nodes grow larger
7. Open Table View → sort by type → verify all entities listed
8. Ctrl+F → search "acme" → matching nodes highlighted
9. Export as GraphML → open in Gephi → verify structure matches
10. Ctrl+Z several times → undo steps back through history
