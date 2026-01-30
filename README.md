# ASWA - AI-Powered Smart Workspace Assistant

<p align="center">
  <strong>Enterprise AI platform for intelligent document processing, insights extraction, and autonomous agents</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#deployment">Deployment</a>
</p>

---

## Overview

**ASWA** (AI-Powered Smart Workspace Assistant) is an enterprise-grade platform that connects to your business data sources, extracts actionable insights using AI/LLM, and enables autonomous AI agents to take actions on your behalf.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   📄 Documents    →    🤖 AI Processing    →    💡 Insights & Actions   │
│   📧 Emails            • Extract insights       • Smart alerts          │
│   💬 Messages          • Find patterns          • Auto-responses        │
│   📁 Files             • Build knowledge        • Task automation       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Docker Desktop 4.x+ (8GB RAM allocated)
- Git

### One-Command Setup

```bash
# Clone and start
git clone <repo-url> && cd aswa
./scripts/dev.sh setup
./scripts/dev.sh up

# Open dashboard
open http://localhost:3000
```

### Add Your API Keys

```bash
# Edit environment file
vi infrastructure/docker/.env

# Add at minimum:
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
```

📖 **Full setup guide**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

---

## Features

### 🔌 Data Connectors
Connect to 15+ enterprise data sources:

| Category | Integrations |
|----------|-------------|
| **Email** | Gmail, Outlook, Microsoft 365 |
| **Messaging** | Slack, Microsoft Teams |
| **Documents** | Google Drive, SharePoint, Confluence, Notion |
| **CRM** | Salesforce, Zoho, HubSpot |
| **Meetings** | Zoom (transcripts) |

### 🧠 AI-Powered Insights
- **Semantic Search**: Natural language queries across all your data
- **Pattern Detection**: Identify trends, anomalies, and opportunities
- **Relationship Mapping**: Discover connections between entities
- **Summarization**: Auto-generate briefs and reports

### 🤖 AI Agent Platform (Phase 9)
Build and deploy autonomous AI agents:

- **Visual Agent Builder**: Drag-and-drop workflow design
- **Action Blocks**: Pre-built integrations (API, database, notifications)
- **Approval Workflows**: Human-in-the-loop for sensitive actions
- **Triggers**: Schedule, webhook, email, Slack-based activation
- **Templates**: Start from pre-built agent templates

### 🔔 Smart Notifications
- **Multi-channel**: Email, Slack, Teams, webhooks
- **Conditional Alerts**: Rule-based triggers
- **Digests**: Daily/weekly summaries

### 🔐 Enterprise Security
- **Multi-tenant**: Complete data isolation
- **SSO/SAML**: Enterprise authentication
- **RBAC**: Role-based access control
- **Audit Logging**: Complete activity trail
- **Encryption**: At-rest and in-transit

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ASWA PLATFORM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌──────────────┐                                  │
│                           │   Users &    │                                  │
│                           │   Systems    │                                  │
│                           └──────┬───────┘                                  │
│                                  │                                          │
│   ┌──────────────────────────────┼──────────────────────────────────┐       │
│   │                     INTERFACE LAYER                              │       │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │       │
│   │  │   Web    │  │   API    │  │  Slack   │  │  Teams   │        │       │
│   │  │Dashboard │  │ Gateway  │  │   Bot    │  │   Bot    │        │       │
│   │  │  React   │  │  Spring  │  │  Python  │  │  Python  │        │       │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │       │
│   └──────────────────────────────┬──────────────────────────────────┘       │
│                                  │                                          │
│   ┌──────────────────────────────┼──────────────────────────────────┐       │
│   │                     SERVICE LAYER                                │       │
│   │                                                                   │       │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │       │
│   │  │Ingestion │  │  Query   │  │ Insight  │  │  Agent   │        │       │
│   │  │ Service  │  │ Service  │  │  Engine  │  │ Service  │        │       │
│   │  │  :8001   │  │  :8002   │  │  :8003   │  │  :8090   │        │       │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │       │
│   │                                                                   │       │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │       │
│   │  │ Notify   │  │Integrate │  │ Connector│                       │       │
│   │  │ Service  │  │ Service  │  │ Service  │                       │       │
│   │  │  :8005   │  │  :8004   │  │          │                       │       │
│   │  └──────────┘  └──────────┘  └──────────┘                       │       │
│   └──────────────────────────────┬──────────────────────────────────┘       │
│                                  │                                          │
│   ┌──────────────────────────────┼──────────────────────────────────┐       │
│   │                      DATA LAYER                                  │       │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │       │
│   │  │PostgreSQL│  │  Redis   │  │  Vector  │  │Elasticsrch│       │       │
│   │  │          │  │          │  │   DB     │  │          │        │       │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │       │
│   │                                                                   │       │
│   │  ┌──────────┐  ┌──────────┐                                     │       │
│   │  │   S3/    │  │  Jaeger  │                                     │       │
│   │  │  MinIO   │  │ Tracing  │                                     │       │
│   │  └──────────┘  └──────────┘                                     │       │
│   └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, TanStack Query |
| **API Gateway** | Java 21, Spring Boot 3.2, WebFlux |
| **Services** | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic |
| **AI/LLM** | OpenAI, Anthropic Claude, AWS Bedrock |
| **Vector DB** | Qdrant (dev), Pinecone (prod) |
| **Database** | PostgreSQL 16, Redis 7, Elasticsearch 8 |
| **Storage** | MinIO (dev), AWS S3 (prod) |
| **Orchestration** | Kubernetes 1.28+, Helm 3.x |
| **CI/CD** | GitHub Actions |
| **Observability** | Prometheus, Grafana, Jaeger, Loki |

