# ASWA Complete Task & Subtask Outline

## Phase 1: Foundation (Weeks 1-2) ✅ COMPLETED
- **Task 1.1**: Initialize Monorepo Structure
  - 1.1.1: Root Project Configuration (Gradle, Poetry, Makefile)
  - 1.1.2: Shared Java Library (common-java)
  - 1.1.3: Shared Python Library (common-python)
- **Task 1.2**: Database Layer Setup
  - 1.2.1: PostgreSQL Schema and Migrations
  - 1.2.2: Python SQLAlchemy Models and Repositories
- **Task 1.3**: API Gateway Service (Java)
  - 1.3.1: Spring Boot API Gateway Setup
- **Task 1.4**: Docker and Local Development Setup
  - 1.4.1: Docker Configuration

## Phase 2: Ingestion Pipeline (Weeks 3-4) ✅ COMPLETED
- **Task 2.1**: Ingestion Service Core
  - 2.1.1: Create Ingestion Service Structure
  - 2.1.2: Document Processing Pipeline
- **Task 2.2**: Data Source Connectors
  - 2.2.1: Connector Framework
  - 2.2.2: Gmail Connector
  - 2.2.3: Slack Connector
  - 2.2.4: Google Drive Connector
  - 2.2.5: Salesforce Connector
- **Task 2.3**: Vector Store Integration
  - 2.3.1: Qdrant Client Wrapper
  - 2.3.2: Hybrid Search Implementation
- **Task 2.4**: Worker & Scheduling
  - 2.4.1: Background Worker Infrastructure
  - 2.4.2: Prefect Workflow Orchestration

---

## Phase 3: Insight Engine (Weeks 5-6) 🔄 IN PROGRESS

### Task 3.1: Insight Engine Service Setup
- **3.1.1**: Service Structure & API Endpoints
- **3.1.2**: LLM Client Abstraction (Bedrock & Azure OpenAI)

### Task 3.2: Extraction Schemas & Prompts
- **3.2.1**: Pydantic Extraction Models (Entity, Risk, Opportunity, Pattern)
- **3.2.2**: Prompt Templates for Each Extraction Type
- **3.2.3**: Confidence Scoring Logic

### Task 3.3: Extraction Pipeline
- **3.3.1**: Instructor-based Structured Extraction
- **3.3.2**: Map-Reduce for Long Documents
- **3.3.3**: Batch Extraction Service

### Task 3.4: Insight Storage & Relationships
- **3.4.1**: Insight Repository & Deduplication
- **3.4.2**: Entity Relationship Graph Builder
- **3.4.3**: Insight Feedback Loop (User Corrections)

---

## Phase 4: Query Service (Weeks 7-8)

### Task 4.1: Query Service Setup
- **4.1.1**: Service Structure & API Endpoints
- **4.1.2**: Natural Language Query Parser

### Task 4.2: RAG Implementation
- **4.2.1**: Context Retrieval Pipeline
- **4.2.2**: Answer Generation with Citations
- **4.2.3**: Query Caching (Redis)

### Task 4.3: Proactive Insights
- **4.3.1**: Daily/Weekly Digest Generation
- **4.3.2**: Trend Detection Service
- **4.3.3**: Anomaly Detection

---

## Phase 5: Interface Layer (Weeks 9-10)

### Task 5.1: Slack Bot
- **5.1.1**: Bolt Python App Setup
- **5.1.2**: Slash Commands (/aswa search, /aswa insights)
- **5.1.3**: Interactive Messages & Modals
- **5.1.4**: Event Handlers (Message Reactions, Threads)

### Task 5.2: Microsoft Teams Bot (Optional)
- **5.2.1**: Teams Bot Framework Setup
- **5.2.2**: Adaptive Cards for Insights

### Task 5.3: Web Dashboard (Optional)
- **5.3.1**: React + Tailwind Setup
- **5.3.2**: Insights Dashboard Components
- **5.3.3**: Search Interface
- **5.3.4**: Admin Settings Pages

---

## Phase 6: Output Integrations (Weeks 11-12)

