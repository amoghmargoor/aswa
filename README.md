# ASWA - AI-driven Insight Aggregation Platform

**ASWA** (AI-Structured Workplace Analytics) is an enterprise-grade platform that aggregates insights from multiple data sources using advanced AI/LLM capabilities. It provides intelligent pattern detection, relationship mapping, and automated alerting for business intelligence.

## Overview

ASWA connects to various enterprise data sources (email, messaging platforms, document repositories, CRM systems) and uses Large Language Models (LLMs) to extract meaningful insights, detect patterns, identify risks and opportunities, and provide actionable intelligence.

### Key Features

- **Multi-source Data Ingestion**: Connect to Gmail, Outlook, Slack, Microsoft Teams, Google Drive, SharePoint, Salesforce, Zoho, Confluence, Notion, and Zoom
- **AI-Powered Insight Extraction**: Leverages LLMs (Claude, GPT) via AWS Bedrock or Azure OpenAI
- **Vector Search**: Efficient semantic search using Pinecone vector database
- **Real-time Pattern Detection**: Identifies trends, anomalies, risks, and opportunities
- **Entity Relationship Mapping**: Discovers and visualizes connections between insights
- **Customizable Alerts**: Configure notifications based on patterns and conditions
- **Multi-tenant Architecture**: Secure tenant isolation with role-based access control
- **RESTful APIs**: Comprehensive API for integration with existing systems
- **Interactive Slack Bot**: Query insights and receive alerts directly in Slack

## Architecture

ASWA is built as a polyglot microservices architecture using Java and Python:

### Technology Stack

- **Languages**: Java 21, Python 3.11+
- **Frameworks**: Spring Boot 3.2+ (WebFlux), FastAPI, SQLAlchemy 2.0
- **Databases**: PostgreSQL 16 (relational), Pinecone (vector), Redis (caching)
- **AI/LLM**: AWS Bedrock (Claude), Azure OpenAI
- **Messaging**: Redis Streams / Kafka (async processing)
- **Observability**: Prometheus, Grafana, structured logging
- **Orchestration**: Kubernetes 1.28+, Helm 3.x
- **CI/CD**: GitHub Actions

### Service Architecture

```
┌─────────────┐
│  API Gateway│  (Java/Spring Boot)
│  + Auth     │
└──────┬──────┘
       │
       ├──────┬──────────┬────────────┬─────────────┐
       │      │          │            │             │
  ┌────▼──┐ ┌▼────────┐ ┌▼──────────┐ ┌▼────────┐ ┌▼──────────┐
  │Ingestion│ │Insight  │ │Query      │ │Notif.   │ │Integration│
  │Service  │ │Engine   │ │Service    │ │Service  │ │Service    │
  │(Python) │ │(Python) │ │(Python)   │ │(Java)   │ │(Java)     │
  └────┬────┘ └─────────┘ └───────────┘ └─────────┘ └───────────┘
       │
  ┌────▼────────────┐
  │Background Workers│
  │- Doc Processor  │
  │- Pattern Analyzer│
  │(Python)         │
  └─────────────────┘
```

### Monorepo Structure

```
aswa/
├── libs/                       # Shared libraries
│   ├── common-java/            # Java utilities, exceptions, models
│   └── common-python/          # Python utilities, models, clients
├── services/                   # Microservices
│   ├── api-gateway/            # Java - REST API & authentication
│   ├── ingestion-service/      # Python - Data source connectors
│   ├── insight-engine/         # Python - LLM-powered insight extraction
│   ├── query-service/          # Python - Search & retrieval
│   ├── notification-service/   # Java - Alerts & notifications
│   ├── integration-service/    # Java - External integrations
│   └── slack-bot/              # Python - Slack integration
├── workers/                    # Background workers
│   ├── document-processor/     # Python - Document parsing & chunking
│   └── pattern-analyzer/       # Python - Pattern detection
├── infrastructure/             # Deployment configuration
│   ├── helm/                   # Helm charts
│   ├── docker/                 # Dockerfiles
│   └── k8s/                    # Kubernetes manifests
├── migrations/postgresql/      # Database migrations (Flyway)
└── scripts/                    # Utility scripts
```

## Prerequisites

Before you begin, ensure you have the following installed:

- **Java 21** (OpenJDK or Eclipse Temurin recommended)
- **Python 3.11+** with Poetry package manager
- **Docker 24+** and Docker Compose
- **Kubernetes 1.28+** (for production deployment)
- **Helm 3.x** (for Kubernetes deployments)
- **Make** (build automation)

### Optional Tools

