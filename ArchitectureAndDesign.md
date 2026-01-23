# InsightWeave AI: Complete System Architecture Design

**InsightWeave AI** can ship its MVP in 8-10 weeks using a pragmatic stack: Airbyte for data ingestion, Qdrant for vector storage, Instructor + LlamaIndex for LLM orchestration, FastAPI for the API layer, and Prefect for workflow orchestration—all deployed on Kubernetes with Helm and ArgoCD. This architecture prioritizes operational simplicity for a lean team while maintaining a clear path to enterprise scale.

The core insight driving these choices: at hundreds of documents per day, the bottleneck isn't infrastructure performance—it's development velocity and operational overhead. Every component selected minimizes the "ops tax" on a 2-developer team while avoiding technology dead-ends that would require expensive rewrites later.

---

## High-level architecture and data flow

The system follows a five-layer architecture designed for clear separation of concerns and independent scaling:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INTERFACE LAYER                                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────────────┐ │
│  │   Slack Bot     │  │   Teams Bot      │  │   Web Dashboard (Optional)      │ │
│  │   (Bolt Python) │  │   (Teams SDK v2) │  │   (React + Tailwind)            │ │
│  └────────┬────────┘  └────────┬─────────┘  └───────────────┬─────────────────┘ │
└───────────┼────────────────────┼────────────────────────────┼───────────────────┘
            │                    │                            │
            ▼                    ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (FastAPI)                               │
│  • Query endpoint (natural language search)                                      │
│  • Document upload/sync triggers                                                 │
│  • Alert configuration                                                           │
│  • Admin/audit endpoints                                                         │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                    ┌────────────────────┼─────────────────────┐
                    ▼                    ▼                     ▼
┌───────────────────────┐  ┌──────────────────────┐  ┌────────────────────────────┐
│   INGESTION LAYER     │  │   INSIGHT ENGINE     │  │   OUTPUT LAYER             │
│                       │  │                      │  │                            │
│  ┌─────────────────┐  │  │  ┌────────────────┐  │  │  ┌────────────────────┐   │
│  │    Airbyte      │  │  │  │  Extraction    │  │  │  │  Jira Integration  │   │
│  │  (Connectors)   │  │  │  │  (Instructor)  │  │  │  └────────────────────┘   │
│  └─────────────────┘  │  │  └────────────────┘  │  │  ┌────────────────────┐   │
│  ┌─────────────────┐  │  │  ┌────────────────┐  │  │  │  CRM Updates       │   │
│  │  Unstructured   │  │  │  │  RAG Query     │  │  │  └────────────────────┘   │
│  │  (Doc parsing)  │  │  │  │  (LlamaIndex)  │  │  │  ┌────────────────────┐   │
│  └─────────────────┘  │  │  └────────────────┘  │  │  │  Webhooks          │   │
│  ┌─────────────────┐  │  │  ┌────────────────┐  │  │  └────────────────────┘   │
│  │  Whisper API    │  │  │  │  Pattern       │  │  │                            │
│  │  (Audio)        │  │  │  │  Recognition   │  │  │                            │
│  └─────────────────┘  │  │  └────────────────┘  │  │                            │
└───────────────────────┘  └──────────────────────┘  └────────────────────────────┘
                    │                    │                     │
                    └────────────────────┼─────────────────────┘
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐  ┌───────────┐  │
│  │   PostgreSQL    │  │     Qdrant       │  │      Redis      │  │    S3     │  │
│  │   (CloudNativePG)│  │   (Vectors)      │  │   (Cache/Queue) │  │  (Blobs)  │  │
│  │                 │  │                  │  │                 │  │           │  │
│  │  • Documents    │  │  • Embeddings    │  │  • Job queue    │  │  • PDFs   │  │
│  │  • Insights     │  │  • Metadata      │  │  • Cache        │  │  • Audio  │  │
│  │  • Users/Tenants│  │  • Hybrid index  │  │  • Rate limits  │  │  • Logs   │  │
│  │  • Audit logs   │  │                  │  │                 │  │           │  │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      Prefect (Workflow Engine)                           │    │
│  │                                                                          │    │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │    │
│  │   │ Sync Flow    │  │ Extract Flow │  │ Alert Flow   │  │ Digest Flow│  │    │
│  │   │ (Scheduled)  │  │ (Triggered)  │  │ (Scheduled)  │  │ (Daily)    │  │    │
│  │   └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Data flow for document processing** follows this path: (1) Airbyte syncs data from connectors on schedule or webhook trigger → (2) Raw documents land in PostgreSQL with blob storage in S3 → (3) Prefect triggers extraction flow → (4) Unstructured.io parses documents into chunks → (5) Chunks are embedded and stored in Qdrant with metadata → (6) Instructor extracts structured insights (entities, risks, opportunities) → (7) Insights are stored in PostgreSQL with vector references → (8) Alerts are evaluated and notifications dispatched.

