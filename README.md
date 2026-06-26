# AI Assessment Platform

An on-premise AI-assisted platform for assessing student work in module-based education.

## Overview

The platform supports teachers and assessors by:

- Managing modules, module groups, and students
- Uploading and managing evidence and module documents
- Running assessment workflows with per-student scoring and feedback
- Recording assessments with consent, retention, and audit trails
- Using local AI support for evidence analysis and overlap detection
- Improving consistency and speed of individual contribution assessment

All AI inference runs on-premise inside Docker — nothing is sent to external APIs.

> For contributor and developer documentation see [DEVELOPMENT.md](DEVELOPMENT.md).

---

## Prerequisites

Before you begin, install the following on the host machine:

| Requirement | Notes |
| ----------- | ----- |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Includes Docker Compose |
| Git | For cloning the repository |

No other local dependencies (Node, Python, etc.) are required — everything runs inside Docker.

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ai-assessment-platform
```

### 2. Create your environment file

```bash
cp .env.example .env
```

The defaults in `.env` work out of the box with Docker Compose. You do not need to change anything for a standard installation. Edit the file only if you need custom database credentials or ports.

**Optional — GPU acceleration for Ollama:**
Set `USE_GPU=1` in `.env` to enable the NVIDIA GPU override. Leave it blank (default) for CPU-only mode.

### 3. Build and start all services

```bash
docker compose -f docker-compose.yml up -d --build
```

This builds and starts the frontend, backend, database, Ollama, AI detector, and STT services. The first build takes several minutes.

The backend automatically applies database migrations on startup — no manual migration step is needed.

### 4. Pull the AI language models

Container images and model weights are separate. After the `ollama` service is running, pull all configured models:

```bash
docker compose -f docker-compose.yml run --rm ollama-init
```

This pulls the general, assessment, and vision models (~10 GB total on a fresh install). This step is only needed once; weights are stored in the `ollama_data` Docker volume and reused on subsequent starts.

### 5. Wait for the AI detector to be ready

The AI-text classifier (`ai-detector`) downloads its model from Hugging Face on first boot (~1–2 GB). Check when it is ready:

```bash
curl http://localhost:9001/health
```

On a fresh install this can take up to 3 minutes. Subsequent starts use the cached `ai_detector_cache` volume and are nearly instant.

### 6. Verify the stack

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/ollama
curl http://localhost:9001/health
```

All three should return a healthy status before using the platform.

---

## Accessing the Platform

Once all services are running and healthy, open the platform in your browser:

| Service | URL |
| ------- | --- |
| **Platform (Frontend)** | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| STT API | http://localhost:9000 |
| AI Detector | http://localhost:9001 |
| Ollama | http://localhost:11434 |

---

## Stopping the Platform

```bash
docker compose down
```

This stops all containers. Your database and uploaded files are preserved in Docker volumes and will be available when you start again.

To stop and remove all data (full reset):

```bash
docker compose down -v
```

---

## Updating

Pull the latest code and rebuild:

```bash
git pull
docker compose -f docker-compose.yml up -d --build
```

Migrations are applied automatically on startup. If new AI models have been added, re-run the model pull step:

```bash
docker compose -f docker-compose.yml run --rm ollama-init
```

---

## Troubleshooting

**Services are not starting**
Run `docker compose logs <service-name>` (e.g. `docker compose logs backend`) to inspect errors.

**Ollama health check fails**
Wait a moment for the service to finish loading, then retry. On first boot the model pull can take several minutes.

**AI Detector is not ready**
Check `docker compose logs ai-detector`. The Hugging Face download requires an internet connection on first boot.

**Port conflict**
If a port is already in use on your machine, edit `.env` to remap the conflicting port, or stop the conflicting process.

---

## Contributors

Developed by HBO Informatica students at NHL Stenden.

## License

This project is currently intended for educational purposes.
