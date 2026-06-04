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
│   │   ├── models/            # SQLAlchemy models
│   │   ├── routes/            # API route handlers
│   │   └── services/          # Business logic
│   ├── Dockerfile
│   └── requirements.txt
│
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

Starts all services with hot-reload for the frontend and pgAdmin for database management:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

| Service  | URL                   |
| -------- | --------------------- |
| Frontend | http://localhost:3000 |
| Backend  | http://localhost:8000 |
| pgAdmin  | http://localhost:5050 |

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
docker compose up -d --build
```

---

# Features

## Current Features

- Next.js project setup
- Tailwind CSS integration
- ESLint configuration
- App Router structure

## Planned Features

- Authentication system
- Module management
- Project management
- Student and group management
- File uploads
- Assessment dashboard
- AI-supported assessment assistance
- Rubric integration
- Contribution analysis
- Reporting and export functionality

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
