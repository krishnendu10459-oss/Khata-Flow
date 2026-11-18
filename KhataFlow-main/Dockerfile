# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

# Install system dependencies required for audio/speech libraries (e.g. portaudio, alsa)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libasound2-dev \
    portaudio19-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition
COPY backend/requirements.txt ./backend/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend source code
COPY backend ./backend

# Create directory for persistent SQLite database
RUN mkdir -p /app/data

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/khataflow.db

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/docs || exit 1

# Start FastAPI application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
