# AI Assessment Platform

An AI-supported assessment platform designed for educational institutions to assist with the evaluation of student group projects.

## Project Overview

This project is being developed as part of an Informatica HBO project at NHL Stenden.

The platform aims to support teachers and assessors by:

- Managing modules and projects
- Managing students and groups
- Uploading and managing assessment-related documents
- Supporting assessment workflows
- Assisting with AI-supported individual contribution analysis
- Improving consistency and efficiency within group assessments

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
│   ├── .env.example           # Environment variable template
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-compose.yml         # Base stack
├── docker-compose.override.yml# Auto-loaded dev overrides (pgAdmin, hot-reload)
├── docker-compose.dev.yml     # Legacy dev compose file
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

Copy the root environment template:

```bash
cp .env.example .env
```

The default values in `.env` work out of the box with Docker Compose. Edit the file if you need custom credentials.

---

# Running the Project

## Development

Starts all services with hot-reload for the frontend and pgAdmin for database management:

```bash
docker compose up -d
```

| Service  | URL                   |
| -------- | --------------------- |
| Frontend | http://localhost:3000 |
| Backend  | http://localhost:8000 |
| pgAdmin  | http://localhost:5050 |

**pgAdmin login:** `admin@admin.com` / `admin`
Connect to the database using host `postgres`, port `5432`, database `ai_assessment`, user `postgres`, password `postgres`.

## Production

```bash
docker compose -f docker-compose.yml up -d
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

Copy `backend/.env.example` to `backend/.env` and adjust as needed:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_assessment
UPLOAD_DIR=/app/data/uploads
RECORDING_DIR=/app/data/recordings
EXPORT_DIR=/app/data/exports
```

> `backend/.env` is git-ignored. Never commit real credentials — use `backend/.env.example` as the committed template.

---

# Testing

## Backend

Tests are in [`test/`](test/README.md): pytest (in-memory SQLite for auth), plus optional live smoke against Docker.

### Run with Docker (recommended)

With the dev stack already running:

```bash
docker exec backend python -m pytest tests/ -v
```

If the stack is not running:

```bash
docker compose run --rm backend python -m pytest tests/ -v
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
    docker compose up -d
    ```

2. Create a new migration after model changes:

    ```bash
    docker compose exec backend alembic revision --autogenerate -m "describe change"
    ```

3. Upgrade to the latest revision:

    ```bash
    docker compose exec backend alembic upgrade head
    ```

4. Check the current revision:

    ```bash
    docker compose exec backend alembic current -v
    ```

5. Downgrade one revision:

    ```bash
    docker compose exec backend alembic downgrade -1
    ```

6. View migration history:

    ```bash
    docker compose exec backend alembic history --indicate-current
    ```

Use the same commands with docker-compose.yml for non-dev environments.

---

# Contributors

Developed by HBO Informatica students at NHL Stenden.

---

# License

This project is currently intended for educational purposes.
