# ── Stage 1: сборка зависимостей ──
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.docker.txt


# ── Stage 2: финальный образ ──
FROM python:3.11-slim

WORKDIR /app

# Только runtime зависимость для psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копируем только собранные пакеты из builder
COPY --from=builder /install /usr/local

COPY src/ ./src/
COPY static/ ./static/

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]