---

## Technology stack with rationale

### Data ingestion layer

| Component | Recommendation | Rationale |
|-----------|----------------|-----------|
| **Connector Platform** | Airbyte (self-hosted Helm) | **600+ connectors** including certified Gmail, Slack, Salesforce, Microsoft 365. Low-code connector builder for custom APIs. Proven Kubernetes deployment with 4 CPU/8GB minimum. |
| **Document Parsing** | Unstructured.io OSS | Best RAG optimization, handles PDFs, DOCX, HTML, emails, images. Falls back to Apache Tika for rare formats. |
| **OCR** | PaddleOCR (GPU) / Tesseract (CPU) | **95%+ accuracy** on documents with PaddleOCR. Tesseract fallback for CPU-only customer environments. |
| **Audio Transcription** | OpenAI Whisper API | **$0.006/minute**, excellent multilingual support, zero infrastructure. Consider Deepgram for real-time needs. |
| **OAuth Management** | Nango (alongside Airbyte) | Pre-built OAuth for 500+ APIs, handles rate limiting and token refresh. Open-source with self-hosting option. |

**Deduplication strategy**: Implement three-stage deduplication: (1) MD5 content hash for exact duplicates, (2) MinHash LSH for near-duplicates at Jaccard threshold 0.8 using the `datasketch` library, (3) document versioning via `(source_id, document_id, version_hash, modified_time)` tuples with upsert logic.

### Vector and insight layer

| Component | Recommendation | Rationale |
|-----------|----------------|-----------|
| **Vector Database** | Qdrant | Lowest operational overhead among purpose-built vector DBs. Excellent filtering for multi-tenancy. **Written in Rust** for memory safety. Simple Helm deployment. Handles billions of vectors, though MVP needs only thousands. |
| **Embedding Model** | OpenAI text-embedding-3-small → BGE-M3 | Start with OpenAI at **$0.02/1M tokens** for simplicity. Migrate to self-hosted BGE-M3 for cost reduction and privacy when scale demands. |
| **LLM Orchestration** | Instructor + LlamaIndex | Instructor provides structured extraction with Pydantic validation and automatic retries. LlamaIndex adds document indexing when RAG complexity grows. **Avoid LangChain**—over-abstraction creates maintenance burden. |
| **Search Strategy** | Hybrid (vector + BM25) with RRF fusion | Vector search alone fails on abbreviations, proper nouns, and exact IDs. Combine with BM25 using Reciprocal Rank Fusion. Add cross-encoder reranking (BGE-reranker-v2-m3) in Phase 2 for quality. |
| **Chunking** | RecursiveCharacterTextSplitter | **512 tokens with 64-token overlap**. Use semantic chunking for reports. Consider late chunking for documents approaching 8K tokens. |

### Infrastructure layer

| Component | Recommendation | Rationale |
|-----------|----------------|-----------|
| **Workflow Orchestration** | Prefect | Python-native with simple decorators. **10x faster than Airflow** (4.8s vs 56s for 40 tasks). Low learning curve—"if you know Python, you know Prefect." |
| **Message Queue** | Redis Streams | Already need Redis for caching; Streams add queue capability without extra infrastructure. Handles millions/sec; hundreds/day is trivial. |
| **API Framework** | FastAPI | Python ecosystem alignment with ML libraries. Automatic OpenAPI documentation. Async support for non-blocking LLM calls. |
| **Database** | PostgreSQL (CloudNativePG operator) | Most popular Kubernetes PostgreSQL operator (27.6% adoption). Built-in HA, automatic backups to S3, Prometheus integration. |
| **Helm/GitOps** | Helm + Kustomize + ArgoCD | Helm for third-party apps, Kustomize for environment overlays. ArgoCD provides visual UI for debugging—invaluable for lean teams. |
| **Monitoring** | Prometheus + Grafana + Loki | Industry standard, free, comprehensive Helm charts. Loki for logs (indexes labels only, cost-effective). |

---

## Low-level design for critical components

