FROM python:3.12-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 9001

FROM base AS dev
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9001", "--reload"]

FROM base AS production
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9001"]
