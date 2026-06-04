FROM python:3.12-slim AS base

# ffmpeg is required by faster-whisper to decode browser audio (webm/ogg).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 9000

FROM base AS dev
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000", "--reload"]

FROM base AS production
# Single worker: the Whisper model is loaded lazily and held in memory.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