### Ingestion pipeline architecture

**Connector abstraction interface**:
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from pydantic import BaseModel

class NormalizedDocument(BaseModel):
    source_id: str           # e.g., "gmail", "slack", "salesforce"
    document_id: str         # Unique within source
    content: str
    content_type: str        # "email", "message", "document", "transcript"
    metadata: dict
    timestamp: datetime
    version_hash: str        # MD5 of content
    raw_payload: dict        # Original data for debugging

class ConnectorInterface(ABC):
    @abstractmethod
    async def authenticate(self, credentials: dict) -> str: ...
    
    @abstractmethod
    async def incremental_sync(self, cursor: str | None) -> AsyncIterator[NormalizedDocument]: ...
    
    @abstractmethod
    async def handle_webhook(self, payload: dict) -> list[NormalizedDocument]: ...
```

**Chunking strategy implementation**:
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

def create_chunker(doc_type: str) -> RecursiveCharacterTextSplitter:
    configs = {
        "email": {"chunk_size": 512, "chunk_overlap": 64},
        "document": {"chunk_size": 1024, "chunk_overlap": 128},
        "transcript": {"chunk_size": 512, "chunk_overlap": 64},
        "legal": {"chunk_size": 256, "chunk_overlap": 32},  # High precision
    }
    config = configs.get(doc_type, configs["document"])
    return RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        **config
    )
```

### Insight extraction engine

**Core extraction schemas** (Pydantic models for Instructor):

```python
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class Entity(BaseModel):
    name: str
    type: Literal["person", "organization", "location", "product", "concept"]
    aliases: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_snippets: list[str]

class Risk(BaseModel):
    title: str
    category: Literal["operational", "financial", "compliance", "market", "technical"]
    severity: Literal["low", "medium", "high", "critical"]
    likelihood: Literal["unlikely", "possible", "likely", "certain"]
    description: str
    mitigation_suggestions: list[str] = []
    evidence: list[str]
    confidence: float

class Opportunity(BaseModel):
    title: str
    category: Literal["growth", "efficiency", "partnership", "technology", "market"]
    potential_impact: Literal["low", "medium", "high", "transformative"]
    time_horizon: Literal["immediate", "short_term", "medium_term", "long_term"]
    description: str
    action_items: list[str] = []
    evidence: list[str]
    confidence: float

class Relationship(BaseModel):
    source_entity: str
    target_entity: str
    relationship_type: Literal[
        "acquired", "partnered_with", "competes_with", "supplies_to",
        "employs", "founded", "located_in", "subsidiary_of", "invests_in"
    ]
    direction: Literal["source_to_target", "bidirectional"]
    confidence: float
    evidence: str
```

**Extraction with confidence scoring**:
```python
import instructor
from openai import AzureOpenAI

client = instructor.from_openai(AzureOpenAI(...))

EXTRACTION_PROMPT = """
Extract all named entities from the following text. For each entity:
- Identify the entity name exactly as it appears
- Classify the type (person, organization, location, product, concept)
- Note any aliases or alternative names mentioned
- Include exact text snippets as evidence
- Rate confidence: 1.0 = explicit, 0.7-0.9 = strongly implied, 0.5-0.7 = inferred, <0.5 = speculative

Text: {chunk}
"""

def extract_entities(chunk: str) -> list[Entity]:
    return client.chat.completions.create(
        model="gpt-4o",
        response_model=list[Entity],
        max_retries=3,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(chunk=chunk)}]
    )
```

**Map-reduce for long documents**: Split document into 1500-3000 token chunks with 10-20% overlap. Extract insights from each chunk in parallel. Aggregate, deduplicate entities by embedding similarity, and consolidate relationships in a reduce pass.

### Query engine (RAG architecture)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import numpy as np