### Services Overview

| Service | Tech | Port | Purpose |
|---------|------|------|---------|
| **API Gateway** | Java/Spring | 8080 | Auth, routing, rate limiting |
| **Web Dashboard** | React/Vite | 3000 | User interface |
| **Ingestion Service** | Python/FastAPI | 8001 | Document processing, embeddings |
| **Query Service** | Python/FastAPI | 8002 | LLM-powered search |
| **Insight Engine** | Python/FastAPI | 8003 | Pattern detection, analytics |
| **Agent Service** | Python/FastAPI | 8090 | AI agent orchestration |
| **Notification Service** | Python/FastAPI | 8005 | Multi-channel notifications |
| **Integration Service** | Python/FastAPI | 8004 | Third-party connectors |
| **Slack Bot** | Python | 8086 | Slack integration |
| **Teams Bot** | Python | 8087 | Teams integration |

---

## Project Structure

```
aswa/
├── services/                    # Microservices
│   ├── api-gateway/             # Java - REST API & authentication
│   ├── web-dashboard/           # React - User interface
│   ├── ingestion-service/       # Python - Document processing
│   ├── query-service/           # Python - LLM search
│   ├── insight-service/         # Python - Pattern detection
│   ├── agent-service/           # Python - AI agents (Phase 9)
│   ├── notification-service/    # Python - Alerts
│   ├── integration-service/     # Python - Connectors
│   ├── slack-bot/               # Python - Slack integration
│   └── teams-bot/               # Python - Teams integration
│
├── libs/                        # Shared libraries
│   ├── common-java/             # Java utilities
│   └── common-python/           # Python utilities
│
├── workers/                     # Background workers
│   └── document-processor/      # Async document processing
│
├── infrastructure/              # Deployment
│   ├── docker/                  # Docker Compose files
│   ├── helm/                    # Helm charts
│   ├── kubernetes/              # K8s manifests
│   └── terraform/               # Infrastructure as Code
│
├── migrations/                  # Database migrations
│   └── postgresql/              # Flyway migrations
│
├── prompts/                     # AI prompt templates
│   └── phase9/                  # Agent platform prompts
│
├── scripts/                     # Utility scripts
│   ├── dev.sh                   # Development manager
│   └── db-migrate.sh            # Database migrations
│
├── docs/                        # Documentation
│   ├── DEPLOYMENT_GUIDE.md      # Production deployment
│   └── DEVELOPMENT.md           # Developer guide
│
└── .github/                     # CI/CD
    └── workflows/               # GitHub Actions
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [**DEVELOPMENT.md**](docs/DEVELOPMENT.md) | Developer quick start, running locally |
| [**DEPLOYMENT_GUIDE.md**](docs/DEPLOYMENT_GUIDE.md) | Production deployment (SaaS & On-Prem) |
| [**ArchitectureAndDesign.md**](ArchitectureAndDesign.md) | Detailed architecture documentation |

---

## Deployment

### Development (Mac/Linux)

```bash
./scripts/dev.sh up      # Start all services
./scripts/dev.sh status  # Check status
./scripts/dev.sh logs    # View logs
./scripts/dev.sh down    # Stop services
```

### Staging/Production

```bash
# Using Helm
helm upgrade --install aswa ./infrastructure/helm/charts/aswa \
  --namespace aswa-prod \
  --values values-prod.yaml
```

### Deployment Options

| Environment | Method | Guide |
|-------------|--------|-------|
| **Local Dev** | Docker Compose | [DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| **AWS (SaaS)** | EKS + Helm | [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md#saas-deployment-aws) |
| **On-Premises** | K8s + Helm | [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md#on-premises-deployment) |

---

## Development

### Prerequisites

| Tool | Version | Required |
|------|---------|----------|
| Docker Desktop | 4.x+ | ✅ |
| Git | 2.x+ | ✅ |
| Python | 3.11+ | Optional (for native dev) |
| Node.js | 20+ | Optional (for native dev) |
| Java | 21+ | Optional (for native dev) |

### Common Commands

```bash
# Development
./scripts/dev.sh up              # Start services
./scripts/dev.sh logs <service>  # View logs
./scripts/dev.sh shell postgres  # Database shell

# Database
./scripts/dev.sh db migrate      # Run migrations
./scripts/dev.sh db seed         # Seed test data

# Testing
./scripts/dev.sh test all        # Run all tests
./scripts/dev.sh test ingestion  # Test specific service
```

### Running Tests

```bash
# All services
./scripts/dev.sh test all

# Specific service
cd services/ingestion-service
poetry run pytest tests/ -v

# With coverage
poetry run pytest tests/ --cov=src --cov-report=html
```

---

## API Reference

### Base URLs

| Environment | URL |
|-------------|-----|
| Local | http://localhost:8000 |
| Staging | https://api.staging.aswa.io |
| Production | https://api.aswa.io |

### Key Endpoints

```bash
# Health check
GET /api/v1/health

# Documents
POST /api/v1/documents/upload
GET  /api/v1/documents/{id}

# Query
POST /api/v1/query
GET  /api/v1/search?q=...

# Agents (Phase 9)
GET  /api/v1/agents
POST /api/v1/agents
POST /api/v1/agents/{id}/execute

# Webhooks
POST /api/v1/webhooks/subscriptions
```

📖 **Full API docs**: http://localhost:8000/docs (Swagger UI)

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`./scripts/dev.sh test all`)
5. Commit (`git commit -m 'Add amazing feature'`)
6. Push (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## License

Proprietary - All Rights Reserved

---

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/aswa/issues)
- **Documentation**: [docs/](docs/)
- **Slack**: #aswa-support
