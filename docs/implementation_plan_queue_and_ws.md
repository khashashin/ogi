Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
Transform Job Queue (RQ + Redis) + WebSocket Communication

Context

Transforms currently execute synchronously — the frontend POST /transforms/{name}/run blocks until the transform finishes, then returns the full result. Slow transforms (WHOIS, cert transparency, username search) can take 10-30+ seconds, causing HTTP
timeouts, unresponsive UI, and no way to cancel. This change makes all transforms (built-in and plugin) run through a Redis-backed job queue (RQ), with results delivered via WebSocket.

Key constraint: BaseTransform.run() interface does NOT change — plugin/community transform authors need zero modifications.

Architecture

Frontend FastAPI (web process) RQ Worker process
┌──────────────┐ ┌────────────────────┐ ┌──────────────────┐
│TransformPanel│─POST /run─→│ Validate + enqueue │──RQ job──→│ Execute transform│
│ │←{id,pending}│ Return immediately │ │ Persist results │
│ │ │ │ │ Publish to Redis │
│useTransformWS│◄═══WS═════│ WS Manager listens │◄─pub/sub──│ channel │
│ → add graph │ job_complete│ to Redis pub/sub │ └──────────────────┘
│ → toast │ job_failed │ │ │
└──────────────┘ └────────────────────┘ │
┌───────┴──────┐
│ Redis │
│ (queue + │
│ pub/sub) │
└──────────────┘

- RQ (Redis Queue) for job management — persistent, retries, timeouts, monitoring via rq-dashboard
- Redis pub/sub for WS notifications — worker publishes completion events, FastAPI subscribes and broadcasts to connected WebSocket clients
- Redis always required — added to docker-compose for all environments, local dev runs Redis via Docker or local install

---

Step 1: Add Redis + RQ Dependencies

backend/pyproject.toml — Add dependencies

"rq>=2.3.0",
"redis>=6.0.0",

backend/ogi/config.py — Add Redis settings

redis_url: str = "redis://localhost:6379/0"
transform_timeout: int = 300 # seconds per transform job
rq_queue_name: str = "transforms"

---

Step 2: Backend — RQ Worker Module

Create backend/ogi/worker/transform_job.py

This module contains the function that RQ workers execute. It runs in a separate process from FastAPI, so it must:

- Initialize its own DB connection (call init_db())
- Initialize TransformEngine (call auto_discover() + load_plugins())
- Look up the transform, entity, and execute it
- Persist results (entities, edges, transform run) to DB
- Publish completion event to Redis pub/sub channel

The job function signature:
def execute_transform(
run_id: str,
transform_name: str,
entity_data: dict, # serialized Entity
project_id: str,
config_data: dict, # serialized TransformConfig
) -> dict: # serialized TransformRun

RQ passes serializable arguments (no ORM objects). The function:

1.  Deserializes entity + config from dicts
2.  Calls transform.run(entity, config) (uses asyncio.run() since RQ workers are sync)
3.  Persists new entities/edges to DB (reuses the deduplication logic from current api/transforms.py lines 87-150)
4.  Updates TransformRun status to COMPLETED/FAILED
5.  Publishes a TransformJobMessage JSON to Redis channel ogi:transform_events:{project_id}

Create backend/ogi/worker/run_worker.py

Entry point for starting the RQ worker:
from redis import Redis
from rq import Worker, Queue
from ogi.config import settings

conn = Redis.from_url(settings.redis_url)
queue = Queue(settings.rq_queue_name, connection=conn)
worker = Worker([queue], connection=conn)
worker.work()

Update backend/Dockerfile — No change needed for web

Create backend/Dockerfile.worker (or use CMD override in docker-compose)

Same base image as backend, but CMD runs the RQ worker instead of uvicorn:
CMD ["python", "-m", "ogi.worker.run_worker"]

---

Step 3: Backend — Modify Transform API

backend/ogi/api/transforms.py

Change POST /{name}/run endpoint:

1.  Same validation (auth, entity lookup, transform lookup via get_transform)
2.  Create TransformRun(status=PENDING), persist to DB immediately
3.  Enqueue RQ job: queue.enqueue(execute_transform, run_id, name, entity.model_dump(), project_id, config.model_dump(), job_timeout=settings.transform_timeout)
4.  Return the pending TransformRun — frontend gets instant response

Add POST /transforms/runs/{run_id}/cancel endpoint:

- Calls rq_job.cancel() on the Redis job
- Updates TransformRun.status to CANCELLED in DB
- Publishes cancellation event to Redis pub/sub

The TransformEngine.run_transform() method stays for CLI/scripting use — it's just no longer called from the API.

---

Step 4: Backend — WebSocket Manager

Create backend/ogi/api/websocket.py

ConnectionManager class:

- Tracks WebSocket connections per project: dict[UUID, list[WebSocket]]
- broadcast_to_project(project_id, message) — sends JSON to all connections for that project
- Dead connection cleanup on send failure

WebSocket endpoint: GET /api/v1/ws/transforms/{project_id}?token=<jwt>

- Auth: validates JWT via Supabase get_user(token). In local mode (no Supabase), accepts without auth
- Incoming messages from client: cancel (cancel a job), ping (heartbeat → responds pong)

Redis pub/sub listener:
On startup (in lifespan), spawn a background asyncio.Task that:

1.  Subscribes to Redis pub/sub pattern ogi:transform_events:\*
2.  On each message, parses TransformJobMessage and calls ws_manager.broadcast_to_project(project_id, msg)

This bridges the RQ worker (separate process) → FastAPI WebSocket connections.

---

Step 5: Backend — Models + Wiring

backend/ogi/models/transform.py

- Add CANCELLED = "cancelled" to TransformStatus enum
- Create TransformJobMessage Pydantic model (not a DB table):

class TransformJobMessage(BaseModel):
type: str # "job_submitted" | "job_started" | "job_completed" | "job_failed" | "job_cancelled"
job_id: UUID
project_id: UUID
transform_name: str
input_entity_id: UUID
progress: float | None = None
message: str | None = None
result: dict[str, Any] | None = None
error: str | None = None
timestamp: datetime

backend/ogi/api/dependencies.py — Add Redis/Queue helpers

\_redis_conn: Redis | None = None
\_rq_queue: Queue | None = None

def init_redis(conn: Redis, queue: Queue) -> None: ...
def get_redis() -> Redis: ...
def get_rq_queue() -> Queue: ...

backend/ogi/main.py — Initialize in lifespan

After transform engine init:

1.  Create Redis connection from settings.redis_url
2.  Create RQ Queue
3.  Call init_redis(conn, queue)
4.  Start Redis pub/sub listener task (for WS broadcasting)
5.  Recover stale jobs: query DB for status=RUNNING runs, mark as FAILED

backend/ogi/api/router.py — Include WS router

from ogi.api import websocket
api_router.include_router(websocket.router)

---

Step 6: Docker — Add Redis + Worker

docker-compose.yml — Add Redis service + worker

redis:
image: redis:7-alpine
ports: - "6379:6379"
healthcheck:
test: ["CMD", "redis-cli", "ping"]
interval: 5s
timeout: 5s
retries: 5

