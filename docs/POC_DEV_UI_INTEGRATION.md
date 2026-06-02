# POC ↔ Dev UI integration

Branch: `feature/G2-overlap-detection` → PR to `dev`

## What this delivers

- **POC AI backend** (TF-IDF, overlap, Ollama, JSON platform store) integrated with **dev wireframe UI**
- Dev route mapping: `projectId` → module, `groupId` → project, `studentId` → student
- **G2-122 – G2-129** dedicated overlap review API + dev UI pages
- PR [#15](https://github.com/StendenRepo/ai-assessment-platform/pull/15) review comments addressed on this branch

## Wired UI (dev styling)

| Screen | Features |
|--------|----------|
| Projects list | `listModules` merged with dev mock projects |
| New project | `createModule` → `createGroup` → students → evidence → criteria |
| Project groups | `getModule` groups; link to overlaps |
| Criteria | Rubric + module guide upload (POC); student criteria tab stays wireframe mock |
| Group page | Evidence upload/remove, add/remove students, **Run AI analysis**, overlaps |
| Student page | **AI insights**, **draft**, **oral questions**, **chat** (FAB/SSE), **export**, consent + transcript, workspace evidence |
| Overlaps list/detail | Scan, confirmed/possible tabs, side-by-side, export |
| Reports | Live **audit log** from `/api/v1/audit` |
| Settings → AI | Live **LLM status** from `/api/v1/llm-status` |

POC workspace shell is **not** ported. Dev **`/modules`** (SQL + JWT) remains; POC store uses the same `/api/v1/modules` paths and is registered **first** in the API router so wireframe `/projects` flows keep working. Use module UI for DB-backed modules and `/projects` for POC demos (`proj-1`, `group-1`).

## API

### Dev bridge

| Method | Path |
|--------|------|
| POST | `/api/v1/projects/{projectId}/groups/{groupId}/ensure` |
| POST | `/api/v1/projects/{projectId}/groups/{groupId}/analyze` |
| GET | `/api/v1/projects/{projectId}/groups/{groupId}/analyze/status` |
| GET | `/api/v1/projects/{projectId}/groups/{groupId}/students/{studentId}/ai-insights` |

### Platform (used by frontend via `platformApi.js`)

| Method | Path |
|--------|------|
| POST | `/api/v1/modules/{moduleId}/projects/{projectId}/analyze` |
| GET | `…/students/{studentId}` (workspace) |
| PATCH | `…/students/{studentId}/draft` |
| POST | `…/students/{studentId}/chat/stream` |
| GET | `…/export/zip`, `…/export/eml` |

### Overlaps (G2)

See [`G2-OVERLAP-STORIES.md`](G2-OVERLAP-STORIES.md).

## Verify

```bash
docker compose up -d --build
./test/run.sh
```

Manual: login `admin@admin.nl` / `admin` → project → group → **Run AI analysis** → student → insights/drafts/chat → overlaps.
