# ASWA Insight Engine

LLM-powered insight extraction service for the ASWA platform.

## Overview

The Insight Engine service uses large language models (LLMs) to extract structured insights from documents. It supports multiple types of insights:

- **Entities**: Named entities like people, organizations, locations, technologies
- **Risks**: Business risks with severity, likelihood, and mitigation strategies
- **Opportunities**: Business opportunities with impact and effort assessments
- **Patterns**: Trends, correlations, anomalies, and other data patterns

## Features

- Multi-provider LLM support (OpenAI, Azure OpenAI, AWS Bedrock)
- Structured extraction using Pydantic models and instructor
- Comprehensive validation and confidence scoring
- RESTful API with FastAPI
- Async/await support throughout
- Observability with Prometheus metrics

## Installation

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov
```

## Running the Service

```bash
# Development mode
poetry run uvicorn aswa_insight.main:app --reload

# Production mode
poetry run insight-engine
```

## Configuration

Set environment variables or use a `.env` file:

```bash
# LLM Configuration
LLM_PROVIDER=openai  # or azure, bedrock
OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com
AWS_REGION=us-east-1

# Service Configuration
LOG_LEVEL=info
REDIS_URL=redis://localhost:6379
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

```bash
# Run linting
poetry run ruff check .

# Format code
poetry run black .

# Type checking
poetry run mypy .
```

## Architecture

The service follows a clean architecture pattern:

```
src/aswa_insight/
├── models/          # Pydantic models for insights
├── llm/             # LLM client abstractions
├── services/        # Business logic
├── api/             # FastAPI routes
├── config.py        # Configuration management
└── main.py          # Application entry point
```

## License

Proprietary - ASWA Platform