worker:
build: ./backend
command: ["python", "-m", "ogi.worker.run_worker"]
env_file: .env
depends_on:
db:
condition: service_healthy
redis:
condition: service_healthy
volumes: - ./plugins:/app/plugins
environment: - OGI_DATABASE_URL=${OGI_DATABASE_URL:-postgresql://postgres:postgres@db:5432/ogi} - OGI_USE_SQLITE=false - OGI_REDIS_URL=redis://redis:6379/0

Backend service gets:
environment:

- OGI_REDIS_URL=redis://redis:6379/0
  depends_on:
  redis:
  condition: service_healthy

docker-compose.prod.yml — Same pattern

Add redis service and worker service. Backend gets OGI_REDIS_URL and depends_on: redis.

---

Step 7: Proxy Config — WebSocket Support

frontend/vite.config.ts — Enable WS proxy

proxy: {
'/api': {
target: 'http://localhost:8000',
ws: true,
},
},

frontend/nginx.conf — Add WebSocket upgrade headers

location /api/ {
proxy_pass http://backend:8000;
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_read_timeout 3600s;
}

---

Step 8: Frontend — Types

frontend/src/types/transform.ts

- Add "cancelled" to TransformStatus type
- Add interfaces:

type TransformJobMessageType =
| "job_submitted" | "job_started" | "job_completed" | "job_failed" | "job_cancelled";

interface TransformJobMessage {
type: TransformJobMessageType;
job_id: string;
project_id: string;
transform_name: string;
input_entity_id: string;
progress: number | null;
message: string | null;
result: TransformResult | null;
error: string | null;
timestamp: string;
}

interface TransformWsCancelMessage { type: "cancel"; job_id: string; }
interface TransformWsPingMessage { type: "ping"; }
type TransformWsOutgoing = TransformWsCancelMessage | TransformWsPingMessage;

---

Step 9: Frontend — WebSocket Hook

Create frontend/src/hooks/useTransformWebSocket.ts

- Connects to ws(s)://host/api/v1/ws/transforms/{projectId}?token=<jwt>
- Gets auth token from supabase.auth.getSession()
- Auto-reconnect with exponential backoff (1s → 2s → 4s → 8s → 16s cap)
- 30s heartbeat ping
- Returns { cancelJob } function
- Takes onMessage callback

---

Step 10: Frontend — Transform Job Store

Create frontend/src/stores/transformJobStore.ts

Zustand store:

- activeJobs: Map<string, TransformJob> — pending/running jobs
- recentCompleted: TransformRun[] — last 20 finished runs
- submitJob(run) — add from REST response
- handleMessage(msg) — update state from WS message
- clearJob(jobId) / clearAll()

---

Step 11: Frontend — Update TransformPanel + API Client

frontend/src/components/TransformPanel.tsx

handleRun — fire-and-forget:
const run = await api.transforms.run(name, entity.id, currentProject.id);
useTransformJobStore.getState().submitJob(run);

WebSocket integration — wire useTransformWebSocket (in WorkspaceView or TransformPanel):

- job_completed → add entities/edges to graph via graphStore.addEntity/addEdge, success toast
- job_failed → error toast
- job_cancelled → remove from active jobs

UI changes:

- Show active jobs with status indicator
- Cancel button per active job
- Allow running multiple transforms simultaneously (remove single running lock)

frontend/src/api/client.ts — Add cancel method

cancel: (runId: string) =>
request<{ status: string; run_id: string }>(`/transforms/runs/${runId}/cancel`, { method: "POST" }),

---

Files Summary

Create (5 files)

┌─────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────┐
│ File │ Purpose │
├─────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ backend/ogi/worker/transform_job.py │ RQ job function — executes transform, persists results, publishes event │
├─────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ backend/ogi/worker/run_worker.py │ RQ worker entry point │
├─────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ backend/ogi/api/websocket.py │ WS endpoint + ConnectionManager + Redis pub/sub listener │
├─────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ frontend/src/hooks/useTransformWebSocket.ts │ WS client hook with reconnection │
├─────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ frontend/src/stores/transformJobStore.ts │ Zustand store for job tracking │
└─────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────┘

Modify (11 files)

┌────────────────────────────────────────────┬───────────────────────────────────────────────────────────────┐
│ File │ Change │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ backend/pyproject.toml │ Add rq, redis dependencies │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ backend/ogi/config.py │ Add redis_url, transform_timeout, rq_queue_name settings │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ backend/ogi/models/transform.py │ Add CANCELLED status, TransformJobMessage model │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ backend/ogi/api/dependencies.py │ Add Redis/Queue singletons │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ backend/ogi/main.py │ Init Redis + pub/sub listener in lifespan, recover stale jobs │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ backend/ogi/api/transforms.py │ Enqueue-and-return pattern, add cancel endpoint │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ backend/ogi/api/router.py │ Include WS router │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ docker-compose.yml │ Add redis + worker services, wire env vars │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ docker-compose.prod.yml │ Add redis + worker services │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ frontend/vite.config.ts │ Enable WS proxy │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ frontend/nginx.conf │ Add WS upgrade headers │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ frontend/src/types/transform.ts │ Add WS message types, cancelled status │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ frontend/src/components/TransformPanel.tsx │ Fire-and-forget, WS-driven results, multi-job UI │
├────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
│ frontend/src/api/client.ts │ Add cancel method │
└────────────────────────────────────────────┴───────────────────────────────────────────────────────────────┘

---

Implementation Order

1.  Dependencies + config (pyproject.toml, config.py) — non-breaking
2.  Models update (transform.py) — non-breaking
3.  Worker module (transform_job.py, run_worker.py) — standalone
4.  WebSocket manager (websocket.py) — standalone
5.  Wiring (dependencies.py, main.py, router.py) — additive
6.  Docker (docker-compose.yml, docker-compose.prod.yml) — additive
7.  Proxy config (vite.config.ts, nginx.conf) — additive
8.  Transform API change (transforms.py) — breaking: frontend must update simultaneously
9.  Frontend types + hook + store + TransformPanel + API client — all at once

Steps 1-7 are additive. Step 8+9 are the breaking change and must ship together.

---

Impact on Community Transforms

Zero. BaseTransform.run(entity, config) -> TransformResult is unchanged. The RQ worker calls this method exactly as before. Plugin authors don't need to modify anything — the queue is invisible to transform implementations.

---

Verification

- uv pip install rq redis + redis-server running locally
- cd backend && OGI_USE_SQLITE=true OGI_DB_PATH=:memory: uv run python -m pytest — existing tests pass
- cd frontend && pnpm tsc --noEmit — TypeScript compiles
- cd frontend && pnpm build — Vite build succeeds
- docker compose up — all services start (backend, frontend, db, redis, worker)
- Manual flow:
  - Submit a transform → REST returns immediately with pending status
  - Worker picks up job, executes transform
  - WebSocket receives job_started, then job_completed with results
  - Entities/edges appear on graph
  - Cancel a running transform → job cancelled, removed from UI
  - Kill backend, restart → stale running jobs marked as failed