class QueryEngine:
    def __init__(self, qdrant: QdrantClient, embedder, llm_client):
        self.qdrant = qdrant
        self.embedder = embedder
        self.llm = llm_client
    
    async def search(
        self, 
        query: str, 
        tenant_id: str,
        top_k: int = 20,
        filters: dict = None
    ) -> list[dict]:
        # 1. Embed query
        query_vector = await self.embedder.embed(query)
        
        # 2. Build filters (multi-tenancy + user filters)
        must_conditions = [FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        if filters:
            for key, value in filters.items():
                must_conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        
        # 3. Vector search with filtering
        results = self.qdrant.search(
            collection_name="documents",
            query_vector=query_vector,
            query_filter=Filter(must=must_conditions),
            limit=top_k,
            with_payload=True
        )
        
        # 4. (Optional) Re-rank with cross-encoder
        # reranked = self.reranker.rerank(query, [r.payload["content"] for r in results])
        
        # 5. Format context for LLM
        context = "\n\n".join([
            f"[Source: {r.payload['source']}]\n{r.payload['content']}" 
            for r in results[:10]
        ])
        
        # 6. Generate response with citations
        response = await self.llm.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Answer based on the provided context. Cite sources."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
            ]
        )
        
        return {
            "answer": response.choices[0].message.content,
            "sources": [{"id": r.id, "source": r.payload["source"], "score": r.score} for r in results[:10]]
        }
```

---

## Integration patterns

### OAuth flows

| Provider | Flow | Key Considerations |
|----------|------|-------------------|
| **Google (Gmail, Drive)** | Authorization Code + PKCE | Scopes: `gmail.readonly`, `drive.readonly`. Rate: 250 quota units/user/sec. |
| **Microsoft (Outlook, Teams, SharePoint)** | Authorization Code | Azure AD app registration. Delta queries for incremental sync. Rate: 10,000 requests/10 min. |
| **Salesforce** | Client Credentials (server-to-server) | Use dedicated Integration User license. Named Credentials for secure callouts. |
| **Slack** | OAuth 2.0 | Scopes: `channels:history`, `channels:read`, `users:read`. Effective **1 req/min** for OAuth on some methods. |

### Webhook vs polling decision matrix

| Source | Strategy | Rationale |
|--------|----------|-----------|
| **Slack** | Webhooks (Events API) | Real-time events available; critical for chat responsiveness |
| **Gmail** | Webhooks + Polling fallback | Push notifications available; polling as safety net |
| **SharePoint** | Webhooks + Polling | Webhooks available but 30-day expiry requires renewal |
| **Salesforce** | Polling (incremental) | No CDC in Airbyte; platform events are alternative |
| **Zoom** | Webhooks | Real-time transcription events; JWT authentication |

**Webhook reliability pattern**: (1) Verify signatures (HMAC-SHA256), (2) Store event IDs for idempotency, (3) Acknowledge immediately, process async, (4) Exponential backoff with jitter on failures, (5) Dead letter queue after 5 retries.

### Rate limiting implementation

```python
import time
import random

def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = delay * (0.5 + random.random())  # 50-150% of delay
    return jitter

async def rate_limited_request(func, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            response = await func()
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', exponential_backoff(attempt)))
                await asyncio.sleep(retry_after)
                continue
            return response
        except RateLimitError:
            await asyncio.sleep(exponential_backoff(attempt))
    raise MaxRetriesExceeded()
```

---

## Database schema design

### PostgreSQL schema (relational + metadata)

```sql
-- Core multi-tenant structure
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'member',  -- admin, manager, member, viewer
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document tracking
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    source_type VARCHAR(50) NOT NULL,      -- gmail, slack, salesforce, etc.
    source_id VARCHAR(255) NOT NULL,       -- External ID from source
    content_hash VARCHAR(64) NOT NULL,     -- MD5 for dedup
    title VARCHAR(500),
    raw_content TEXT,
    processed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, source_type, source_id)
);

-- Extracted insights
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    document_id UUID REFERENCES documents(id),
    insight_type VARCHAR(50) NOT NULL,     -- entity, risk, opportunity, pattern
    title VARCHAR(500),
    content JSONB NOT NULL,                -- Full structured extraction
    confidence FLOAT,
    vector_ids TEXT[],                     -- References to Qdrant vectors
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit logging (append-only)
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_documents_tenant_source ON documents(tenant_id, source_type);
CREATE INDEX idx_insights_tenant_type ON insights(tenant_id, insight_type);
CREATE INDEX idx_audit_tenant_time ON audit_logs(tenant_id, created_at DESC);
```

### Qdrant collection configuration

```python
from qdrant_client.models import VectorParams, Distance, PayloadSchemaType

