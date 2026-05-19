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

- React 19
- Next.js 16 (App Router)
- JavaScript
- Tailwind CSS 4
- ESLint

## Backend

- Python
- FastAPI
- SQLAlchemy 2 (ORM)
- Alembic (migrations)
- PostgreSQL 16

## Infrastructure

- Docker & Docker Compose
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

Copy the backend environment template:

```bash
cp backend/.env.example backend/.env
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
