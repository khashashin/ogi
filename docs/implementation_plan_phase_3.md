 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 OGI Phase 3 — Supabase, Auth, Real-Time, Plugins & Docker

 Context

 Phases 1 and 2 are complete. OGI has a working FastAPI backend with SQLite (aiosqlite), 15 transforms, in-memory graph engine, undo/redo, import/export, and graph analysis. The React frontend uses Sigma.js, Zustand, and Tailwind CSS v4.

 Phase 3 transforms OGI from a local single-user tool into a collaborative, deployable platform by migrating to Supabase (PostgreSQL + Auth + Realtime + Storage), adding a directory-based plugin system for transforms, and containerizing with Docker.

 User choices: Supabase (database, auth, blob storage), directory-based plugin system, full Phase 3 scope.

 ---
 0. Supabase Integration — Replace SQLite with PostgreSQL

 0.1 New Dependencies

 Backend (pyproject.toml):
 asyncpg>=0.30.0          # Async PostgreSQL driver
 supabase>=2.0.0          # Supabase Python client (auth, storage)
 python-jose[cryptography]>=3.3.0  # JWT token validation
 pydantic-settings>=2.0.0 # Environment-based config

 Frontend (package.json):
 @supabase/supabase-js    # Supabase client (auth, realtime)

 0.2 Configuration Update

 File: backend/ogi/config.py

 Replace the current BaseModel config with pydantic-settings.BaseSettings:

 class Settings(BaseSettings):
     app_name: str = "OGI"

     # Supabase
     supabase_url: str = ""
     supabase_anon_key: str = ""
     supabase_service_role_key: str = ""  # Server-side only

     # Direct PostgreSQL (for asyncpg, bypasses Supabase REST)
     database_url: str = "postgresql://postgres:postgres@localhost:5432/ogi"

     # Plugins
     plugin_dirs: list[str] = ["plugins"]

     # Legacy SQLite fallback (for local dev without Supabase)
     database_path: str = "ogi.db"
     use_sqlite: bool = False

     cors_origins: list[str] = [...]
     host: str = "0.0.0.0"
     port: int = 8000

     model_config = SettingsConfigDict(env_file=".env", env_prefix="OGI_")

 0.3 Database Layer — asyncpg Pool

 File: backend/ogi/db/database.py (rewrite)

 Replace the aiosqlite.Connection singleton with an asyncpg.Pool:

 - create_pool() → creates a connection pool from settings.database_url
 - get_pool() → returns the pool singleton
 - close_pool() → drains and closes the pool
 - Keep aiosqlite path behind settings.use_sqlite for offline/local dev

 0.4 PostgreSQL Schema

 File: backend/ogi/db/migrations.py (rewrite)

 Convert all SQLite-specific SQL to PostgreSQL:
 - TEXT primary keys → UUID using gen_random_uuid()
 - JSON columns → JSONB
 - TEXT[] for tags
 - Add owner_id UUID REFERENCES profiles(id) to projects
 - Add profiles table (synced with Supabase Auth auth.users)
 - Add project_members table for sharing (project_id, user_id, role)
 - Add plugins table for installed plugin metadata
 - Add api_keys table for encrypted per-user transform API keys
 - Add proper indexes, constraints, and ON DELETE CASCADE

 New tables:

 CREATE TABLE profiles (
     id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
     display_name TEXT,
     avatar_url TEXT,
     created_at TIMESTAMPTZ DEFAULT now()
 );

 CREATE TABLE project_members (
     project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
     user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
     role TEXT NOT NULL DEFAULT 'viewer',  -- 'owner', 'editor', 'viewer'
     PRIMARY KEY (project_id, user_id)
 );

 CREATE TABLE plugins (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     name TEXT UNIQUE NOT NULL,
     version TEXT,
     description TEXT,
     author TEXT,
     enabled BOOLEAN DEFAULT true,
     installed_at TIMESTAMPTZ DEFAULT now()
 );

 CREATE TABLE api_keys (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
     service_name TEXT NOT NULL,
     encrypted_key TEXT NOT NULL,
     created_at TIMESTAMPTZ DEFAULT now(),
     UNIQUE(user_id, service_name)
 );

 Row Level Security (RLS):
 - projects: users can only see projects they own or are members of
 - entities / edges / transform_runs: inherit access from their project
 - profiles: users can read all profiles, update only their own
 - api_keys: users can only read/write their own keys

 0.5 Store Layer Migration

 Files: backend/ogi/store/project_store.py, entity_store.py, edge_store.py, transform_run_store.py

 Refactor each store to accept an asyncpg.Pool instead of aiosqlite.Connection:
 - Replace ? param placeholders with $1, $2, ... (PostgreSQL paramstyle)
 - Replace aiosqlite.Row dict access with asyncpg.Record attribute access
 - Replace json.dumps/loads with native JSONB handling (asyncpg handles dicts natively)
 - Replace INSERT OR REPLACE with INSERT ... ON CONFLICT ... DO UPDATE
 - Add user_id parameter to project queries for RLS enforcement
 - Keep a SqliteEntityStore / AsyncpgEntityStore pattern or use a protocol/ABC if dual-mode is desired

 0.6 Startup Changes

 File: backend/ogi/main.py

 Update the lifespan context manager:
 - Create asyncpg pool instead of aiosqlite connection
 - Run PostgreSQL migrations (apply schema via pool)
 - Pass pool to all store constructors
 - Initialize Supabase client for storage operations

 ---
 1. Authentication — Supabase Auth + JWT

 1.1 Auth Flow

 Use Supabase Auth with JWT tokens:
 - Frontend uses @supabase/supabase-js for login/signup UI
 - Supabase issues JWTs on successful auth
 - Frontend sends JWT as Authorization: Bearer <token> header
 - Backend validates JWT using Supabase's JWT secret (HMAC) or JWKS endpoint
 - Extract user_id from the JWT sub claim

 1.2 Backend Auth Middleware

 New file: backend/ogi/api/auth.py

 async def get_current_user(request: Request) -> UserProfile:
     """FastAPI dependency that extracts and validates the JWT."""
     token = request.headers.get("Authorization", "").removeprefix("Bearer ")
     payload = decode_jwt(token, settings.supabase_jwt_secret)
     user_id = UUID(payload["sub"])
     return UserProfile(id=user_id, email=payload.get("email", ""))

 - get_current_user is a FastAPI Depends() injection
 - Returns UserProfile with id, email, display_name
 - Raises HTTPException(401) on invalid/expired token
 - Optional: make auth optional with get_optional_user for public endpoints

 1.3 Protect API Endpoints

 Add current_user: UserProfile = Depends(get_current_user) to all route handlers:
 - projects.py: filter projects by membership, enforce owner/editor roles on mutations
 - entities.py, edges.py: verify user has access to the project before any CRUD
 - transforms.py: verify project access, inject user's API keys from api_keys table
 - graph.py: verify project access

 1.4 Frontend Auth

 New files:
 - frontend/src/lib/supabase.ts — initialize Supabase client with URL + anon key
 - frontend/src/stores/authStore.ts — Zustand store for auth state (user, session, loading)
 - frontend/src/components/AuthPage.tsx — login/signup page with email + password (or magic link)
 - frontend/src/components/AuthGuard.tsx — wrapper that redirects to auth page if not logged in

 Auth store actions:
 - signIn(email, password) → Supabase auth.signInWithPassword()
 - signUp(email, password) → Supabase auth.signUp()
 - signOut() → Supabase auth.signOut()
 - onAuthStateChange() → listen for session changes, update store

 API client update (frontend/src/api/client.ts):
 - Add auth header to all requests: Authorization: Bearer ${session.access_token}
 - Handle 401 responses by redirecting to auth page
 - Auto-refresh tokens using Supabase's built-in session management

 1.5 Project Sharing UI

 New component: frontend/src/components/ShareDialog.tsx

 - Invite users by email to a project
 - Role selector: Owner / Editor / Viewer
 - List current members with ability to change role or remove
 - Backend endpoints:
   - POST /api/v1/projects/{id}/members — invite user
   - GET /api/v1/projects/{id}/members — list members
   - PATCH /api/v1/projects/{id}/members/{user_id} — change role
   - DELETE /api/v1/projects/{id}/members/{user_id} — remove member

 ---
 2. Real-Time Collaboration — Supabase Realtime

 2.1 Architecture

 Use Supabase Realtime channels for live graph synchronization:
 - Each project gets a Realtime channel: project:{project_id}
 - When any user adds/removes/updates an entity or edge, the change is broadcast to all connected users
 - Other users' frontends receive the event and apply the change to their local Graphology graph

 2.2 Backend: Broadcast Changes

 File: backend/ogi/api/entities.py, edges.py (modify)

 After each mutation (create, update, delete), broadcast the change via Supabase Realtime:
 await supabase.channel(f"project:{project_id}").send({
     "type": "broadcast",
     "event": "entity_created",
     "payload": entity.model_dump()
 })

 Alternatively, use Supabase Postgres Changes (CDC) — listen to database changes via Supabase's built-in trigger system. This is simpler as the backend doesn't need to manually broadcast; Supabase auto-broadcasts row changes to subscribed clients.

 Recommended approach: Use Postgres Changes (CDC) for simplicity. The frontend subscribes to table changes filtered by project_id.

 2.3 Frontend: Subscribe to Changes

 New file: frontend/src/hooks/useRealtimeSync.ts

 function useRealtimeSync(projectId: string) {
   useEffect(() => {
     const channel = supabase
       .channel(`project:${projectId}`)
       .on('postgres_changes', {
         event: '*',
         schema: 'public',
         table: 'entities',
         filter: `project_id=eq.${projectId}`
       }, (payload) => {
         // Apply change to local graph
         if (payload.eventType === 'INSERT') addEntity(payload.new);
         if (payload.eventType === 'DELETE') removeEntity(payload.old.id);
         if (payload.eventType === 'UPDATE') updateEntity(payload.new);
       })
       .on('postgres_changes', {
         event: '*',
         schema: 'public',
         table: 'edges',
         filter: `project_id=eq.${projectId}`
       }, (payload) => {
         // Apply edge changes similarly
       })
       .subscribe();

     return () => { supabase.removeChannel(channel); };
   }, [projectId]);
 }

 2.4 Conflict Resolution

 - Last-write-wins for property updates (simplest approach)
 - Entity/edge creation deduplication already handled by type + value uniqueness constraint
 - Deletions are idempotent (deleting a non-existent entity is a no-op)
 - The Graphology graph is the source of truth locally; database is the source of truth globally
 - Future enhancement: operational transform or CRDT for concurrent property edits

 2.5 Presence (Optional)

 Show other users' cursors/activity on the graph:
 - Use Supabase Realtime Presence to track which users are connected to a project
 - Show small avatar badges near the graph canvas
 - Optional: show a colored ring around the node another user has selected

 ---
 3. Plugin System — Directory-Based Transform Discovery

 3.1 Plugin Directory Structure

 Plugins live in a configurable directory (default: plugins/ relative to the backend root). Each plugin is a subdirectory:

 plugins/
 ├── my-custom-transforms/
 │   ├── plugin.yaml          # Plugin metadata (required)
 │   ├── requirements.txt     # Optional: pip dependencies
 │   ├── transforms/
 │   │   ├── __init__.py
 │   │   ├── my_transform.py  # Must subclass BaseTransform
 │   │   └── another.py
 │   └── entities/
 │       └── custom_types.yaml  # Optional: custom entity types
 └── shodan-transforms/
     ├── plugin.yaml
     ├── requirements.txt
     └── transforms/
         ├── __init__.py
         └── ip_to_shodan.py

 plugin.yaml schema:
 name: my-custom-transforms
 version: "1.0.0"
 display_name: "My Custom Transforms"
 description: "A set of custom OSINT transforms"
 author: "author@example.com"
 min_ogi_version: "0.3.0"
 entity_types: []           # Optional custom entity types to register

 3.2 Plugin Discovery Engine

 New file: backend/ogi/engine/plugin_engine.py

 class PluginEngine:
     def __init__(self, plugin_dirs: list[str]):
         self.plugin_dirs = plugin_dirs
         self.plugins: dict[str, PluginInfo] = {}

     def discover(self) -> list[PluginInfo]:
         """Scan plugin directories for valid plugins."""
         # For each dir in plugin_dirs:
         #   - List subdirectories
         #   - Look for plugin.yaml
         #   - Validate schema
         #   - Return list of discovered plugins

     def load_transforms(self, plugin_name: str) -> list[BaseTransform]:
         """Import and instantiate transforms from a plugin."""
         # - Add plugin's transforms/ directory to sys.path
         # - Import all .py files
         # - Find all BaseTransform subclasses
         # - Instantiate and return

     def load_all(self, transform_engine: TransformEngine) -> None:
         """Discover all plugins and register their transforms."""
         for plugin in self.discover():
             transforms = self.load_transforms(plugin.name)
             for t in transforms:
                 transform_engine.register(t)
             self.plugins[plugin.name] = plugin

 3.3 Update TransformEngine

 File: backend/ogi/engine/transform_engine.py (modify)

 Keep auto_discover() for built-in transforms. Add a new method:

 def load_plugins(self, plugin_dirs: list[str]) -> None:
     engine = PluginEngine(plugin_dirs)
     engine.load_all(self)

 Call this in main.py lifespan after auto_discover().

 3.4 Plugin Management API

 New file: backend/ogi/api/plugins.py

 - GET /api/v1/plugins — list installed plugins with their transforms
 - GET /api/v1/plugins/{name} — get plugin details
 - POST /api/v1/plugins/{name}/enable — enable/disable a plugin
 - POST /api/v1/plugins/{name}/reload — reload transforms from plugin directory

 3.5 Frontend Plugin UI

 New component: frontend/src/components/PluginManager.tsx

 - Accessible from Toolbar settings menu
 - Lists installed plugins with name, version, author, transform count
 - Toggle enable/disable per plugin
 - "Reload" button to pick up changes from the filesystem
 - Shows which transforms come from which plugin

 3.6 API Key Management for Transforms

 New file: backend/ogi/api/api_keys.py

 - GET /api/v1/settings/api-keys — list configured services (names only, not keys)
 - POST /api/v1/settings/api-keys — save an API key (encrypted at rest)
 - DELETE /api/v1/settings/api-keys/{service} — remove a key

 New component: frontend/src/components/ApiKeySettings.tsx

 - Settings dialog to configure API keys for transforms (e.g., VirusTotal, Shodan)
 - Stored per-user in the api_keys table
 - Injected into TransformConfig.settings when running transforms that need them

 ---
 4. Supabase Storage — File Exports & Attachments

 4.1 Storage Buckets

 Create Supabase Storage buckets:
 - exports — exported graph files (JSON, CSV, GraphML)
 - attachments — entity file attachments (future: screenshots, documents)

 4.2 Backend Integration

 File: backend/ogi/api/export.py (modify)

 After generating an export file, optionally upload it to Supabase Storage:
 - Generate export in-memory
 - Upload to exports/{project_id}/{filename}
 - Return a signed download URL (valid for 1 hour)
 - Also support direct download (current behavior) for non-Supabase deployments

 4.3 Frontend Integration

 - Export dialog shows both "Download" and "Save to Cloud" options
 - Import dialog supports loading from Supabase Storage bucket
 - URL-based sharing of exports between team members

 ---
 5. Docker Deployment

 5.1 Backend Dockerfile

 New file: backend/Dockerfile

 FROM python:3.12-slim
 WORKDIR /app
 COPY pyproject.toml .
 RUN pip install uv && uv pip install --system -e .
 COPY ogi/ ogi/
 COPY plugins/ plugins/  # Include default plugins
 EXPOSE 8000
 CMD ["uvicorn", "ogi.main:app", "--host", "0.0.0.0", "--port", "8000"]

 5.2 Frontend Dockerfile

 New file: frontend/Dockerfile

 FROM node:20-alpine AS build
 WORKDIR /app
 RUN npm install -g pnpm
 COPY package.json pnpm-lock.yaml ./
 RUN pnpm install --frozen-lockfile
 COPY . .
 RUN pnpm build

 FROM nginx:alpine
 COPY --from=build /app/dist /usr/share/nginx/html
 COPY nginx.conf /etc/nginx/conf.d/default.conf
 EXPOSE 80

 5.3 Docker Compose

 New file: docker-compose.yml (project root)

 services:
   backend:
     build: ./backend
     ports: ["8000:8000"]
     env_file: .env
     depends_on: [db]
     volumes:
       - ./plugins:/app/plugins  # Mount plugins directory

   frontend:
     build: ./frontend
     ports: ["3000:80"]
     depends_on: [backend]

   db:
     image: postgres:16-alpine
     environment:
       POSTGRES_DB: ogi
       POSTGRES_USER: postgres
       POSTGRES_PASSWORD: postgres
     volumes:
       - pgdata:/var/lib/postgresql/data
     ports: ["5432:5432"]

 volumes:
   pgdata:

 Note: For Supabase-hosted deployments, the db service is omitted — the backend connects directly to the Supabase PostgreSQL instance. The docker-compose is for self-hosted deployments.

 5.4 Environment Configuration

 New file: .env.example

 # Supabase (for hosted deployment)
 OGI_SUPABASE_URL=https://your-project.supabase.co
 OGI_SUPABASE_ANON_KEY=eyJ...
 OGI_SUPABASE_SERVICE_ROLE_KEY=eyJ...

 # Direct PostgreSQL (for self-hosted)
 OGI_DATABASE_URL=postgresql://postgres:postgres@db:5432/ogi

 # SQLite fallback (for local dev)
 # OGI_USE_SQLITE=true
 # OGI_DATABASE_PATH=ogi.db

 # Plugins
 OGI_PLUGIN_DIRS=plugins,/opt/ogi/plugins

 5.5 Frontend nginx.conf

 New file: frontend/nginx.conf

 - Serve static files from /usr/share/nginx/html
 - Proxy /api/ requests to http://backend:8000
 - SPA fallback: serve index.html for all non-file routes

 ---
 6. Implementation Order

 Step 1: Config + Database Migration

 - Update config.py to use pydantic-settings with .env support
 - Create asyncpg pool wrapper in database.py
 - Write PostgreSQL schema migration (all tables + RLS policies)
 - Migrate all 4 stores from aiosqlite to asyncpg
 - Update main.py lifespan to use asyncpg pool
 - Keep SQLite fallback behind use_sqlite flag
 - Verify: Backend starts, all existing tests pass with PostgreSQL, CRUD works

 Files to modify:
 - backend/ogi/config.py
 - backend/ogi/db/database.py
 - backend/ogi/db/migrations.py
 - backend/ogi/store/project_store.py
 - backend/ogi/store/entity_store.py
 - backend/ogi/store/edge_store.py
 - backend/ogi/store/transform_run_store.py
 - backend/ogi/main.py

 Step 2: Authentication

 - Add backend/ogi/api/auth.py with JWT validation
 - Add get_current_user dependency to all route handlers
 - Add profiles, project_members tables and RLS
 - Add project sharing endpoints
 - Frontend: create Supabase client, auth store, auth page, auth guard
 - Update API client to include auth headers
 - Verify: Can sign up, log in, create project, share with another user

 New files:
 - backend/ogi/api/auth.py
 - backend/ogi/api/members.py
 - frontend/src/lib/supabase.ts
 - frontend/src/stores/authStore.ts
 - frontend/src/components/AuthPage.tsx
 - frontend/src/components/AuthGuard.tsx
 - frontend/src/components/ShareDialog.tsx

 Step 3: Real-Time Collaboration

 - Frontend: add useRealtimeSync hook subscribing to Supabase Postgres Changes
 - Wire into graphStore to apply remote changes to local Graphology graph
 - Add presence indicators (optional)
 - Verify: Open two browser tabs → add entity in one → appears in the other

 New files:
 - frontend/src/hooks/useRealtimeSync.ts

 Step 4: Plugin System

 - Create PluginEngine with directory scanning + dynamic import
 - Add plugin.yaml schema validation
 - Register plugin transforms in TransformEngine
 - Add plugin management API endpoints
 - Frontend: PluginManager component
 - Create an example plugin for testing
 - Verify: Drop a plugin folder → restart → transforms appear in the UI

 New files:
 - backend/ogi/engine/plugin_engine.py
 - backend/ogi/api/plugins.py
 - frontend/src/components/PluginManager.tsx
 - plugins/example-plugin/plugin.yaml
 - plugins/example-plugin/transforms/hello_world.py

 Step 5: API Key Management

 - Add api_keys table and store
 - Add API key CRUD endpoints
 - Inject keys into transform config at runtime
 - Frontend: ApiKeySettings component
 - Verify: Set VirusTotal API key → run hash lookup transform → key is used

 New files:
 - backend/ogi/store/api_key_store.py
 - backend/ogi/api/api_keys.py
 - frontend/src/components/ApiKeySettings.tsx

 Step 6: Storage Integration

 - Configure Supabase Storage buckets
 - Update export endpoints to optionally upload to storage
 - Add signed URL generation for downloads
 - Verify: Export project → file appears in Supabase Storage → download works

 Step 7: Docker

 - Write Dockerfiles for backend and frontend
 - Write docker-compose.yml
 - Write nginx.conf for frontend
 - Write .env.example
 - Test full stack with docker compose up
 - Verify: docker compose up → open http://localhost:3000 → full app works

 New files:
 - backend/Dockerfile
 - frontend/Dockerfile
 - frontend/nginx.conf
 - docker-compose.yml
 - .env.example

 ---
 7. New File Manifest

 Backend — New Files

 backend/ogi/
 ├── api/
 │   ├── auth.py                # JWT validation + get_current_user
 │   ├── members.py             # Project member management
 │   ├── plugins.py             # Plugin management endpoints
 │   └── api_keys.py            # API key CRUD
 ├── engine/
 │   └── plugin_engine.py       # Directory-based plugin discovery
 ├── store/
 │   └── api_key_store.py       # Encrypted API key storage
 └── models/
     └── (add UserProfile, ProjectMember, PluginInfo, ApiKey models)

 backend/
 └── Dockerfile

 Frontend — New Files

 frontend/src/
 ├── lib/
 │   └── supabase.ts            # Supabase client initialization
 ├── stores/
 │   └── authStore.ts           # Auth state management
 ├── components/
 │   ├── AuthPage.tsx           # Login/signup page
 │   ├── AuthGuard.tsx          # Auth route guard
 │   ├── ShareDialog.tsx        # Project sharing dialog
 │   ├── PluginManager.tsx      # Plugin list/management
 │   └── ApiKeySettings.tsx     # API key configuration
 ├── hooks/
 │   └── useRealtimeSync.ts     # Supabase Realtime subscription

 frontend/
 ├── Dockerfile
 └── nginx.conf

 Root — New Files

 docker-compose.yml
 .env.example
 plugins/
 └── example-plugin/
     ├── plugin.yaml
     └── transforms/
         ├── __init__.py
         └── hello_world.py

 ---
 8. New Dependencies

 Backend (add to pyproject.toml)

 asyncpg>=0.30.0
 supabase>=2.0.0
 python-jose[cryptography]>=3.3.0
 pydantic-settings>=2.0.0
 pyyaml>=6.0.0               # Parse plugin.yaml files

 Frontend (add to package.json)

 @supabase/supabase-js

 ---
 9. Verification

 Per-step verification:

 1. Database migration: uv run pytest — all existing tests pass with PostgreSQL. Manual: create/read/update/delete projects, entities, edges via API.
 2. Auth: Sign up → log in → create project → access denied without token. Share project → other user can see it.
 3. Real-time: Two browser tabs on the same project → add entity in tab A → entity appears in tab B within 1–2 seconds.
 4. Plugins: Create plugins/test-plugin/ with a simple transform → restart backend → transform appears in GET /api/v1/transforms and in the frontend UI.
 5. API keys: Configure a VirusTotal key → run hash lookup → transform uses the key. Delete key → transform shows "API key required" message.
 6. Storage: Export project → download link works. Upload attachment → visible in Supabase dashboard.
 7. Docker: docker compose up --build → open browser → create account → full workflow works.

 End-to-end scenario:

 1. docker compose up → OGI launches
 2. Sign up with email → lands on project list
 3. Create project "Investigation Alpha"
 4. Add Domain entity "target-domain.com"
 5. Run "Domain to IP" transform → IP nodes appear
 6. Share project with another user (different browser/incognito)
 7. Second user opens the project → sees the same graph
 8. First user adds a new entity → appears in second user's graph in real-time
 9. Install a custom plugin by dropping it in plugins/ → restart → new transforms available
 10. Export project as JSON → download works → import into a new project → graph matches