# Create collection with optimized settings
client.create_collection(
    collection_name="documents",
    vectors_config=VectorParams(
        size=1536,  # OpenAI text-embedding-3-small
        distance=Distance.COSINE
    ),
    # Enable payload indexing for filtering
    payload_schema={
        "tenant_id": PayloadSchemaType.KEYWORD,
        "source_type": PayloadSchemaType.KEYWORD,
        "document_id": PayloadSchemaType.KEYWORD,
        "created_at": PayloadSchemaType.DATETIME,
    }
)
```

---

## Kubernetes deployment architecture

### Resource requirements by component

| Component | Requests | Limits | Replicas | Notes |
|-----------|----------|--------|----------|-------|
| **API Gateway** | 250m CPU / 512Mi | 1 CPU / 1Gi | 2 | HPA at 70% CPU |
| **Document Workers** | 500m CPU / 1Gi | 2 CPU / 4Gi | 2-4 | Scale by queue depth |
| **Qdrant** | 500m CPU / 2Gi | 2 CPU / 8Gi | 1 | Single node for MVP |
| **PostgreSQL** | 250m CPU / 512Mi | 1 CPU / 2Gi | 1+1 replica | CloudNativePG manages HA |
| **Redis** | 100m CPU / 256Mi | 500m CPU / 1Gi | 1 | Persistence optional |
| **Prefect Server** | 250m CPU / 512Mi | 1 CPU / 1Gi | 1 | Lightweight |
| **Airbyte** | 4 CPU / 8Gi (total) | - | 1 | Includes scheduler + workers |

**Total cluster requirement**: 3 nodes × 4 CPU / 16GB RAM minimum. Estimated cost: **$200-400/month** on major cloud providers.

### Helm chart structure

```
charts/insightweave/
├── Chart.yaml
├── values.yaml                    # Defaults
├── values-dev.yaml
├── values-prod.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── hpa.yaml
│   └── pdb.yaml
└── charts/
    ├── postgresql/               # CloudNativePG subchart
    ├── qdrant/                   # Qdrant Helm chart
    └── redis/                    # Bitnami Redis
