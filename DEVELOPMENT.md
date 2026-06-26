# Development Guide — AI Assessment Platform

This document covers everything needed to contribute to the project: tech stack, project structure, local dev setup, testing, database migrations, CI/CD, and more.

> For end-user installation instructions see [README.md](README.md).

---

## Tech Stack

### Frontend

- [Next.js 16](https://nextjs.org/) (App Router)
- [React 19](https://react.dev/)
- JavaScript (JSX)
- [Tailwind CSS 4](https://tailwindcss.com/)
- [lucide-react](https://lucide.dev/) — icon library
- [ESLint 9](https://eslint.org/) — linting
- [Prettier 3](https://prettier.io/) — code formatting
- [Husky](https://typicode.github.io/husky/) + [lint-staged](https://github.com/lint-staged/lint-staged) — pre-commit hooks

### Backend

- [Python](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [Pydantic v2](https://docs.pydantic.dev/) — data validation
- [SQLAlchemy 2](https://www.sqlalchemy.org/) — ORM
- [Alembic](https://alembic.sqlalchemy.org/) — database migrations
- [Uvicorn](https://www.uvicorn.org/) — ASGI server
- [psycopg2-binary](https://www.psycopg.org/) — PostgreSQL driver
- [python-dotenv](https://github.com/theskumar/python-dotenv) — environment variables
- [PostgreSQL 16](https://www.postgresql.org/)

### Infrastructure

- [Docker](https://www.docker.com/) & Docker Compose
- [Ollama](https://ollama.com/) — on-premise LLM for assessment chat and overlap warnings
- **ai-detector** — RoBERTa classifier for AI-generated text detection (separate from Ollama)
- STT microservice (faster-whisper) for interview transcription
- pgAdmin 4 (development only)

---

## Project Structure

```txt
ai-assessment-platform/
│
├── frontend/                  # Next.js frontend application
│   ├── src/app/               # App Router pages and layouts
│   ├── public/                # Static assets
│   ├── Dockerfile
│   └── package.json
│
├── backend/                   # FastAPI backend application
│   ├── app/
│   │   ├── config.py          # Environment-based settings
│   │   ├── database.py        # SQLAlchemy engine & session
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── api/               # API dependencies, routers, endpoints
│   │   ├── models/            # SQLAlchemy models
│   │   └── services/          # Business logic
│   ├── Dockerfile
│   └── requirements.txt
│
├── stt/                       # Speech-to-text service
│   ├── app.py
│   └── Dockerfile
│
├── ai-detector/               # RoBERTa AI-text classifier
│   └── Dockerfile
│
├── scripts/                   # Seed import, demo setup helpers
├── .env.example               # Environment variable template
├── docker-compose.yml         # Production stack
├── docker-compose.dev.yml     # Development overrides (pgAdmin, hot-reload)
├── README.md                  # End-user installation guide
└── DEVELOPMENT.md             # This file
```

---

## Development Setup

Start all services with hot-reload for frontend and backend, plus pgAdmin:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Development uploads, recordings, and exports are stored in `backend/data` on the host so files created by the Dockerized backend are visible locally.

| Service      | URL                    |
| ------------ | ---------------------- |
| Frontend     | http://localhost:3000  |
| Backend      | http://localhost:8000  |
| STT API      | http://localhost:9000  |
| AI detector  | http://localhost:9001  |
| Ollama       | http://localhost:11434 |
| pgAdmin      | http://localhost:5050  |

**pgAdmin login:** `admin@admin.com` / `admin`
Connect to the database using host `postgres`, port `5432`, database `ai_assessment`, user `postgres`, password `postgres`.

### Regenerate Dev Seed SQLite DB

Regenerates `backend/database/database.db` with realistic test records (excluding file/evidence uploads):

```bash
./scripts/reseed-dev-db.sh
```

### Import Dev Seed into Postgres

Copies the SQLite seed database into the running Postgres database:

```bash
./scripts/import-db-to-postgres.sh
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_assessment
UPLOAD_DIR=/app/data/uploads
RECORDING_DIR=/app/data/recordings
EXPORT_DIR=/app/data/exports

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_MODEL_BACKUP=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=20

ASSESSMENT_OLLAMA_MODEL=qwen2.5:7b
ASSESSMENT_OLLAMA_MODEL_BACKUP=llama3.1:8b
ASSESSMENT_OLLAMA_TIMEOUT_SECONDS=120

VISION_MODEL=llava:7b

AI_DETECTOR_URL=http://ai-detector:9001
AI_DETECTOR_MODEL=Hello-SimpleAI/chatgpt-detector-roberta
AI_DETECTOR_TIMEOUT_SECONDS=120
```

> `.env` is git-ignored. Never commit real credentials — use `.env.example` as the committed template.

---

## Local AI Stack

All inference runs on-premise inside Docker. Nothing is sent to external APIs.

Ollama uses **two model tiers**:

| Env vars | Default models | Used for |
| -------- | -------------- | -------- |
| `OLLAMA_MODEL` / `OLLAMA_MODEL_BACKUP` | `llama3.2:1b` / `qwen2.5:3b` | General dev stack, image evidence helpers, fast paths |
| `ASSESSMENT_OLLAMA_MODEL` / backup | `qwen2.5:7b` / `llama3.1:8b` | Assessment suggestions, discuss/refine chat, overlap LLM |
| `VISION_MODEL` | `llava:7b` | Image evidence descriptions |

Pull or refresh all Ollama weights:

```bash
docker compose -f docker-compose.dev.yml run --rm ollama-init
```

Check what models are available:

```bash
curl http://localhost:8000/api/v1/health/ollama
```

Shared client: `backend/app/services/ollama_client.py` (per-call model chain with backup fallback).

### AI Detector (RoBERTa)

AI-generated text detection uses a dedicated **ai-detector** container (`Hello-SimpleAI/chatgpt-detector-roberta`), not Ollama. This keeps classification separate from generative tasks and produces more stable segment-level scores.

```env
AI_DETECTOR_URL=http://ai-detector:9001
AI_DETECTOR_MODEL=Hello-SimpleAI/chatgpt-detector-roberta
```

The image is built by `docker compose up --build`. Model weights download automatically on first container start and are cached in the `ai_detector_cache` volume (~1–2 GB).

**ai-detector is additive.** Assessment, uploads, recordings, and text overlap scanning work the same as before. Only the AI-writing segment analysis in overlap review prefers the new container; if it is down or still loading, the backend falls back to the existing Ollama-based detection path.

---

## API Endpoints

Base API URL: `http://localhost:8000/api/v1`

Core route groups:

| Group | Path |
| ----- | ---- |
| Health | `/health` |
| Auth | `/auth` |
| Admin | `/admin` |
| Modules | `/modules` |
| Projects | `/projects` |
| Students | `/students` |
| Evidence | `/evidence` |
| Recordings | `/recordings` |

Interactive docs (while running locally):

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Assessment Review Workflow

The student assessment tab implements a teacher-in-the-loop review flow:

1. **Generate suggestions** — Ollama scores each rubric criterion from uploaded evidence, module book, and interview transcripts.
2. **Discuss with AI** — conversational chat only; nothing is written to the form until the teacher accepts a proposal.
3. **Refine from discussion** — builds a structured proposal (score/comment diffs) from the full thread.
4. **Accept or reject** — accepted changes update the draft and highlight affected criteria in the form. Overrides lock a criterion from further AI changes.
5. **Finalize** — locks the assessment and records an audit snapshot.

API surface (`/api/v1/assessments/{id}/…`):

| Endpoint | Purpose |
| -------- | ------- |
| `POST /chat` | Discuss (no draft mutation) |
| `POST /chat/refine` | Build refinement proposal |
| `POST /chat/apply` | Accept proposal |
| `POST /chat/reject` | Reject proposal |
| `POST /chat/undo` | Revert last applied refinement |

---

## Overlap Detection

Overlap scanning compares evidence across students in a module group. The review UI supports:

- Side-by-side document comparison with synced scrolling
- Text similarity, paraphrase, and integrity signals (including AI-segment flags from the RoBERTa service)
- Highlighted phrase matching in the detail view

---

## Features

### Current

- Role-based authentication and profile endpoint
- Module and student management APIs
- Evidence upload, listing, content readback, and supported types endpoint
- Recording workflow with consent, transcription, reminders, extension limits, and auto-purge
- Audit events for sensitive operations
- Overlap detection with detail review UI, integrity signals, and AI-segment highlighting
- Assessment draft workflow: AI suggestions, per-criterion overrides, discuss/refine chat, finalize
- Frontend dashboard, settings, reports, and module workflows

### Planned

- Additional reporting and export options
- Further overlap and evidence-matching tuning
- UX polish across module pages
- Expanded AI review and evidence matching quality

---

## Code Formatting

This project uses Prettier for code formatting.

1. Install dependencies:

    ```bash
    npm install
    ```

2. Format code manually:

    ```bash
    npm run format
    ```

3. Pre-commit hook — Prettier is enforced on staged files automatically. Set up Husky:

    ```bash
    npm run prepare
    ```

---

## Recommended VS Code Extensions

- ESLint
- Tailwind CSS IntelliSense
- Prettier
- Error Lens

---

## Testing

### Backend

Tests are in `backend/tests/` and use pytest with an in-memory SQLite database — no running services required.

**With Docker (recommended)**

With the dev stack already running:

```bash
docker exec backend python -m pytest tests/ -v
```

If the stack is not running:

```bash
docker compose -f docker-compose.dev.yml run --rm backend python -m pytest tests/ -v
```

With coverage report:

```bash
docker exec backend python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

**Without Docker**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## Database Migration

Run Alembic inside the backend container.

1. Start services:

    ```bash
    docker compose up -d --build
    ```

2. Create a new migration after model changes:

    ```bash
    docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "describe change"
    ```

3. Upgrade to the latest revision:

    ```bash
    docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
    ```

4. Check the current revision:

    ```bash
    docker compose -f docker-compose.dev.yml exec backend alembic current -v
    ```

5. Downgrade one revision:

    ```bash
    docker compose -f docker-compose.dev.yml exec backend alembic downgrade -1
    ```

6. View migration history:

    ```bash
    docker compose -f docker-compose.dev.yml exec backend alembic history --indicate-current
    ```

Use the same commands with `docker-compose.yml` for non-dev environments.

---

## Git Workflow

```
feature/* → dev → test → main
```

Create a feature branch:

```bash
git checkout -b feature/feature-name
```

Commit changes:

```bash
git add .
git commit -m "Add feature"
```

Push branch:

```bash
git push origin feature/feature-name
```

---

## CI/CD & OTAP

All workflows are in `.github/workflows/`.

### `ci.yml` — Continuous Integration

Runs on every push and every pull request.

| Job | What it does |
| --- | ------------ |
| Frontend build | `npm ci` → `npm run build` |
| Backend check | `pip install -r requirements.txt` → import check on `app.main` |

### `otap-develop.yml` — Development (`dev` branch)

Runs on push to `dev`.

1. Runs CI checks
2. Builds Docker images for backend and frontend (`ai-assessment-backend:dev`, `ai-assessment-frontend:dev`)
3. Builds the full stack via `docker compose build`

### `otap-test.yml` — Test (`test` branch)

Runs on push to `test`.

1. Runs CI checks
2. Runs all backend tests with pytest + coverage (`backend/tests/`)
3. Runs frontend tests if a `test` script is present in `package.json`

### `otap-main.yml` — Production (`main` branch)

Runs on push to `main`.

1. Runs CI checks
2. Automatically generates a version tag (`v<year>.<month>.<day>-<short-sha>`)
3. Generates a changelog based on commits since the last tag
4. Creates a GitHub Release with the changelog and commit information

### OTAP Branch Strategy

| Branch | OTAP stage  | Workflow            |
| ------ | ----------- | ------------------- |
| `dev`  | Development | CI + Docker build   |
| `test` | Test        | CI + all tests      |
| `main` | Production  | CI + GitHub Release |

---

## Contributors

Developed by HBO Informatica students at NHL Stenden.
