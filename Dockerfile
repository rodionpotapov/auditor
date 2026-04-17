FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для psycopg2 и scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Зависимости
COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt

# Код приложения
COPY src/ ./src/
COPY static/ ./static/

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]