### Task 6.1: Integration Service (Java)
- **6.1.1**: Service Structure & API
- **6.1.2**: Webhook Outbound System

### Task 6.2: Jira Integration
- **6.2.1**: Jira Client & Authentication
- **6.2.2**: Create Issues from Insights
- **6.2.3**: Sync Issue Status Back

### Task 6.3: Notification Service
- **6.3.1**: Email Notifications (SMTP/SendGrid)
- **6.3.2**: Slack Notifications
- **6.3.3**: Digest Email Templates

---

## Phase 7: Infrastructure & DevOps (Parallel)

### Task 7.1: Helm Charts
- **7.1.1**: Base Chart Structure
- **7.1.2**: Service-Specific Templates
- **7.1.3**: Values for Dev/Staging/Prod

### Task 7.2: Kubernetes Manifests
- **7.2.1**: Namespace & RBAC
- **7.2.2**: ConfigMaps & Secrets Management
- **7.2.3**: Ingress & Network Policies

### Task 7.3: CI/CD Pipelines
- **7.3.1**: GitHub Actions - Build & Test
- **7.3.2**: GitHub Actions - Docker Build & Push
- **7.3.3**: ArgoCD Application Manifests

### Task 7.4: Observability Stack
- **7.4.1**: Prometheus ServiceMonitors
- **7.4.2**: Grafana Dashboards
- **7.4.3**: Loki Logging Configuration
- **7.4.4**: Alerting Rules

### Task 7.5: Local Development
- **7.5.1**: Docker Compose Full Stack
- **7.5.2**: Skaffold Configuration
- **7.5.3**: Development Scripts

---

## Phase 8: Security & Compliance (Parallel)

### Task 8.1: Authentication & Authorization
- **8.1.1**: JWT Token Service
- **8.1.2**: RBAC Implementation
- **8.1.3**: API Key Management

### Task 8.2: Data Security
- **8.2.1**: Encryption at Rest (Database)
- **8.2.2**: Credentials Encryption Service
- **8.2.3**: PII Detection & Anonymization (Presidio)

### Task 8.3: Audit & Compliance
- **8.3.1**: Audit Log Service
- **8.3.2**: Data Retention Policies
- **8.3.3**: GDPR Data Export/Deletion

---

## Summary: Total Subtasks by Phase

| Phase | Tasks | Subtasks |
|-------|-------|----------|
| Phase 1: Foundation | 4 | 7 |
| Phase 2: Ingestion | 4 | 12 |
| Phase 3: Insight Engine | 4 | 10 |
| Phase 4: Query Service | 3 | 8 |
| Phase 5: Interface Layer | 3 | 10 |
| Phase 6: Output Integrations | 3 | 7 |
| Phase 7: Infrastructure | 5 | 14 |
| Phase 8: Security | 3 | 9 |
| **TOTAL** | **29** | **77** |

---

## Recommended Generation Order

I recommend generating artifacts in this order for logical dependency flow:

1. **Phase 3** (current): 3.1.2 → 3.2.1 → 3.2.2 → 3.2.3 → 3.3.1 → 3.3.2 → 3.3.3 → 3.4.1 → 3.4.2 → 3.4.3
2. **Phase 4**: 4.1.1 → 4.1.2 → 4.2.1 → 4.2.2 → 4.2.3 → 4.3.1 → 4.3.2 → 4.3.3
3. **Phase 5**: 5.1.1 → 5.1.2 → 5.1.3 → 5.1.4 → (5.2, 5.3 optional)
4. **Phase 6**: 6.1.1 → 6.1.2 → 6.2.1 → 6.2.2 → 6.2.3 → 6.3.1 → 6.3.2 → 6.3.3
5. **Phase 7**: 7.1.1 → 7.1.2 → 7.1.3 → 7.2.1 → 7.2.2 → 7.2.3 → 7.3.1 → 7.3.2 → 7.3.3 → 7.4.* → 7.5.*
6. **Phase 8**: 8.1.* → 8.2.* → 8.3.*

---

**Shall I proceed generating artifacts for Phase 3 subtasks in the order listed above?**
