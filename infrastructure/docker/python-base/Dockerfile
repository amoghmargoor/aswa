# Base image for Python services
FROM python:3.11-slim AS base

# Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s $POETRY_HOME/bin/poetry /usr/local/bin/poetry

# Verify Poetry installation
RUN poetry --version

WORKDIR /app

# Builder stage - installs dependencies
FROM base AS builder

# Copy poetry files
COPY libs/common-python/pyproject.toml libs/common-python/poetry.lock libs/common-python/

# Install dependencies
WORKDIR /app/libs/common-python
RUN poetry install --no-root --only main

# Copy source code
COPY libs/common-python/src libs/common-python/src

# Install the package
RUN poetry install --only main

# Runtime stage
FROM python:3.11-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r aswa && useradd -r -g aswa aswa

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/libs/common-python/.venv /app/.venv

# Copy source code
COPY --from=builder /app/libs/common-python /app/libs/common-python

# Set PATH to use virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/libs/common-python/src:$PYTHONPATH"

# Switch to non-root user
USER aswa

# Default command
CMD ["python", "--version"]