- **kubectl** - Kubernetes CLI
- **k9s** - Kubernetes TUI
- **Gradle 8.5+** (included via wrapper)
- **PostgreSQL 16** client tools

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/aswa.git
cd aswa
```

### 2. Install Dependencies

```bash
make setup
```

This will:
- Install Poetry (if not already installed)
- Install Python dependencies
- Set up pre-commit hooks

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start Local Infrastructure

```bash
make dev-up
```

This starts PostgreSQL, Redis, and other required services via Docker Compose.

### 5. Run Database Migrations

```bash
./scripts/db-migrate.sh migrate dev
```

### 6. Build All Services

```bash
make build
```

### 7. Run Tests

```bash
make test
```

## Development Workflow

### Building Services

```bash
# Build everything
make build

# Build Java services only
./gradlew build

# Build Python services only
poetry build
```

### Running Tests

```bash
# Run all tests
make test

# Run Java tests only
make test-java

# Run Python tests only
make test-python

# Run tests with coverage
make test  # Coverage reports in htmlcov/ and build/reports/
```

### Code Quality

```bash
# Format all code
make format

# Run linters
make lint

# Run pre-commit hooks manually
poetry run pre-commit run --all-files
```

### Local Development Environment

```bash
# Start all services
make dev-up

# View logs
make dev-logs

# Stop all services
make dev-down
```

## Configuration

ASWA follows the [12-factor app](https://12factor.net/) methodology and uses environment variables for configuration.

### Key Environment Variables

See `.env.example` for a complete list. Key variables include:

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL connection
- `REDIS_HOST`, `REDIS_PORT` - Redis connection
- `LLM_PROVIDER` - AI provider (`bedrock` or `azure_openai`)
- `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT` - Vector database
- `JWT_SECRET` - Authentication secret
- `LOG_LEVEL` - Logging level

## Deployment

### Docker

```bash
# Build Docker images
make docker-build

# Push to registry
export DOCKER_REGISTRY=your-registry.com
make docker-push
```

### Kubernetes with Helm

```bash
# Lint Helm charts
make helm-lint

# Install to cluster
helm install aswa infrastructure/helm/aswa \
  --namespace aswa \
  --create-namespace \
  --values infrastructure/helm/aswa/values-prod.yaml
```

## API Documentation

Once the API Gateway is running, access the interactive API documentation at:

- **Swagger UI**: `http://localhost:8080/swagger-ui.html`
- **OpenAPI Spec**: `http://localhost:8080/v3/api-docs`

## Monitoring and Observability

- **Health Check**: `GET /actuator/health`
- **Readiness Check**: `GET /ready`
- **Metrics (Prometheus)**: `GET /actuator/prometheus`
- **Logs**: Structured JSON logs with request tracing

## Testing

### Unit Tests

```bash
# Java
./gradlew test

# Python
poetry run pytest
```

### Integration Tests

```bash
# Java (uses Testcontainers)
./gradlew integrationTest

# Python (uses Testcontainers)
poetry run pytest tests/integration/
```

### Coverage Requirements

- **Java**: 80% minimum (enforced by JaCoCo)
- **Python**: 80% minimum (enforced by pytest-cov)

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and commit: `git commit -m "Add my feature"`
3. Ensure tests pass: `make test`
4. Ensure code is formatted: `make format`
5. Push and create a pull request

### Code Style

- **Java**: Google Java Format (enforced by Spotless)
- **Python**: Black (line length 100) + Ruff

## Project Structure

### Shared Libraries

- **common-java**: Exception handling, models, utilities, logging, resilience patterns
- **common-python**: Exception handling, Pydantic models, settings, HTTP clients, metrics

### Services

- **api-gateway**: RESTful API, JWT authentication, request routing
- **ingestion-service**: Data source connectors, OAuth flows, incremental sync
- **insight-engine**: LLM integration, prompt engineering, insight extraction
- **query-service**: Vector search, full-text search, filtering
- **notification-service**: Email, Slack, webhook notifications
- **integration-service**: External API integrations (Salesforce, Zoho, etc.)
- **slack-bot**: Interactive Slack bot for queries and alerts

### Workers

- **document-processor**: Document parsing, chunking, embedding generation
- **pattern-analyzer**: Time-series analysis, anomaly detection, trend identification

## Troubleshooting

### Common Issues

**Build Failures**
```bash
# Clean and rebuild
make clean
make build
```

**Test Failures**
```bash
# Ensure test infrastructure is running
make dev-up

# Run tests with verbose output
./gradlew test --info
poetry run pytest -vv
```

**Database Connection Issues**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Verify connection
psql -h localhost -U aswa -d aswa
```

## License

Proprietary - All Rights Reserved

## Support

For issues, questions, or contributions, please contact the ASWA development team.

---

**Built with ❤️ by the ASWA Team**
