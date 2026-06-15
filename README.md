# AI Assessment Platform

An on-premise AI-assisted platform for assessing student work in module-based education.

## Project Overview

This project is being developed as part of an Informatica HBO project at NHL Stenden.

The platform supports teachers and assessors by:

- Managing modules, module groups, and students
- Uploading and managing evidence and module documents
- Running assessment workflows with per-student scoring and feedback
- Recording assessments with consent, retention, and audit trails
- Using local AI support for evidence analysis and overlap detection
- Improving consistency and speed of individual contribution assessment

The project is currently in the prototype and development phase.

---

# Tech Stack

## Frontend

- [Next.js 16](https://nextjs.org/) (App Router)
- [React 19](https://react.dev/)
- JavaScript (JSX)
- [Tailwind CSS 4](https://tailwindcss.com/)
- [lucide-react](https://lucide.dev/) — icon library
- [ESLint 9](https://eslint.org/) — linting
- [Prettier 3](https://prettier.io/) — code formatting
- [Husky](https://typicode.github.io/husky/) + [lint-staged](https://github.com/lint-staged/lint-staged) — pre-commit hooks

## Backend

- [Python](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [Pydantic v2](https://docs.pydantic.dev/) — data validation
- [SQLAlchemy 2](https://www.sqlalchemy.org/) — ORM
- [Alembic](https://alembic.sqlalchemy.org/) — database migrations
- [Uvicorn](https://www.uvicorn.org/) — ASGI server
- [psycopg2-binary](https://www.psycopg.org/) — PostgreSQL driver
- [python-dotenv](https://github.com/theskumar/python-dotenv) — environment variables
- [PostgreSQL 16](https://www.postgresql.org/)

## Infrastructure

- [Docker](https://www.docker.com/) & Docker Compose
- [Ollama](https://ollama.com/) — on-premise LLM for assessment chat and overlap warnings
- **ai-detector** — RoBERTa classifier for AI-generated text detection (separate from Ollama)
- STT microservice (faster-whisper) for interview transcription
- pgAdmin 4 (development only)

## Version Control

- Git
- GitHub

---

# Project Structure

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
└── README.md
```

---

# Getting Started

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git

---

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd ai-assessment-platform
```

Copy the environment template:

```bash
cp .env.example .env
```

The default values in `.env` work out of the box with Docker Compose. Edit the file if you need custom credentials.

---

# Running the Project

## Development

Starts all services with hot-reload for frontend and backend, plus local AI services and pgAdmin:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Development uploads, recordings, and exports are stored in [backend/data](backend/data) on the host so files created by the Dockerized backend are visible locally.

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

To regenerate the local development seed database (`backend/database/database.db`) with realistic test records (excluding file/evidence uploads):

```bash
./scripts/reseed-dev-db.sh
```

### Import Dev Seed into Postgres

To copy the SQLite seed database into the running Postgres database used by pgAdmin:

```bash
./scripts/import-db-to-postgres.sh
```

## Production

```bash
docker compose -f docker-compose.yml up -d --build
```

See [Building containers and pulling models](#building-containers-and-pulling-models) for first-time setup, Ollama weights, and the new **ai-detector** service.

---

# Building containers and pulling models

Use this when setting up fresh, or when upgrading an existing `dev` deployment to this branch.

## 1. Update environment

```bash
cp .env.example .env   # skip if you already have .env
```

Ensure these keys are present:

```env
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

## 2. Build and start all containers

```bash
docker compose -f docker-compose.yml up -d --build
```

`--build` compiles the new **ai-detector** image along with frontend, backend, and stt. Existing Docker volumes (`postgres_data`, `platform_data`, `ollama_data`, etc.) are reused — no database reset required.

For development with hot-reload:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

The backend runs `alembic upgrade head` on startup, so new migrations (for example chat message metadata) apply automatically.

## 3. Pull Ollama LLM models

Container images and LLM weights are separate. After `ollama` is running, pull the configured models into the shared `ollama_data` volume:

```bash
docker compose -f docker-compose.yml run --rm ollama-init
```

Use the same command with `docker-compose.dev.yml` in dev. This pulls general, assessment, and vision models into the shared `ollama_data` volume. First run can take a while (~10+ GB total if all models are new).

## 4. ai-detector model download

Unlike Ollama, the RoBERTa classifier does not use `ollama-init`. The **ai-detector** container downloads `Hello-SimpleAI/chatgpt-detector-roberta` from Hugging Face on first start and caches it in the `ai_detector_cache` volume (~1–2 GB).

- **Production:** the backend waits for `ai-detector` to pass its health check (up to ~3 minutes on first boot).
- **Development:** the backend starts once the container is up; the model may still be loading for the first few minutes.

Check when it is ready:

```bash
curl http://localhost:9001/health
```

## 5. Verify the stack

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/ollama
curl http://localhost:9001/health
```

---

# Compatibility with existing features

The new services plug into the stack without replacing what was already there.

| Area | What it uses | Notes |
| ---- | ------------ | ----- |
| Auth, modules, students, evidence | Postgres | Unchanged |
| Recordings & STT | `stt` container | Unchanged |
| Assessment suggestions & chat | Ollama (`ASSESSMENT_OLLAMA_*`) | 7B models for JSON and reasoning |
| Overlap text similarity | Backend detectors | Unchanged |
| Overlap AI-segment flags | **ai-detector** (primary) | RoBERTa classifier |
| Overlap AI fallback | Ollama (`ASSESSMENT_OLLAMA_*`) + heuristics | When classifier unavailable |
| Image evidence (after merge with `dev`) | Ollama (`VISION_MODEL`) | `llava:7b` |
| General / future dev paths | Ollama (`OLLAMA_*`) | Fast 1B/3B defaults |

**ai-detector is additive.** Assessment, uploads, recordings, and text overlap scanning work the same as before. Only the AI-writing segment analysis in overlap review prefers the new container; if it is down or still loading, the backend falls back to the existing Ollama-based detection path.

No wipe of Postgres or upload volumes is needed when upgrading from `dev`.

---

# Local AI stack

All inference runs on-premise inside Docker. Nothing is sent to external APIs.

Ollama uses **two model tiers** so this branch aligns with `dev` defaults while keeping quality for assessment and overlap:

| Env vars | Default models | Used for |
| -------- | -------------- | -------- |
| `OLLAMA_MODEL` / `OLLAMA_MODEL_BACKUP` | `llama3.2:1b` / `qwen2.5:3b` | General dev stack, image evidence helpers, fast paths |
| `ASSESSMENT_OLLAMA_MODEL` / backup | `qwen2.5:7b` / `llama3.1:8b` | Assessment suggestions, discuss/refine chat, overlap LLM |
| `VISION_MODEL` | `llava:7b` | Image evidence descriptions (same as `dev`) |

```env
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_MODEL_BACKUP=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=20

ASSESSMENT_OLLAMA_MODEL=qwen2.5:7b
ASSESSMENT_OLLAMA_MODEL_BACKUP=llama3.1:8b
ASSESSMENT_OLLAMA_TIMEOUT_SECONDS=120

VISION_MODEL=llava:7b
```

`ollama-init` pulls every model listed above. Assessment and overlap code routes through `ollama_client.assessment_models()`; everything else uses `OLLAMA_*`.

Pull or refresh all Ollama weights:

```bash
docker compose -f docker-compose.yml run --rm ollama-init
```

Check what is available:

```bash
curl http://localhost:8000/api/v1/health/ollama
```

Shared client: `backend/app/services/ollama_client.py` (per-call model chain with backup fallback).

## AI detector (RoBERTa)

AI-generated text detection uses a dedicated **ai-detector** container (`Hello-SimpleAI/chatgpt-detector-roberta`), not Ollama. This keeps classification separate from generative tasks and produces more stable segment-level scores.

```env
AI_DETECTOR_URL=http://ai-detector:9001
AI_DETECTOR_MODEL=Hello-SimpleAI/chatgpt-detector-roberta
```

The image is built by `docker compose up --build`. Model weights download automatically on first container start (see [Building containers and pulling models](#building-containers-and-pulling-models)).

---

# Assessment review workflow

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

# Overlap detection

Overlap scanning compares evidence across students in a module group. The review UI supports:

- Side-by-side document comparison with synced scrolling
- Text similarity, paraphrase, and integrity signals (including AI-segment flags from the RoBERTa service)
- Highlighted phrase matching in the detail view

---

# API Endpoints

Base API URL:

- http://localhost:8000/api/v1

Core route groups:

- Health: /health
- Auth: /auth
- Admin: /admin
- Modules: /modules
- Projects: /projects
- Students: /students
- Evidence: /evidence
- Recordings: /recordings

Useful health checks:

- Backend health: http://localhost:8000/api/v1/health
- Ollama health: http://localhost:8000/api/v1/health/ollama

For interactive docs while running locally:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

# Features

## Current Features

- Role-based authentication and profile endpoint
- Module and student management APIs
- Evidence upload, listing, content readback, and supported types endpoint
- Recording workflow with consent, transcription, reminders, extension limits, and auto-purge
- Audit events for sensitive operations
- Overlap detection with detail review UI, integrity signals, and AI-segment highlighting
- Assessment draft workflow: AI suggestions, per-criterion overrides, discuss/refine chat, finalize
- Frontend dashboard, settings, reports, and module workflows

## Planned Features

- Additional reporting and export options
- Further overlap and evidence-matching tuning
- UX polish across module pages

---

# Development

## Recommended VS Code Extensions

- ESLint
- Tailwind CSS IntelliSense
- Prettier
- Error Lens

---

# Git Workflow

Recommended workflow:

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

# CI/CD & OTAP

This project uses GitHub Actions for continuous integration and an OTAP pipeline. All workflows are located in `.github/workflows/`.

## Workflows

### `ci.yml` — Continuous Integration

Runs on **every push** and **every pull request** (all branches).

| Job            | What it does                                                   |
| -------------- | -------------------------------------------------------------- |
| Frontend build | `npm ci` → `npm run build`                                     |
| Backend check  | `pip install -r requirements.txt` → import check on `app.main` |

---

### `otap-develop.yml` — Development (`dev` branch)

Runs on push to `dev`.

1. Runs the CI checks (see above)
2. Builds the Docker images for backend and frontend (`ai-assessment-backend:dev`, `ai-assessment-frontend:dev`)
3. Builds the full stack via `docker compose build`

---

### `otap-test.yml` — Test (`test` branch)

Runs on push to `test`.

1. Runs the CI checks
2. Runs all **backend tests** with pytest + coverage (`backend/tests/`)
3. Runs **frontend tests** if a `test` script is present in `package.json`

---

### `otap-main.yml` — Production (`main` branch)

Runs on push to `main`.

1. Runs the CI checks
2. Automatically generates a version tag (`v<year>.<month>.<day>-<short-sha>`)
3. Generates a changelog based on commits since the last tag
4. Creates a **GitHub Release** with the changelog and commit information

---

## OTAP Branch Strategy

```
feature/* → dev → test → main
```

| Branch | OTAP stage  | Workflow            |
| ------ | ----------- | ------------------- |
| `dev`  | Development | CI + Docker build   |
| `test` | Test        | CI + all tests      |
| `main` | Production  | CI + GitHub Release |

---

# Code Formatting

This project uses Prettier for code formatting. To ensure consistent styling:

1. Install dependencies:

    ```bash
    npm install
    ```

2. Format code manually:

    ```bash
    npm run format
    ```

3. Pre-commit Hook:
   Prettier is enforced on staged files via a pre-commit hook. Ensure you have Husky installed by running:
    ```bash
    npm run prepare
    ```
    This sets up the pre-commit hook to format staged files automatically.

---

# Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_assessment
UPLOAD_DIR=/app/data/uploads
RECORDING_DIR=/app/data/recordings
EXPORT_DIR=/app/data/exports

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_MODEL_BACKUP=qwen2.5:3b

ASSESSMENT_OLLAMA_MODEL=qwen2.5:7b
ASSESSMENT_OLLAMA_MODEL_BACKUP=llama3.1:8b

AI_DETECTOR_URL=http://ai-detector:9001
```

> `.env` is git-ignored. Never commit real credentials — use `.env.example` as the committed template.

---

# Testing

## Backend

Tests are located in `backend/tests/` and use pytest with an in-memory SQLite database — no running services required.

### Run with Docker (recommended)

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

### Run locally (without Docker)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

# Database Migration

Run Alembic inside the backend container.

1. Start services:

    ```bash
    docker compose -f docker-compose.dev.yml up -d --build
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

Use the same commands with docker-compose.yml for non-dev environments.

---

# Contributors

Developed by HBO Informatica students at NHL Stenden.

---

# License

This project is currently intended for educational purposes.
