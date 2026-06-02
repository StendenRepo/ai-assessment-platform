# Integration test suite

Standalone tests for branch `feature/integrate-poc-dev-ui`: POC AI backend merged into `dev`, without changing the dev wireframe UI.

## What was integrated (summary for reporting)

| Layer | Change |
|-------|--------|
| **Backend** | POC pipeline (TF-IDF, overlap, Ollama/templates), JSON platform store, `/api/v1/modules/...` routes |
| **Bridge API** | Dev URL shape: `projectId` → module, `groupId` → project, mock student ids → fixture evidence |
| **Database** | Existing Postgres + JWT auth/admin unchanged |
| **Frontend** | Unchanged (mock data); no new UI wiring |
| **Docker** | Platform data volume, Ollama via `host.docker.internal`, single Uvicorn worker for store consistency |

## What these tests prove

1. **Auth** — JWT login from `dev` still works next to platform routes.
2. **Platform** — modules CRUD, seed-demo, LLM status.
3. **Dev bridge** — ensure → analyze → status → per-student `ai-insights` (overlap/suggestions from fixtures).
4. **Overlaps (G2-122/124/126)** — detect, list (confirmed/possible, sort), side-by-side detail API.
5. **Live stack** — same flow against `docker compose` on `:8000`.
6. **Frontend** — main pages return HTTP 200 (smoke only; no UI/API coupling).

## Prerequisites

1. From repo root: `docker compose up -d --build` (Postgres migrations create seed user).
2. Optional: Ollama on the host for LLM drafts (`scripts/ensure-ollama-mac.sh` on macOS). Tests pass without it (TF-IDF + templates).
3. **Seed login (live smoke):** `admin@admin.nl` / `admin`

- **API-only** (`./test/run.sh --api-only`): running `backend` container **or** local `pip install -r backend/requirements.txt` + `PYTHONPATH=backend pytest ...`
- **Live smoke** (`./test/run.sh` default): requires step 1 above

## Run everything

From repository root:

```bash
./test/run.sh
```

Options:

```bash
./test/run.sh --api-only          # pytest only
./test/run.sh --live-only         # integration + frontend smoke (needs Docker)
./test/run.sh --no-live           # skip live tests if stack is down
```

## Run individually

```bash
# API (local)
PYTHONPATH=backend pytest -c test/pytest.ini test/backend -v

# API (Docker)
docker compose cp test/backend backend:/app/test/backend
docker compose exec -T backend pytest /app/test/backend -v

# Live API smoke
./test/integration/smoke.sh

# Frontend smoke
./test/frontend/smoke.sh
```

## Layout

```
test/
  README.md           — this file
  run.sh              — runs all suites
  pytest.ini          — pytest config (pythonpath → backend)
  backend/            — FastAPI TestClient tests
  integration/        — curl smoke against running stack
  frontend/           — HTTP smoke for Next.js routes
```

## Expected results (verified)

- **19** pytest cases: pass
- **Integration smoke:** health, auth, ensure, analyze, insights, modules — pass
- **Frontend smoke:** `/`, `/dashboard`, `/projects` — 200

## API reference (bridge)

| Method | Path |
|--------|------|
| POST | `/api/v1/projects/{projectId}/groups/{groupId}/ensure` |
| POST | `/api/v1/projects/{projectId}/groups/{groupId}/analyze` |
| GET | `/api/v1/projects/{projectId}/groups/{groupId}/analyze/status` |
| GET | `/api/v1/projects/{projectId}/groups/{groupId}/students/{studentId}/ai-insights` |
| GET | `/api/v1/llm-status` |

Default smoke IDs: `proj-1`, `group-1`, `student-1` (Lisa Anderson fixture; overlap with `student-2`).
