# POC ↔ Dev UI integration (`feature/integrate-poc-dev-ui`)

## What this branch does

- Keeps **dev** wireframe UI (projects → groups → students, admin, JWT auth).
- Adds **POC AI pipeline** (TF-IDF, overlap, Ollama, JSON platform store) from `proof-of-concept-2`.
- Maps dev routes to the platform store:
  - `projectId` → module id (e.g. `proj-1`)
  - `groupId` → project id (e.g. `group-1`)
  - `studentId` → student id (e.g. `student-1`, `student-2` with fixture evidence)

## Frontend

Dev wireframe UI is **unchanged** (still mock data for projects/groups/AI insights). No new buttons or panels were added.

Wire the UI later via the dev-shaped API below when screens are ready.

## Verification

Automated tests live in [`test/`](../test/README.md). From repo root:

```bash
docker compose up -d --build
./test/run.sh
```

Ollama (optional): set `OLLAMA_BASE_URL` in `.env` (see `backend/.env.example`). Without Ollama, analysis uses TF-IDF + templates.

## API (dev-shaped)

| Method | Path |
|--------|------|
| POST | `/api/v1/projects/{projectId}/groups/{groupId}/ensure` |
| POST | `/api/v1/projects/{projectId}/groups/{groupId}/analyze` |
| GET | `/api/v1/projects/{projectId}/groups/{groupId}/analyze/status` |
| GET | `/api/v1/projects/{projectId}/groups/{groupId}/students/{studentId}/ai-insights` |
| GET | `/api/v1/llm-status` |

Full platform CRUD remains under `/api/v1/modules/...` (JSON store).
