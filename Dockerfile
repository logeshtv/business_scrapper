# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir "poetry==1.8.3" \
    && poetry export --without-hashes --format=requirements.txt -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt \
    && pip uninstall -y poetry

COPY app app
COPY prisma prisma
COPY README.md README.md

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
