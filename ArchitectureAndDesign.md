# ASWA Architecture and Design

A comprehensive technical architecture document for the ASWA (AI-Powered Smart Workspace Assistant) platform.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Service Architecture](#service-architecture)
4. [Data Architecture](#data-architecture)
5. [AI/LLM Architecture](#aillm-architecture)
6. [Agent Platform Architecture](#agent-platform-architecture)
7. [Security Architecture](#security-architecture)
8. [Integration Architecture](#integration-architecture)
9. [Deployment Architecture](#deployment-architecture)
10. [Observability Architecture](#observability-architecture)
11. [Design Decisions](#design-decisions)

---

## Executive Summary

ASWA is an enterprise AI platform built on a microservices architecture that provides:

- **Document Intelligence**: Ingest, process, and extract insights from enterprise documents
- **Semantic Search**: Natural language queries powered by LLMs and vector databases
- **Pattern Detection**: Automated identification of trends, risks, and opportunities
- **AI Agents**: Autonomous agents that can take actions based on triggers and workflows
- **Multi-tenant SaaS**: Secure, isolated environments for multiple organizations

### Key Architectural Principles

| Principle | Implementation |
|-----------|----------------|
| **Microservices** | 10+ independently deployable services |
| **Polyglot** | Java for API Gateway, Python for AI services |
| **Event-Driven** | Async processing via Redis/message queues |
| **Cloud-Native** | Kubernetes, Helm, containerized workloads |
| **AI-First** | LLM integration at core, vector search, embeddings |
| **Secure by Default** | Multi-tenant isolation, encryption, RBAC |

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 CLIENTS                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Browser   │  │  Slack App  │  │ Teams App   │  │  API Client │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            INGRESS LAYER                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Load Balancer / Ingress Controller                    │    │
│  │                    (AWS ALB / NGINX / Traefik)                           │    │
│  │  • TLS Termination  • Rate Limiting  • WAF  • Geographic Routing        │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INTERFACE LAYER                                        │
│                                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │
│  │   Web Dashboard  │  │   API Gateway    │  │   Bot Services   │              │
│  │                  │  │                  │  │                  │              │
│  │  • React 18      │  │  • Spring Boot   │  │  • Slack Bot     │              │
│  │  • TypeScript    │  │  • JWT Auth      │  │  • Teams Bot     │              │
│  │  • Vite          │  │  • Rate Limiting │  │  • Webhooks      │              │
│  │  • TailwindCSS   │  │  • API Routing   │  │                  │              │
│  │                  │  │  • OpenAPI       │  │                  │              │
│  │  Port: 3000      │  │  Port: 8080      │  │  Port: 8086-87   │              │
│  └──────────────────┘  └────────┬─────────┘  └──────────────────┘              │
│                                 │                                               │
└─────────────────────────────────┼───────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER                                          │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         CORE SERVICES                                    │    │
│  │                                                                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │    │
│  │  │  Ingestion   │  │    Query     │  │   Insight    │  │    Agent     │ │    │
│  │  │   Service    │  │   Service    │  │    Engine    │  │   Service    │ │    │
│  │  │              │  │              │  │              │  │              │ │    │
│  │  │ • Upload     │  │ • Search     │  │ • Patterns   │  │ • Agents     │ │    │
│  │  │ • Parse      │  │ • LLM Query  │  │ • Trends     │  │ • Actions    │ │    │
│  │  │ • Chunk      │  │ • RAG        │  │ • Anomalies  │  │ • Triggers   │ │    │
│  │  │ • Embed      │  │ • Summarize  │  │ • Relations  │  │ • Workflows  │ │    │
│  │  │              │  │              │  │              │  │              │ │    │
│  │  │ Port: 8001   │  │ Port: 8002   │  │ Port: 8003   │  │ Port: 8090   │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                       SUPPORT SERVICES                                   │    │
│  │                                                                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │    │
│  │  │ Notification │  │ Integration  │  │  Connector   │                   │    │
│  │  │   Service    │  │   Service    │  │   Service    │                   │    │
│  │  │              │  │              │  │              │                   │    │
│  │  │ • Email      │  │ • OAuth      │  │ • Gmail      │                   │    │
│  │  │ • Slack      │  │ • Webhooks   │  │ • Outlook    │                   │    │
│  │  │ • Teams      │  │ • Sync       │  │ • Drive      │                   │    │
│  │  │ • Push       │  │              │  │ • Salesforce │                   │    │
│  │  │              │  │              │  │ • Slack      │                   │    │
│  │  │ Port: 8005   │  │ Port: 8004   │  │              │                   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      BACKGROUND WORKERS                                  │    │
│  │                                                                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │    │
│  │  │  Document    │  │   Pattern    │  │   Scheduled  │                   │    │
│  │  │  Processor   │  │   Analyzer   │  │    Tasks     │                   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                            │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  PostgreSQL  │  │    Redis     │  │  Vector DB   │  │Elasticsearch │        │
│  │              │  │              │  │              │  │              │        │
│  │ • Users      │  │ • Cache      │  │ • Embeddings │  │ • Full-text  │        │
│  │ • Tenants    │  │ • Sessions   │  │ • Similarity │  │ • Analytics  │        │
│  │ • Documents  │  │ • Queues     │  │ • RAG        │  │ • Logs       │        │
│  │ • Insights   │  │ • Pub/Sub    │  │              │  │              │        │
│  │ • Agents     │  │              │  │ Qdrant/      │  │              │        │
│  │ • Audit      │  │              │  │ Pinecone     │  │              │        │
│  │              │  │              │  │              │  │              │        │
│  │ Port: 5432   │  │ Port: 6379   │  │ Port: 6333   │  │ Port: 9200   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐                                             │
│  │   S3/MinIO   │  │    Jaeger    │                                             │
│  │              │  │              │                                             │
│  │ • Documents  │  │ • Traces     │                                             │
│  │ • Exports    │  │ • Spans      │                                             │
│  │ • Backups    │  │              │                                             │
│  │              │  │              │                                             │
│  │ Port: 9000   │  │ Port: 16686  │                                             │
│  └──────────────┘  └──────────────┘                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           REQUEST FLOW EXAMPLE                                  │
│                        "Search for Q4 sales insights"                           │
└────────────────────────────────────────────────────────────────────────────────┘

User                API Gateway         Query Service       Vector DB        LLM
 │                      │                    │                  │              │
 │  POST /query         │                    │                  │              │
 │  "Q4 sales insights" │                    │                  │              │
 │─────────────────────▶│                    │                  │              │
 │                      │                    │                  │              │
 │                      │  Validate JWT      │                  │              │
 │                      │  Check Rate Limit  │                  │              │
 │                      │  Get Tenant ID     │                  │              │
 │                      │                    │                  │              │
 │                      │  Forward Request   │                  │              │
 │                      │───────────────────▶│                  │              │
 │                      │                    │                  │              │
 │                      │                    │  Embed Query     │              │
 │                      │                    │─────────────────▶│              │
 │                      │                    │                  │              │
 │                      │                    │  Similar Vectors │              │
 │                      │                    │◀─────────────────│              │
 │                      │                    │                  │              │
 │                      │                    │  Build Context + Prompt         │
 │                      │                    │─────────────────────────────────▶
 │                      │                    │                  │              │
 │                      │                    │  Generated Response              │
 │                      │                    │◀─────────────────────────────────
 │                      │                    │                  │              │
 │                      │  JSON Response     │                  │              │
 │                      │◀───────────────────│                  │              │
 │                      │                    │                  │              │
 │  Response            │                    │                  │              │
 │◀─────────────────────│                    │                  │              │
 │                      │                    │                  │              │
```

---

## Service Architecture

### Service Catalog

| Service | Language | Framework | Purpose | Dependencies |
|---------|----------|-----------|---------|--------------|
| **api-gateway** | Java 21 | Spring Boot 3.2 | Authentication, routing, rate limiting | Redis, PostgreSQL |
| **web-dashboard** | TypeScript | React 18, Vite | User interface | API Gateway |
| **ingestion-service** | Python 3.11 | FastAPI | Document processing, embeddings | PostgreSQL, Redis, Vector DB, S3 |
| **query-service** | Python 3.11 | FastAPI | LLM-powered search | PostgreSQL, Redis, Vector DB, LLM |
| **insight-service** | Python 3.11 | FastAPI | Pattern detection, analytics | PostgreSQL, Redis, Elasticsearch |
| **agent-service** | Python 3.11 | FastAPI | AI agents, workflows | PostgreSQL, Redis, All services |
| **notification-service** | Python 3.11 | FastAPI | Multi-channel notifications | Redis, SMTP, Slack API |
| **integration-service** | Python 3.11 | FastAPI | Third-party OAuth, sync | PostgreSQL, Redis |
| **slack-bot** | Python 3.11 | Bolt | Slack workspace integration | API Gateway, Redis |
| **teams-bot** | Python 3.11 | Teams SDK | Teams integration | API Gateway, Redis |

### Service Communication

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SERVICE COMMUNICATION PATTERNS                            │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SYNCHRONOUS (HTTP/REST)                                 │
│                                                                                  │
│     ┌────────────┐         ┌────────────┐         ┌────────────┐               │
│     │   Client   │────────▶│ API Gateway│────────▶│  Service   │               │
│     └────────────┘         └────────────┘         └────────────┘               │
│                                                                                  │
│     Use Cases:                                                                   │
│     • User requests (queries, uploads)                                          │
│     • Real-time operations                                                       │
│     • Health checks                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ASYNCHRONOUS (Redis Queue)                               │
│                                                                                  │
│     ┌────────────┐         ┌────────────┐         ┌────────────┐               │
│     │  Producer  │────────▶│   Redis    │────────▶│   Worker   │               │
│     │  Service   │         │   Queue    │         │  Service   │               │
│     └────────────┘         └────────────┘         └────────────┘               │
│                                                                                  │
│     Use Cases:                                                                   │
│     • Document processing                                                        │
│     • Embedding generation                                                       │
│     • Notification dispatch                                                      │
│     • Pattern analysis                                                           │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                          EVENT-DRIVEN (Redis Pub/Sub)                            │
│                                                                                  │
│     ┌────────────┐         ┌────────────┐         ┌────────────┐               │
│     │  Publisher │────────▶│   Redis    │────────▶│ Subscriber │               │
│     │            │         │   Pub/Sub  │         │  (Many)    │               │
│     └────────────┘         └────────────┘         └────────────┘               │
│                                                                                  │
│     Use Cases:                                                                   │
│     • Real-time updates                                                          │
│     • Cache invalidation                                                         │
│     • Agent triggers                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### API Gateway Detail

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                         │
│                           (Spring Boot 3.2)                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         REQUEST PIPELINE                                 │    │
│  │                                                                          │    │
│  │   Request ──▶ [Rate Limit] ──▶ [Auth] ──▶ [Validate] ──▶ [Route]        │    │
│  │                                                                          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│  │  Authentication │  │  Rate Limiting  │  │    Routing      │                 │
│  │                 │  │                 │  │                 │                 │
│  │  • JWT Tokens   │  │  • Per-user     │  │  • Path-based   │                 │
│  │  • API Keys     │  │  • Per-tenant   │  │  • Service mesh │                 │
│  │  • OAuth 2.0    │  │  • Per-endpoint │  │  • Load balance │                 │
│  │  • SAML/SSO     │  │  • Sliding win  │  │  • Retry logic  │                 │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│  │   Validation    │  │    Logging      │  │    Metrics      │                 │
│  │                 │  │                 │  │                 │                 │
│  │  • Request body │  │  • Structured   │  │  • Prometheus   │                 │
│  │  • Headers      │  │  • Trace IDs    │  │  • Latency      │                 │
│  │  • Tenant ctx   │  │  • Audit trail  │  │  • Error rates  │                 │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│                                                                                  │
│  Routes:                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  /api/v1/documents/*  ──▶  ingestion-service:8001                        │    │
│  │  /api/v1/query/*      ──▶  query-service:8002                            │    │
│  │  /api/v1/insights/*   ──▶  insight-service:8003                          │    │
│  │  /api/v1/agents/*     ──▶  agent-service:8090                            │    │
│  │  /api/v1/notify/*     ──▶  notification-service:8005                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Architecture

### Database Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           POSTGRESQL SCHEMA                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│       tenants       │     │        users        │     │       roles         │
├─────────────────────┤     ├─────────────────────┤     ├─────────────────────┤
│ id              PK  │◀────│ tenant_id       FK  │     │ id              PK  │
│ name                │     │ id              PK  │────▶│ name                │
│ slug                │     │ email               │     │ permissions    JSON │
│ settings       JSON │     │ password_hash       │     └─────────────────────┘
│ created_at          │     │ role_id         FK  │
│ status              │     │ created_at          │
└─────────────────────┘     └─────────────────────┘

         │
         │ 1:N
         ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│     documents       │     │    document_chunks  │     │     embeddings      │
├─────────────────────┤     ├─────────────────────┤     ├─────────────────────┤
│ id              PK  │◀────│ document_id     FK  │────▶│ chunk_id        FK  │
│ tenant_id       FK  │     │ id              PK  │     │ vector      VECTOR  │
│ source_type         │     │ content        TEXT │     │ metadata       JSON │
│ source_id           │     │ chunk_index         │     └─────────────────────┘
│ title               │     │ token_count         │
│ content_hash        │     │ created_at          │
│ metadata       JSON │     └─────────────────────┘
│ status              │
│ created_at          │
└─────────────────────┘

         │
         │ 1:N
         ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│      insights       │     │    insight_entities │     │   insight_relations │
├─────────────────────┤     ├─────────────────────┤     ├─────────────────────┤
│ id              PK  │◀────│ insight_id      FK  │     │ id              PK  │
│ tenant_id       FK  │     │ entity_type         │     │ source_insight  FK  │
│ document_id     FK  │     │ entity_value        │     │ target_insight  FK  │
│ type                │     │ confidence          │     │ relation_type       │
│ title               │     └─────────────────────┘     │ confidence          │
│ content        TEXT │                                 └─────────────────────┘
│ confidence          │
│ metadata       JSON │
│ created_at          │
└─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│       agents        │     │    agent_executions │     │    agent_actions    │
├─────────────────────┤     ├─────────────────────┤     ├─────────────────────┤
│ id              PK  │◀────│ agent_id        FK  │────▶│ execution_id    FK  │
│ tenant_id       FK  │     │ id              PK  │     │ id              PK  │
│ name                │     │ status              │     │ action_type         │
│ type                │     │ input_data     JSON │     │ input_data     JSON │
│ config         JSON │     │ result         JSON │     │ output_data    JSON │
│ workflow       JSON │     │ started_at          │     │ status              │
│ status              │     │ completed_at        │     │ duration_ms         │
│ version             │     │ triggered_by        │     └─────────────────────┘
│ created_at          │     └─────────────────────┘
└─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│     audit_logs      │     │     sync_jobs       │
├─────────────────────┤     ├─────────────────────┤
│ id              PK  │     │ id              PK  │
│ tenant_id       FK  │     │ tenant_id       FK  │
│ user_id         FK  │     │ source_type         │
│ action              │     │ status              │
│ resource_type       │     │ last_sync_at        │
│ resource_id         │     │ next_sync_at        │
│ details        JSON │     │ config         JSON │
│ ip_address          │     │ error_message       │
│ created_at          │     └─────────────────────┘
└─────────────────────┘
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DOCUMENT PROCESSING FLOW                                │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  Upload  │────▶│  Parse   │────▶│  Chunk   │────▶│  Embed   │────▶│  Store   │
  │          │     │          │     │          │     │          │     │          │
  │ PDF/DOCX │     │ Extract  │     │ Semantic │     │ OpenAI/  │     │ Vector + │
  │ MD/Email │     │ Text/Meta│     │ Chunking │     │ Bedrock  │     │ Postgres │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │                │                │                │                │
       ▼                ▼                ▼                ▼                ▼
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  S3/     │     │Unstructu-│     │ 500-1000 │     │ 1536-dim │     │  Qdrant  │
  │  MinIO   │     │ red.io   │     │  tokens  │     │ vectors  │     │ Pinecone │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                            QUERY/RAG FLOW                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  Query   │────▶│  Embed   │────▶│  Search  │────▶│ Build    │────▶│ Generate │
  │          │     │          │     │          │     │ Context  │     │ Response │
  │ "Find Q4 │     │ Query to │     │ Top-K    │     │ Chunks + │     │ LLM with │
  │  sales"  │     │ Vector   │     │ Similar  │     │ Prompt   │     │ Context  │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │                │                │                │                │
       ▼                ▼                ▼                ▼                ▼
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Natural  │     │ Same     │     │ Cosine   │     │ ~4K      │     │ Claude/  │
  │ Language │     │ Embedder │     │ Sim 0.7+ │     │ tokens   │     │ GPT-4    │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### Storage Strategy

| Data Type | Storage | Retention | Backup |
|-----------|---------|-----------|--------|
| **User Data** | PostgreSQL | Indefinite | Daily |
| **Documents** | S3/MinIO | Per policy | Daily |
| **Embeddings** | Vector DB | With document | Weekly |
| **Cache** | Redis | TTL-based | None |
| **Logs** | Elasticsearch | 30 days | None |
| **Traces** | Jaeger | 7 days | None |
| **Audit** | PostgreSQL | 7 years | Daily |

---

## AI/LLM Architecture

### LLM Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LLM INTEGRATION LAYER                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LLM ROUTER                                          │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                        Request Handler                                   │   │
│   │                                                                          │   │
│   │   • Provider selection (cost/latency/capability)                         │   │
│   │   • Rate limiting per provider                                           │   │
│   │   • Fallback handling                                                    │   │
│   │   • Response caching                                                     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│              ┌─────────────────────┼─────────────────────┐                      │
│              ▼                     ▼                     ▼                      │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐              │
│   │     OpenAI      │   │    Anthropic    │   │   AWS Bedrock   │              │
│   │                 │   │                 │   │                 │              │
│   │  • GPT-4        │   │  • Claude 3     │   │  • Claude       │              │
│   │  • GPT-4o       │   │  • Claude 3.5   │   │  • Titan        │              │
│   │  • Embeddings   │   │                 │   │  • Embeddings   │              │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Embedding Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          EMBEDDING PIPELINE                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

Document                    Chunking                      Embedding
   │                           │                             │
   ▼                           ▼                             ▼
┌──────┐    ┌──────────────────────────────┐    ┌──────────────────────────────┐
│      │    │  Semantic Chunking            │    │  Batch Embedding             │
│ PDF  │───▶│                               │───▶│                              │
│ DOCX │    │  • 500-1000 tokens per chunk  │    │  • OpenAI text-embedding-3   │
│ TXT  │    │  • Overlap: 100 tokens        │    │  • 1536 dimensions           │
│ MD   │    │  • Preserve paragraphs        │    │  • Batch size: 100           │
│      │    │  • Metadata attached          │    │  • Rate limited              │
└──────┘    └──────────────────────────────┘    └──────────────────────────────┘
                                                              │
                                                              ▼
                                                 ┌──────────────────────────────┐
                                                 │  Vector Storage               │
                                                 │                              │
                                                 │  • Qdrant (dev)              │
                                                 │  • Pinecone (prod)           │
                                                 │  • HNSW index                │
                                                 │  • Metadata filtering        │
                                                 └──────────────────────────────┘
```

### RAG (Retrieval Augmented Generation)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              RAG PIPELINE                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

User Query: "What were the key issues in the Q4 customer feedback?"

Step 1: Query Embedding
┌─────────────────────────────────────────────────────────────────────────────────┐
│  "What were the key issues..." ──▶ [0.023, -0.891, 0.442, ...]  (1536-dim)     │
└─────────────────────────────────────────────────────────────────────────────────┘

Step 2: Vector Search
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Query: vector + filters (tenant_id, date_range, source_type)                   │
│  Result: Top 10 chunks with similarity > 0.75                                   │
│                                                                                  │
│  Chunk 1: "Q4 feedback showed 23% increase in shipping complaints..." (0.89)   │
│  Chunk 2: "Customer satisfaction dropped in November due to..." (0.85)         │
│  Chunk 3: "Support tickets related to delivery delays..." (0.82)               │
└─────────────────────────────────────────────────────────────────────────────────┘

Step 3: Context Building
┌─────────────────────────────────────────────────────────────────────────────────┐
│  System: You are an AI assistant analyzing business documents.                  │
│                                                                                  │
│  Context:                                                                        │
│  [Document: Q4 Customer Feedback Report]                                        │
│  Q4 feedback showed 23% increase in shipping complaints...                      │
│                                                                                  │
│  [Document: Support Analysis November]                                          │
│  Customer satisfaction dropped in November due to...                            │
│                                                                                  │
│  User: What were the key issues in the Q4 customer feedback?                    │
└─────────────────────────────────────────────────────────────────────────────────┘

Step 4: LLM Generation
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Based on the Q4 customer feedback analysis, the key issues were:               │
│                                                                                  │
│  1. **Shipping Delays** (23% increase in complaints)                            │
│     - Primary cause: Holiday season volume                                      │
│     - Most affected: East Coast customers                                       │
│                                                                                  │
│  2. **Customer Support Wait Times**                                             │
│     - Average wait time increased to 12 minutes                                 │
│     - Peak times: Monday mornings                                               │
│                                                                                  │
│  3. **Product Quality** (specific to SKU range 4500-4700)                       │
│     - Return rate: 8.5% (up from 5.2% in Q3)                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Platform Architecture

### Agent System Overview (Phase 9)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          AGENT PLATFORM (Phase 9)                                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                             AGENT SERVICE                                        │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                          AGENT CORE                                      │    │
│  │                                                                          │    │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │    │
│  │   │   Agent     │   │   Agent     │   │   Action    │   │   Agent     │ │    │
│  │   │  Registry   │   │Orchestrator │   │ Repository  │   │  Executor   │ │    │
│  │   │             │   │             │   │             │   │             │ │    │
│  │   │ • CRUD      │   │ • Workflow  │   │ • Built-in  │   │ • Run steps │ │    │
│  │   │ • Versions  │   │ • State     │   │ • Custom    │   │ • Handle    │ │    │
│  │   │ • Templates │   │ • Routing   │   │ • Validate  │   │   errors    │ │    │
│  │   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                          TRIGGERS                                        │    │
│  │                                                                          │    │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │    │
│  │   │  Schedule   │   │   Webhook   │   │    Email    │   │    Slack    │ │    │
│  │   │  Trigger    │   │   Trigger   │   │   Trigger   │   │   Trigger   │ │    │
│  │   │             │   │             │   │             │   │             │ │    │
│  │   │ • Cron      │   │ • HTTP POST │   │ • IMAP poll │   │ • Events    │ │    │
│  │   │ • Interval  │   │ • Signature │   │ • Filters   │   │ • Commands  │ │    │
│  │   │ • One-time  │   │ • Auth      │   │             │   │             │ │    │
│  │   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        ACTION BLOCKS                                     │    │
│  │                                                                          │    │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │    │
│  │   │ External    │   │  Database   │   │Notification │   │    File     │ │    │
│  │   │    API      │   │   Action    │   │   Action    │   │   Action    │ │    │
│  │   │             │   │             │   │             │   │             │ │    │
│  │   │ • REST      │   │ • Query     │   │ • Email     │   │ • Read      │ │    │
│  │   │ • GraphQL   │   │ • Insert    │   │ • Slack     │   │ • Write     │ │    │
│  │   │ • OAuth     │   │ • Update    │   │ • Teams     │   │ • Transform │ │    │
│  │   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      APPROVAL WORKFLOW                                   │    │
│  │                                                                          │    │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │    │
│  │   │  Approval   │   │  Approval   │   │ Escalation  │   │   Audit     │ │    │
│  │   │   Engine    │   │     UI      │   │   Logic     │   │   Logger    │ │    │
│  │   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Agent Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        AGENT EXECUTION FLOW                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

Trigger                 Agent Service              Actions              External
   │                         │                        │                    │
   │  Event (schedule/       │                        │                    │
   │  webhook/email)         │                        │                    │
   │────────────────────────▶│                        │                    │
   │                         │                        │                    │
   │                         │  Load Agent Config     │                    │
   │                         │  Create Execution      │                    │
   │                         │                        │                    │
   │                         │  Step 1: API Call      │                    │
   │                         │───────────────────────▶│                    │
   │                         │                        │  HTTP Request      │
   │                         │                        │───────────────────▶│
   │                         │                        │                    │
   │                         │                        │  Response          │
   │                         │                        │◀───────────────────│
   │                         │  Step 1 Result         │                    │
   │                         │◀───────────────────────│                    │
   │                         │                        │                    │
   │                         │  Step 2: Approval      │                    │
   │                         │  Required?             │                    │
   │                         │        │               │                    │
   │                         │        ▼               │                    │
   │                         │  [Wait for Approval]   │                    │
   │                         │        │               │                    │
   │                         │        ▼               │                    │
   │                         │  Step 3: Send Email    │                    │
   │                         │───────────────────────▶│                    │
   │                         │                        │  SMTP Send         │
   │                         │                        │───────────────────▶│
   │                         │                        │                    │
   │                         │  Execution Complete    │                    │
   │                         │  Emit Webhook Event    │                    │
   │◀────────────────────────│                        │                    │
   │                         │                        │                    │
```

### Agent Types

| Type | Description | Example Use Cases |
|------|-------------|-------------------|
| **Conversational** | Interactive Q&A agents | Customer support, internal help desk |
| **Task** | Execute predefined workflows | Data sync, report generation |
| **Reactive** | Respond to events | Alert on anomalies, auto-triage |
| **Scheduled** | Time-based execution | Daily digests, cleanup jobs |
| **Hybrid** | Combine multiple types | Complex multi-step automation |

---

## Security Architecture

### Security Layers

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY ARCHITECTURE                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: NETWORK SECURITY                                                        │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   WAF / DDoS    │  │  TLS 1.3        │  │  Network        │                  │
│  │   Protection    │  │  Everywhere     │  │  Policies       │                  │
│  │                 │  │                 │  │                 │                  │
│  │  • AWS Shield   │  │  • HTTPS only   │  │  • Default deny │                  │
│  │  • Rate limits  │  │  • Strong cipher│  │  • Pod-to-pod   │                  │
│  │  • IP filtering │  │  • Cert rotation│  │  • Egress rules │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: AUTHENTICATION                                                          │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   JWT Tokens    │  │   OAuth 2.0     │  │   API Keys      │                  │
│  │                 │  │                 │  │                 │                  │
│  │  • RS256 signed │  │  • PKCE flow    │  │  • Hashed       │                  │
│  │  • 1hr expiry   │  │  • Scoped       │  │  • Rotatable    │                  │
│  │  • Refresh tok  │  │  • Third-party  │  │  • Rate limited │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: AUTHORIZATION                                                           │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   RBAC          │  │  Tenant         │  │  Resource       │                  │
│  │                 │  │  Isolation      │  │  Permissions    │                  │
│  │  • Admin        │  │                 │  │                 │                  │
│  │  • Editor       │  │  • Row-level    │  │  • Read/Write   │                  │
│  │  • Viewer       │  │  • Schema sep   │  │  • Owner/Share  │                  │
│  │  • Custom       │  │  • Query filter │  │  • Inheritance  │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: DATA PROTECTION                                                         │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  Encryption     │  │  Secrets        │  │  Data           │                  │
│  │  at Rest        │  │  Management     │  │  Masking        │                  │
│  │                 │  │                 │  │                 │                  │
│  │  • KMS managed  │  │  • AWS Secrets  │  │  • PII redact   │                  │
│  │  • AES-256      │  │  • Vault        │  │  • Log sanitize │                  │
│  │  • Key rotation │  │  • External Sec │  │  • Export filter│                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: CONTAINER SECURITY                                                      │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  Pod Security   │  │  Image          │  │  Runtime        │                  │
│  │  Standards      │  │  Scanning       │  │  Protection     │                  │
│  │                 │  │                 │  │                 │                  │
│  │  • Non-root     │  │  • Trivy        │  │  • Seccomp      │                  │
│  │  • Read-only FS │  │  • CVE checks   │  │  • AppArmor     │                  │
│  │  • Drop caps    │  │  • SBOM         │  │  • Falco        │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Multi-Tenant Isolation

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-TENANT ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                         │
│                                                                                  │
│   Request ──▶ Extract Tenant ID ──▶ Validate Access ──▶ Inject Context          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER                                          │
│                                                                                  │
│   Every query: WHERE tenant_id = :current_tenant_id                             │
│   Every insert: SET tenant_id = :current_tenant_id                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                            │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐  │
│   │                        PostgreSQL                                         │  │
│   │                                                                           │  │
│   │   ┌─────────────────────────────────────────────────────────────────┐    │  │
│   │   │  Row-Level Security (RLS)                                        │    │  │
│   │   │                                                                   │    │  │
│   │   │  CREATE POLICY tenant_isolation ON documents                     │    │  │
│   │   │  USING (tenant_id = current_setting('app.tenant_id'));          │    │  │
│   │   └─────────────────────────────────────────────────────────────────┘    │  │
│   │                                                                           │  │
│   │   Tenant A Data    │    Tenant B Data    │    Tenant C Data             │  │
│   │   ═══════════════  │    ═══════════════  │    ═══════════════           │  │
│   └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐  │
│   │                        Vector DB                                          │  │
│   │                                                                           │  │
│   │   Collection: embeddings                                                  │  │
│   │   Filter: {"tenant_id": "tenant-123"}                                    │  │
│   └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐  │
│   │                          S3                                               │  │
│   │                                                                           │  │
│   │   Bucket: aswa-documents                                                  │  │
│   │   Path: /tenant-123/documents/...                                        │  │
│   └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Integration Architecture

### Third-Party Connectors

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       INTEGRATION ARCHITECTURE                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CONNECTOR FRAMEWORK                                      │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Base Connector Interface                              │    │
│  │                                                                          │    │
│  │   • authenticate()      • sync()           • handle_webhook()           │    │
│  │   • list_items()        • get_item()       • transform()                │    │
│  │   • health_check()      • rate_limit()     • retry_with_backoff()       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│         ┌────────────────────────────┼────────────────────────────┐             │
│         ▼                            ▼                            ▼             │
│  ┌─────────────┐             ┌─────────────┐             ┌─────────────┐       │
│  │   Email     │             │  Document   │             │     CRM     │       │
│  │ Connectors  │             │ Connectors  │             │ Connectors  │       │
│  │             │             │             │             │             │       │
│  │ • Gmail     │             │ • GDrive    │             │ • Salesforce│       │
│  │ • Outlook   │             │ • SharePoint│             │ • Zoho      │       │
│  │ • MS 365    │             │ • Confluence│             │ • HubSpot   │       │
│  │             │             │ • Notion    │             │             │       │
│  └─────────────┘             └─────────────┘             └─────────────┘       │
│                                                                                  │
│  ┌─────────────┐             ┌─────────────┐             ┌─────────────┐       │
│  │  Messaging  │             │  Meetings   │             │   Custom    │       │
│  │ Connectors  │             │ Connectors  │             │ Connectors  │       │
│  │             │             │             │             │             │       │
│  │ • Slack     │             │ • Zoom      │             │ • REST API  │       │
│  │ • Teams     │             │ • Meet      │             │ • GraphQL   │       │
│  │             │             │             │             │ • Webhooks  │       │
│  └─────────────┘             └─────────────┘             └─────────────┘       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                          OAUTH FLOW                                              │
│                                                                                  │
│   User          ASWA           Provider                                          │
│    │             │                │                                              │
│    │ Connect     │                │                                              │
│    │────────────▶│                │                                              │
│    │             │  Auth URL      │                                              │
│    │             │───────────────▶│                                              │
│    │◀────────────│                │                                              │
│    │  Redirect   │                │                                              │
│    │─────────────────────────────▶│                                              │
│    │             │                │  User Consents                               │
│    │◀─────────────────────────────│                                              │
│    │  Code       │                │                                              │
│    │────────────▶│                │                                              │
│    │             │  Exchange Code │                                              │
│    │             │───────────────▶│                                              │
│    │             │  Tokens        │                                              │
│    │             │◀───────────────│                                              │
│    │  Connected  │                │                                              │
│    │◀────────────│                │                                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

### Kubernetes Deployment

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       KUBERNETES ARCHITECTURE                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EKS CLUSTER                                         │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         NAMESPACES                                       │    │
│  │                                                                          │    │
│  │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │    │
│  │   │   aswa-prod   │  │ aswa-staging  │  │   aswa-dev    │               │    │
│  │   │               │  │               │  │               │               │    │
│  │   │ • Services    │  │ • Services    │  │ • Services    │               │    │
│  │   │ • Secrets     │  │ • Secrets     │  │ • Secrets     │               │    │
│  │   │ • ConfigMaps  │  │ • ConfigMaps  │  │ • ConfigMaps  │               │    │
│  │   └───────────────┘  └───────────────┘  └───────────────┘               │    │
│  │                                                                          │    │
│  │   ┌───────────────┐  ┌───────────────┐                                  │    │
│  │   │  monitoring   │  │   logging     │                                  │    │
│  │   │               │  │               │                                  │    │
│  │   │ • Prometheus  │  │ • Fluent Bit  │                                  │    │
│  │   │ • Grafana     │  │ • Loki        │                                  │    │
│  │   │ • Jaeger      │  │               │                                  │    │
│  │   └───────────────┘  └───────────────┘                                  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    NODE GROUPS                                           │    │
│  │                                                                          │    │
│  │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │    │
│  │   │  General      │  │  Compute      │  │   Memory      │               │    │
│  │   │  Purpose      │  │  Optimized    │  │  Optimized    │               │    │
│  │   │               │  │               │  │               │               │    │
│  │   │  m6i.xlarge   │  │  c6i.2xlarge  │  │  r6i.xlarge   │               │    │
│  │   │  (API, Web)   │  │  (Ingestion)  │  │  (Query, ES)  │               │    │
│  │   └───────────────┘  └───────────────┘  └───────────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Helm Chart Structure

```
infrastructure/helm/charts/aswa/
├── Chart.yaml                 # Chart metadata
├── values.yaml                # Default values
├── values-dev.yaml           # Development overrides
├── values-staging.yaml       # Staging overrides
├── values-prod.yaml          # Production overrides
│
├── templates/
│   ├── _helpers.tpl          # Template helpers
│   ├── configmap.yaml        # Configuration
│   ├── secret.yaml           # Secrets reference
│   │
│   ├── api-gateway/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   │
│   ├── ingestion-service/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   │
│   ├── ... (other services)
│   │
│   ├── ingress.yaml          # Ingress configuration
│   └── networkpolicy.yaml    # Network policies
│
└── charts/                    # Dependencies
    ├── postgresql/
    ├── redis/
    └── elasticsearch/
```

---

## Observability Architecture

### Monitoring Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITY ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              METRICS                                             │
│                                                                                  │
│   Services ──▶ Prometheus Exporter ──▶ Prometheus ──▶ Grafana                  │
│                     (Port 9090)          (Scrape)       (Visualize)             │
│                                                                                  │
│   Key Metrics:                                                                   │
│   • Request rate, latency (p50, p95, p99)                                       │
│   • Error rates by service and endpoint                                          │
│   • Resource utilization (CPU, memory)                                           │
│   • Queue depths and processing times                                            │
│   • LLM token usage and costs                                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LOGGING                                             │
│                                                                                  │
│   Services ──▶ stdout/stderr ──▶ Fluent Bit ──▶ Loki ──▶ Grafana               │
│                  (JSON logs)      (Collect)     (Store)   (Query)               │
│                                                                                  │
│   Log Format:                                                                    │
│   {                                                                              │
│     "timestamp": "2024-01-15T10:30:00Z",                                        │
│     "level": "info",                                                             │
│     "service": "query-service",                                                  │
│     "trace_id": "abc123",                                                        │
│     "tenant_id": "tenant-456",                                                   │
│     "message": "Query processed",                                                │
│     "duration_ms": 234                                                           │
│   }                                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TRACING                                             │
│                                                                                  │
│   Services ──▶ OpenTelemetry SDK ──▶ OTLP Collector ──▶ Jaeger                 │
│                  (Instrument)         (Export)          (Visualize)             │
│                                                                                  │
│   Trace Flow:                                                                    │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐                     │
│   │ Gateway │───▶│ Query   │───▶│ Vector  │───▶│   LLM   │                     │
│   │  Span   │    │  Span   │    │  Span   │    │  Span   │                     │
│   │  50ms   │    │  150ms  │    │  30ms   │    │  500ms  │                     │
│   └─────────┘    └─────────┘    └─────────┘    └─────────┘                     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ALERTING                                            │
│                                                                                  │
│   Prometheus ──▶ AlertManager ──▶ Slack/PagerDuty/Email                         │
│                                                                                  │
│   Alert Rules:                                                                   │
│   • ServiceDown: Pod not ready > 1 minute                                        │
│   • HighErrorRate: Error rate > 5% for 5 minutes                                 │
│   • HighLatency: p99 > 2 seconds for 5 minutes                                   │
│   • DiskSpaceLow: Disk usage > 80%                                               │
│   • LLMCostSpike: Token usage > 2x normal                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Design Decisions

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Microservices vs Monolith** | Microservices | Independent scaling, polyglot, team autonomy |
| **Java vs Python for Gateway** | Java | Performance, Spring ecosystem, enterprise patterns |
| **Python for AI Services** | Python | LLM libraries, ML ecosystem, rapid development |
| **PostgreSQL vs NoSQL** | PostgreSQL | ACID, relations, mature tooling, vector extension |
| **Qdrant vs Pinecone (dev)** | Qdrant | Self-hosted, no cost for dev, good performance |
| **Kubernetes vs ECS** | Kubernetes | Portability, ecosystem, on-prem support |
| **REST vs GraphQL** | REST | Simplicity, caching, widespread adoption |
| **JWT vs Session** | JWT | Stateless, scalable, microservices friendly |

### Trade-offs Considered

| Trade-off | Chosen | Alternative | Reasoning |
|-----------|--------|-------------|-----------|
| Sync vs Async processing | Async for heavy ops | All sync | Better UX for uploads |
| Single vs Multi-tenant DB | Multi-tenant with RLS | Separate DBs | Cost efficiency, simpler ops |
| Self-hosted vs Managed LLM | Managed (OpenAI/Bedrock) | Self-hosted | Faster iteration, less ops |
| Monorepo vs Polyrepo | Monorepo | Polyrepo | Atomic changes, shared libs |

---

## Future Considerations

### Scalability Path

1. **Horizontal Scaling**: All services stateless, scale via HPA
2. **Database Scaling**: Read replicas, connection pooling, sharding if needed
3. **Vector DB Scaling**: Pinecone managed scaling or Qdrant cluster
4. **LLM Scaling**: Provider rate limits, fallback providers, caching

### Potential Enhancements

- **Multi-region**: Active-active deployment
- **Edge Computing**: CDN for static assets, edge functions
- **Real-time**: WebSocket support for live updates
- **Federated Learning**: On-prem model fine-tuning
- **Compliance**: SOC 2, HIPAA, GDPR certifications

---

*Last Updated: January 2026*