```

### ArgoCD application manifest

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: insightweave
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/company/insightweave-deploy
    targetRevision: main
    path: charts/insightweave
    helm:
      valueFiles:
        - values-prod.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: insightweave
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

---

## MVP implementation roadmap

### Phase 1: Foundation (Weeks 1-3)

**Goal**: Core ingestion and storage working end-to-end.

| Week | Tasks | Owner |
|------|-------|-------|
| 1 | Kubernetes cluster setup, Helm chart scaffolding, ArgoCD | DevOps |
| 1 | FastAPI skeleton, PostgreSQL schema, basic auth | Dev 1 |
| 1 | Qdrant deployment, embedding pipeline prototype | Dev 2 |
| 2 | Airbyte deployment, Gmail connector configuration | DevOps |
| 2 | Document ingestion flow (Airbyte → PostgreSQL → Unstructured) | Dev 1 |
| 2 | Chunking pipeline, vector storage in Qdrant | Dev 2 |
| 3 | Deduplication logic, incremental sync handling | Dev 1 |
| 3 | Basic RAG query endpoint (vector search + LLM) | Dev 2 |
| 3 | Monitoring stack (Prometheus + Grafana + Loki) | DevOps |

**Milestone**: Query any ingested Gmail email via API.

### Phase 2: Insight extraction (Weeks 4-6)

**Goal**: Structured insights extracted and queryable.

| Week | Tasks | Owner |
|------|-------|-------|
| 4 | Instructor integration, entity extraction schemas | Dev 1 |
| 4 | Slack connector (Airbyte), message normalization | Dev 2 |
| 4 | Prefect deployment, extraction workflow orchestration | DevOps |
| 5 | Risk/opportunity extraction prompts, confidence scoring | Dev 1 |
| 5 | Hybrid search (add BM25), metadata filtering | Dev 2 |
| 5 | Audit logging, basic RBAC | DevOps |
| 6 | Pattern recognition across documents | Dev 1 |
| 6 | Multi-tenant isolation, tenant API scoping | Dev 2 |
| 6 | Security hardening, secrets management | DevOps |

**Milestone**: Extract entities/risks from Slack + Gmail, searchable by tenant.

### Phase 3: Interface and outputs (Weeks 7-9)

**Goal**: Slack bot working, basic alerts, output integrations.

| Week | Tasks | Owner |
|------|-------|-------|
| 7 | Slack bot (Bolt Python), slash commands for search | Dev 1 |
| 7 | Salesforce connector, CRM data normalization | Dev 2 |
| 7 | HPA configuration, load testing | DevOps |
| 8 | Alert engine (proactive notifications to Slack) | Dev 1 |
| 8 | Jira integration (create tickets from insights) | Dev 2 |
| 8 | Backup/restore procedures, DR testing | DevOps |
| 9 | Daily digest generation and delivery | Dev 1 |
| 9 | Webhook output for custom integrations | Dev 2 |
| 9 | Customer deployment documentation | DevOps |

**Milestone**: Slack chatbot queries insights, creates Jira tickets, sends daily digests.

### Phase 4: Polish and launch (Weeks 10-12)

**Goal**: Production-ready MVP for pilot customers.

| Week | Tasks | Owner |
|------|-------|-------|
| 10 | Microsoft 365 connector (Outlook, Teams, SharePoint) | Dev 1 + Dev 2 |
| 10 | Performance optimization, query latency tuning | DevOps |
| 11 | User feedback loop (thumbs up/down on insights) | Dev 1 |
| 11 | Web dashboard prototype (optional) | Dev 2 |
| 11 | SOC 2 preparation, compliance documentation | All |
| 12 | Beta testing with pilot customer | All |
| 12 | Bug fixes, edge case handling | Dev 1 + Dev 2 |
| 12 | Runbook creation, on-call setup | DevOps |

**Launch milestone**: Production deployment for first paying customer.

### Build vs buy decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| **Data connectors** | **Buy** (Airbyte) | 600+ connectors vs weeks per custom connector |
| **Document parsing** | **Buy** (Unstructured.io) | Multi-format support, RAG-optimized |
| **Transcription** | **Buy** (Whisper API) | $0.006/min vs GPU infrastructure |
| **Vector database** | **Buy** (Qdrant) | Mature, Helm-ready, feature-complete |
| **LLM** | **Buy** (Azure OpenAI/Bedrock) | Enterprise compliance requirement |
| **Orchestration** | **Buy** (Prefect) | Python-native, minimal ops overhead |
| **Extraction logic** | **Build** | Core differentiator, domain-specific prompts |
| **RAG pipeline** | **Build** | Customization required for insight layer |
| **Slack bot** | **Build** | Primary interface, needs tight integration |
| **Alert engine** | **Build** | Business logic specific to insights |

---

## Security and compliance checklist

### SOC 2 requirements for customer-hosted

- [ ] Encryption at rest (AES-256 for databases, etcd encryption for K8s secrets)
- [ ] Encryption in transit (TLS 1.3 minimum, mTLS for internal services)
- [ ] Audit logging for all user actions with immutable storage
- [ ] RBAC with least privilege (Admin, Manager, Member, Viewer roles)
- [ ] Incident response procedures documented
- [ ] Annual penetration testing scheduled
- [ ] Shared responsibility model documented for customers

### GDPR/CCPA implementation

- [ ] Data Processing Agreement (DPA) template for customers
- [ ] Right to erasure implementation (cascade delete across all stores including vectors)
- [ ] Data export in machine-readable format (JSON/CSV)
- [ ] 72-hour breach notification procedure
- [ ] Processing activity records (RoPA) maintained
- [ ] Privacy policy with annual review cycle

### PII handling

Use **Microsoft Presidio** for PII detection before storage:
```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def anonymize_pii(text: str) -> str:
    results = analyzer.analyze(text=text, language='en')
    return anonymizer.anonymize(text=text, analyzer_results=results).text
```

---

## Conclusion: A pragmatic path to production

InsightWeave AI's architecture balances **speed-to-market** with **enterprise readiness** through three key principles:

**Minimize operational complexity**. Qdrant over Milvus, Prefect over Airflow, Redis Streams over Kafka—each choice reduces the ops burden on a 3-person team while maintaining a clear upgrade path. The stack runs on 3 modest nodes at $200-400/month.

**Buy infrastructure, build differentiation**. The insight extraction engine, RAG pipeline tuning, and pattern recognition logic are where competitive advantage lies. Everything else—connectors, parsing, transcription, vector storage—should be purchased components with proven production deployments.

**Design for multi-tenancy from day one**. Tenant isolation permeates the schema design, vector metadata, API scoping, and RBAC model. Retrofitting multi-tenancy is expensive; building it in costs little extra upfront.

The 10-12 week roadmap delivers a Slack-first MVP that ingests from Gmail, Slack, and Salesforce; extracts entities, risks, and opportunities with confidence scores; answers natural language queries with citations; creates Jira tickets from insights; and sends proactive alerts—all deployed on customer-controlled Kubernetes infrastructure with audit logging and encryption. This foundation supports adding Microsoft 365, web dashboard, and advanced pattern recognition in subsequent releases.
