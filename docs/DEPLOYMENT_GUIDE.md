# ASWA Deployment Guide

A comprehensive guide for deploying the ASWA (AI-powered Smart Workspace Assistant) platform in both SaaS and On-Premises environments.

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Services Overview](#services-overview)
4. [Storage Requirements](#storage-requirements)
5. [SaaS Deployment (AWS)](#saas-deployment-aws)
6. [On-Premises Deployment](#on-premises-deployment)
7. [Deployment Scripts Reference](#deployment-scripts-reference)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Monitoring & Observability](#monitoring--observability)
10. [Security Configuration](#security-configuration)
11. [Troubleshooting](#troubleshooting)

---

## Platform Overview

ASWA is a microservices-based AI platform consisting of 13 services that work together to provide intelligent document processing, querying, and insights.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ASWA PLATFORM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│   │     Users    │    │   Slack/     │    │   External   │                  │
│   │   (Browser)  │    │   Teams      │    │   Webhooks   │                  │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
│          │                   │                   │                           │
│          ▼                   ▼                   ▼                           │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                    INGRESS / LOAD BALANCER                       │       │
│   │              (NGINX / AWS ALB - TLS Termination)                 │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                         │
│          ┌─────────────────────────┼─────────────────────────┐              │
│          ▼                         ▼                         ▼              │
│   ┌──────────────┐          ┌──────────────┐          ┌──────────────┐      │
│   │     Web      │          │     API      │          │   Slack/     │      │
│   │  Dashboard   │          │   Gateway    │          │  Teams Bot   │      │
│   │   (React)    │          │ (Spring Boot)│          │  (Python)    │      │
│   │   Port 3000  │          │   Port 8080  │          │  Port 8086   │      │
│   └──────────────┘          └──────┬───────┘          └──────────────┘      │
│                                    │                                         │
│   ┌────────────────────────────────┼────────────────────────────────┐       │
│   │                    INTERNAL SERVICE MESH                         │       │
│   └────────────────────────────────┼────────────────────────────────┘       │
│                                    │                                         │
│   ┌────────────┬───────────────────┼───────────────────┬────────────┐       │
│   ▼            ▼                   ▼                   ▼            ▼       │
│ ┌──────┐   ┌──────┐           ┌──────┐           ┌──────┐      ┌──────┐    │
│ │Ingest│   │Query │           │Insight│          │Notify│      │Agent │    │
│ │Svc   │   │Svc   │           │Engine │          │Svc   │      │Svc   │    │
│ │:8001 │   │:8002 │           │:8003  │          │:8005 │      │:8090 │    │
│ └──┬───┘   └──┬───┘           └──┬───┘           └──────┘      └──────┘    │
│    │          │                  │                                          │
│    └──────────┴──────────────────┴──────────────────────────────────┐       │
│                                                                      │       │
│   ┌──────────────────────────────────────────────────────────────────┼──┐   │
│   │                       DATA LAYER                                  │  │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┴─┐│   │
│   │  │PostgreSQL│  │  Redis   │  │  Elastic │  │  Vector  │  │  S3/   ││   │
│   │  │  (RDS)   │  │(Elasti-  │  │  Search  │  │   DB     │  │ MinIO  ││   │
│   │  │          │  │  Cache)  │  │(OpenSrch)│  │(Qdrant/  │  │        ││   │
│   │  │  :5432   │  │  :6379   │  │  :9200   │  │Pinecone) │  │ :9000  ││   │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘│   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Diagram

### Service Communication Flow

```
                                    ┌─────────────────┐
                                    │   User Request  │
                                    └────────┬────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                    │
│                         (Authentication & Routing)                          │
│                                                                             │
│   • JWT Token Validation        • Rate Limiting                             │
│   • Request Routing             • API Versioning                            │
│   • CORS Handling               • Request/Response Logging                  │
└────────────────────────────────────────────────────────────────────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│    INGESTION SERVICE    │   │     QUERY SERVICE       │   │    INSIGHT ENGINE       │
│                         │   │                         │   │                         │
│  • Document Upload      │   │  • Natural Language     │   │  • Pattern Detection    │
│  • File Processing      │   │    Query Processing     │   │  • Relationship Mapping │
│  • Chunking             │   │  • Vector Similarity    │   │  • Trend Analysis       │
│  • Embedding Generation │   │    Search               │   │  • Confidence Scoring   │
│                         │   │  • LLM Response         │   │                         │
└───────────┬─────────────┘   └───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │                             │
            │                             │                             │
            ▼                             ▼                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           SHARED DATA STORES                                │
│                                                                             │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐     │
│  │ PostgreSQL │    │   Redis    │    │   Vector   │    │    S3      │     │
│  │            │    │            │    │    DB      │    │            │     │
│  │ • Metadata │    │ • Cache    │    │ • Embed-   │    │ • Document │     │
│  │ • Users    │    │ • Sessions │    │   dings    │    │   Storage  │     │
│  │ • Tenants  │    │ • Queues   │    │ • Vectors  │    │ • Files    │     │
│  └────────────┘    └────────────┘    └────────────┘    └────────────┘     │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Document Processing Pipeline

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Upload  │────▶│  Parse   │────▶│  Chunk   │────▶│  Embed   │────▶│  Store   │
│          │     │          │     │          │     │          │     │          │
│ PDF/DOCX │     │ Extract  │     │ Split    │     │ OpenAI/  │     │ Vector   │
│ MD/TXT   │     │ Text     │     │ Semantic │     │ Bedrock  │     │ DB + S3  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                                                                    │
     │                                                                    │
     ▼                                                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              QUERY FLOW                                       │
│                                                                               │
│  User Query ──▶ Embed Query ──▶ Vector Search ──▶ LLM Context ──▶ Response   │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Services Overview

### Core Services

| Service | Technology | Port | Purpose |
|---------|------------|------|---------|
| **API Gateway** | Java Spring Boot | 8080 | Authentication, routing, rate limiting |
| **Web Dashboard** | React/Vite | 3000 | User interface |
| **Ingestion Service** | Python FastAPI | 8001 | Document processing and embedding |
| **Query Service** | Python FastAPI | 8002 | LLM-powered query processing |
| **Insight Engine** | Python FastAPI | 8003 | Pattern detection and analytics |

### Integration Services

| Service | Technology | Port | Purpose |
|---------|------------|------|---------|
| **Agent Service** | Python FastAPI | 8090 | AI agent management |
| **Notification Service** | Python FastAPI | 8005 | Email/push notifications |
| **Integration Service** | Python FastAPI | 8004 | Third-party connectors |
| **Slack Bot** | Python | 8086 | Slack workspace integration |
| **Teams Bot** | Python | 8087 | Microsoft Teams integration |

### Background Workers

| Worker | Purpose |
|--------|---------|
| **Document Processor** | Async document processing jobs |

---

## Storage Requirements

### Minimum Requirements by Environment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STORAGE REQUIREMENTS                                  │
├─────────────────┬───────────────┬───────────────┬───────────────────────────┤
│   Component     │  Development  │   Staging     │      Production           │
├─────────────────┼───────────────┼───────────────┼───────────────────────────┤
│ PostgreSQL      │    1 GB       │    10 GB      │  100 GB (io2, 32K IOPS)   │
│ PostgreSQL WAL  │    -          │    -          │   20 GB (gp3, 16K IOPS)   │
│ Redis           │    512 MB     │    1 GB       │    5 GB (ElastiCache)     │
│ Elasticsearch   │    2 GB       │    20 GB      │  100 GB per node          │
│ Vector DB       │    1 GB       │    10 GB      │   50 GB+ (Pinecone)       │
│ Object Storage  │    5 GB       │    50 GB      │  500 GB+ (S3)             │
├─────────────────┼───────────────┼───────────────┼───────────────────────────┤
│ TOTAL           │   ~10 GB      │   ~90 GB      │  ~775 GB+                 │
└─────────────────┴───────────────┴───────────────┴───────────────────────────┘
```

### Storage Class Configuration (Kubernetes)

```yaml
# High-Performance SSD (for databases)
aswa-ssd-io1:
  - Type: io2
  - IOPS: 32,000
  - Use: PostgreSQL primary data

# Fast SSD (for WAL, Redis)
aswa-ssd-fast:
  - Type: gp3
  - IOPS: 16,000
  - Throughput: 1000 MB/s
  - Use: PostgreSQL WAL, Redis

# Standard SSD
aswa-ssd:
  - Type: gp3
  - IOPS: 3,000
  - Use: Elasticsearch, general storage

# Shared Storage
aswa-efs:
  - Type: EFS
  - Use: Shared file access across pods
```

---

## SaaS Deployment (AWS)

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              AWS CLOUD                                      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         VPC (10.0.0.0/16)                            │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐     │   │
│  │  │                    PUBLIC SUBNETS                            │     │   │
│  │  │                                                               │     │   │
│  │  │  ┌──────────────┐         ┌──────────────┐                   │     │   │
│  │  │  │     ALB      │         │   NAT GW     │                   │     │   │
│  │  │  │  (Ingress)   │         │              │                   │     │   │
│  │  │  └──────┬───────┘         └──────────────┘                   │     │   │
│  │  └─────────┼─────────────────────────────────────────────────────┘     │   │
│  │            │                                                           │   │
│  │  ┌─────────┼─────────────────────────────────────────────────────┐     │   │
│  │  │         ▼          PRIVATE SUBNETS (EKS)                       │     │   │
│  │  │  ┌─────────────────────────────────────────────────────────┐   │     │   │
│  │  │  │                    EKS CLUSTER                           │   │     │   │
│  │  │  │                                                           │   │     │   │
│  │  │  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │     │   │
│  │  │  │   │API GW   │ │Ingestion│ │ Query   │ │ Insight │       │   │     │   │
│  │  │  │   │(3 pods) │ │(3 pods) │ │(3 pods) │ │(3 pods) │       │   │     │   │
│  │  │  │   └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │     │   │
│  │  │  │                                                           │   │     │   │
│  │  │  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │     │   │
│  │  │  │   │Dashboard│ │  Agent  │ │  Slack  │ │ Notify  │       │   │     │   │
│  │  │  │   │(3 pods) │ │(3 pods) │ │(2 pods) │ │(2 pods) │       │   │     │   │
│  │  │  │   └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │     │   │
│  │  │  └─────────────────────────────────────────────────────────┘   │     │   │
│  │  └─────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │   │
│  │  │                    PRIVATE SUBNETS (DATA)                        │     │   │
│  │  │                                                                   │     │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │     │   │
│  │  │  │   RDS    │  │ElastiCach│  │OpenSearch│  │    S3    │         │     │   │
│  │  │  │PostgreSQL│  │  Redis   │  │  (ES)    │  │ Buckets  │         │     │   │
│  │  │  │  Multi-AZ│  │ Cluster  │  │ 3-node   │  │          │         │     │   │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │     │   │
│  │  └─────────────────────────────────────────────────────────────────┘     │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │    KMS      │  │  Secrets   │  │    ECR      │  │ CloudWatch  │       │
│  │ (Encryption)│  │  Manager   │  │  (Images)   │  │ (Logging)   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
└────────────────────────────────────────────────────────────────────────────┘
```

### Step-by-Step SaaS Deployment

#### Prerequisites

```bash
# Required tools
- AWS CLI v2
- kubectl
- Helm 3.x
- Terraform 1.x
- Docker
```

#### Step 1: Infrastructure Setup (Terraform)

```bash
# Navigate to terraform directory
cd infrastructure/terraform

# Initialize and apply
terraform init
terraform plan -var-file=environments/prod.tfvars
terraform apply -var-file=environments/prod.tfvars
```

This creates:
- VPC with public/private subnets
- EKS cluster with managed node groups
- RDS PostgreSQL (Multi-AZ)
- ElastiCache Redis cluster
- OpenSearch domain
- S3 buckets
- KMS keys for encryption
- IAM roles and policies

#### Step 2: Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --region us-east-1 \
  --name aswa-prod-cluster
```

#### Step 3: Create Namespaces

```bash
# Apply namespace configurations
kubectl apply -f infrastructure/kubernetes/namespaces/
```

#### Step 4: Configure Secrets

```bash
# Create secrets from AWS Secrets Manager
kubectl apply -f infrastructure/kubernetes/security/external-secrets.yaml

# Or create manually
kubectl create secret generic aswa-secrets \
  --namespace aswa-prod \
  --from-literal=database-url="postgresql://..." \
  --from-literal=redis-url="redis://..." \
  --from-literal=jwt-secret="..."
```

#### Step 5: Deploy with Helm

```bash
# Add Bitnami repo for dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Deploy ASWA
cd infrastructure/helm/charts/aswa

helm upgrade --install aswa . \
  --namespace aswa-prod \
  --values values-prod.yaml \
  --set image.tag=v1.0.0 \
  --wait --timeout 10m
```

#### Step 6: Run Database Migrations

```bash
# Execute migration job
./scripts/db-migrate.sh migrate prod
```

#### Step 7: Verify Deployment

```bash
# Check pod status
kubectl get pods -n aswa-prod

# Check services
kubectl get svc -n aswa-prod

# Check ingress
kubectl get ingress -n aswa-prod

# Run health checks
curl https://api.aswa.io/api/v1/health
```

### Production Helm Values Summary

```yaml
# values-prod.yaml key settings

global:
  environment: production

replicaCount:
  apiGateway: 3
  ingestionService: 3
  queryService: 3
  insightService: 3
  webDashboard: 3

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPU: 70
  targetMemory: 80

resources:
  apiGateway:
    requests: { cpu: 200m, memory: 512Mi }
    limits: { cpu: 1000m, memory: 1Gi }
  ingestionService:
    requests: { cpu: 500m, memory: 1Gi }
    limits: { cpu: 2000m, memory: 4Gi }

ingress:
  enabled: true
  hosts:
    - api.aswa.io
    - app.aswa.io
  tls:
    enabled: true
    certManager: true

externalServices:
  postgresql:
    host: aswa-prod.xxxxx.us-east-1.rds.amazonaws.com
    ssl: require
  redis:
    host: aswa-prod.xxxxx.cache.amazonaws.com
    tls: true
  elasticsearch:
    host: aswa-prod.us-east-1.es.amazonaws.com
```

---

## On-Premises Deployment

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         ON-PREMISES DATA CENTER                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      NETWORK / DMZ                                   │   │
│  │                                                                       │   │
│  │  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐ │   │
│  │  │   Firewall   │────────▶│ Load Balancer│────────▶│  HAProxy/    │ │   │
│  │  │              │         │   (F5/NGINX) │         │  Traefik     │ │   │
│  │  └──────────────┘         └──────────────┘         └──────┬───────┘ │   │
│  └───────────────────────────────────────────────────────────┼─────────┘   │
│                                                               │             │
│  ┌───────────────────────────────────────────────────────────┼─────────┐   │
│  │                    KUBERNETES CLUSTER                      │         │   │
│  │                    (3+ Master, 5+ Worker Nodes)            │         │   │
│  │                                                            ▼         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    ASWA NAMESPACE                            │   │   │
│  │  │                                                               │   │   │
│  │  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │   │   │
│  │  │   │API GW   │ │Ingestion│ │ Query   │ │ Insight │           │   │   │
│  │  │   │         │ │ Service │ │ Service │ │ Engine  │           │   │   │
│  │  │   └─────────┘ └─────────┘ └─────────┘ └─────────┘           │   │   │
│  │  │                                                               │   │   │
│  │  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │   │   │
│  │  │   │Dashboard│ │  Agent  │ │ Notify  │ │ Integr. │           │   │   │
│  │  │   │         │ │ Service │ │ Service │ │ Service │           │   │   │
│  │  │   └─────────┘ └─────────┘ └─────────┘ └─────────┘           │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    MONITORING NAMESPACE                      │   │   │
│  │  │   Prometheus │ Grafana │ Jaeger │ Fluent Bit │ Loki         │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      DATA TIER (Physical/VM)                         │   │
│  │                                                                       │   │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │   │
│  │   │ PostgreSQL  │   │    Redis    │   │ Elasticsearch│               │   │
│  │   │  Primary +  │   │   Primary + │   │   3-node     │               │   │
│  │   │  Replica    │   │   Replica   │   │   Cluster    │               │   │
│  │   └─────────────┘   └─────────────┘   └─────────────┘               │   │
│  │                                                                       │   │
│  │   ┌─────────────┐   ┌─────────────┐                                   │   │
│  │   │   Qdrant    │   │    MinIO    │                                   │   │
│  │   │  (Vector)   │   │  (S3-compat)│                                   │   │
│  │   │   Cluster   │   │   Cluster   │                                   │   │
│  │   └─────────────┘   └─────────────┘                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      STORAGE (SAN/NAS)                               │   │
│  │                                                                       │   │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │   │
│  │   │ PostgreSQL  │   │    MinIO    │   │    Logs     │               │   │
│  │   │   Volumes   │   │   Volumes   │   │   Volumes   │               │   │
│  │   │   500 GB    │   │   1+ TB     │   │   200 GB    │               │   │
│  │   └─────────────┘   └─────────────┘   └─────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

### Hardware Requirements

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MINIMUM HARDWARE REQUIREMENTS                            │
├─────────────────────┬───────────────────────────────────────────────────────┤
│                     │              SPECIFICATIONS                            │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ Kubernetes Masters  │ 3x servers: 4 CPU, 16 GB RAM, 100 GB SSD each        │
│ (Control Plane)     │                                                        │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ Kubernetes Workers  │ 5x servers: 8 CPU, 32 GB RAM, 200 GB SSD each        │
│ (Application Nodes) │ (Scale based on workload)                             │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ PostgreSQL          │ 2x servers: 8 CPU, 32 GB RAM, 500 GB NVMe SSD        │
│ (Primary + Replica) │ (Dedicated for database)                              │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ Redis               │ 2x servers: 4 CPU, 16 GB RAM, 50 GB SSD              │
│ (Primary + Replica) │                                                        │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ Elasticsearch       │ 3x servers: 8 CPU, 32 GB RAM, 500 GB SSD each        │
│ (3-node cluster)    │                                                        │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ Qdrant (Vector DB)  │ 3x servers: 4 CPU, 16 GB RAM, 200 GB SSD each        │
│                     │                                                        │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ MinIO (S3-compat)   │ 4x servers: 4 CPU, 16 GB RAM, 1 TB HDD each          │
│                     │                                                        │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ Load Balancer       │ 2x servers: 4 CPU, 8 GB RAM (HA pair)                 │
├─────────────────────┴───────────────────────────────────────────────────────┤
│ TOTAL: ~24 servers, 164 CPU cores, 480 GB RAM, ~6 TB storage                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Step-by-Step On-Premises Deployment

#### Step 1: Prepare Infrastructure

```bash
# Install Kubernetes (example with kubeadm)
# On all nodes:
curl -fsSL https://get.docker.com | sh
apt-get install -y kubelet kubeadm kubectl

# On master nodes:
kubeadm init --control-plane-endpoint "k8s-lb.internal:6443" \
  --upload-certs \
  --pod-network-cidr=10.244.0.0/16

# Install CNI (Calico recommended for on-prem)
kubectl apply -f https://docs.projectcalico.org/manifests/calico.yaml
```

#### Step 2: Deploy Data Services

**PostgreSQL (Using Bitnami Helm Chart):**
```bash
helm install postgresql bitnami/postgresql \
  --namespace aswa-data \
  --set auth.postgresPassword=<secure-password> \
  --set auth.database=aswa \
  --set primary.persistence.size=100Gi \
  --set architecture=replication \
  --set readReplicas.replicaCount=1
```

**Redis:**
```bash
helm install redis bitnami/redis \
  --namespace aswa-data \
  --set auth.password=<secure-password> \
  --set architecture=replication \
  --set replica.replicaCount=1
```

**Elasticsearch:**
```bash
helm install elasticsearch bitnami/elasticsearch \
  --namespace aswa-data \
  --set master.replicaCount=3 \
  --set data.replicaCount=3 \
  --set coordinating.replicaCount=2
```

**MinIO:**
```bash
helm install minio bitnami/minio \
  --namespace aswa-data \
  --set auth.rootUser=admin \
  --set auth.rootPassword=<secure-password> \
  --set mode=distributed \
  --set statefulset.replicaCount=4
```

**Qdrant (Vector Database):**
```bash
helm repo add qdrant https://qdrant.to/helm
helm install qdrant qdrant/qdrant \
  --namespace aswa-data \
  --set replicaCount=3 \
  --set persistence.size=50Gi
```

#### Step 3: Build and Push Images

```bash
# Set up local registry (or use Harbor)
docker run -d -p 5000:5000 --name registry registry:2

# Build images
cd services/api-gateway
docker build -t localhost:5000/aswa/api-gateway:v1.0.0 .
docker push localhost:5000/aswa/api-gateway:v1.0.0

# Repeat for all services...
```

#### Step 4: Configure Values for On-Prem

```yaml
# values-onprem.yaml

global:
  environment: onprem
  imageRegistry: registry.internal:5000

externalServices:
  postgresql:
    host: postgresql.aswa-data.svc.cluster.local
    port: 5432
    ssl: prefer
  redis:
    host: redis-master.aswa-data.svc.cluster.local
    port: 6379
  elasticsearch:
    host: elasticsearch.aswa-data.svc.cluster.local
    port: 9200
  minio:
    endpoint: http://minio.aswa-data.svc.cluster.local:9000
    bucket: aswa-documents
  qdrant:
    host: qdrant.aswa-data.svc.cluster.local
    port: 6333

# Use internal LLM or configure external
llm:
  provider: ollama  # or external API
  endpoint: http://ollama.aswa-data.svc.cluster.local:11434

ingress:
  enabled: true
  className: nginx
  hosts:
    - aswa.internal.company.com
  tls:
    enabled: true
    secretName: aswa-tls-cert
```

#### Step 5: Deploy ASWA

```bash
# Create namespace
kubectl create namespace aswa

# Deploy
helm upgrade --install aswa ./infrastructure/helm/charts/aswa \
  --namespace aswa \
  --values values-onprem.yaml \
  --wait --timeout 10m

# Run migrations
kubectl exec -it deploy/api-gateway -n aswa -- \
  ./scripts/db-migrate.sh migrate prod
```

#### Step 6: Configure Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: aswa-ingress
  namespace: aswa
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - aswa.internal.company.com
      secretName: aswa-tls-cert
  rules:
    - host: aswa.internal.company.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 8080
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web-dashboard
                port:
                  number: 3000
```

---

## Deployment Scripts Reference

### Database Migration Script

```bash
# scripts/db-migrate.sh

Usage: ./scripts/db-migrate.sh <command> <environment>

Commands:
  migrate   - Run pending migrations
  info      - Show migration status
  validate  - Validate migrations
  clean     - Clean database (DANGER!)
  baseline  - Baseline existing database
  repair    - Repair migration history

Environments:
  dev       - Development database
  test      - Test database
  prod      - Production database

Examples:
  ./scripts/db-migrate.sh migrate dev
  ./scripts/db-migrate.sh info prod
```

### Development Script

```bash
# scripts/dev.sh

Usage: ./scripts/dev.sh <command>

Commands:
  up        - Start all services
  down      - Stop all services
  logs      - View logs
  ps        - Show running services
  build     - Build all images
  clean     - Remove all containers and volumes

Examples:
  ./scripts/dev.sh up
  ./scripts/dev.sh logs api-gateway
```

### Deployment Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT WORKFLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Developer                    CI/CD Pipeline                    Production
    │                              │                               │
    │  git push                    │                               │
    ├─────────────────────────────▶│                               │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │   1. Run Tests    │                     │
    │                    │   - Unit Tests    │                     │
    │                    │   - Lint          │                     │
    │                    │   - Security Scan │                     │
    │                    └─────────┬─────────┘                     │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │  2. Build Images  │                     │
    │                    │   - Multi-arch    │                     │
    │                    │   - Push to ECR   │                     │
    │                    └─────────┬─────────┘                     │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │ 3. Deploy Staging │                     │
    │                    │   - Helm upgrade  │                     │
    │                    │   - Run E2E tests │                     │
    │                    └─────────┬─────────┘                     │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │ 4. Manual Approval│                     │
    │◀───────────────────│   (for prod)      │                     │
    │   Approve?         └─────────┬─────────┘                     │
    │                              │                               │
    ├─────────────────────────────▶│                               │
    │   Yes                        │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │5. Backup Database │                     │
    │                    └─────────┬─────────┘                     │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │  6. Canary Deploy │────────────────────▶│
    │                    │   (10% traffic)   │         10%         │
    │                    └─────────┬─────────┘                     │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │ 7. Health Checks  │                     │
    │                    │   - Error rates   │                     │
    │                    │   - Latency       │                     │
    │                    └─────────┬─────────┘                     │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │  8. Full Rollout  │────────────────────▶│
    │                    │   (100% traffic)  │        100%         │
    │                    └─────────┬─────────┘                     │
    │                              │                               │
    │                    ┌─────────┴─────────┐                     │
    │                    │  9. Notify Team   │                     │
    │◀───────────────────│   (Slack/Email)   │                     │
    │                    └───────────────────┘                     │
    │                                                              │
```

---

## CI/CD Pipeline

### Pipeline Overview

```yaml
# .github/workflows/ structure

├── ci.yaml                 # Main CI pipeline (tests, lint, security)
├── build-images.yaml       # Build and push Docker images
├── deploy-staging.yaml     # Deploy to staging environment
├── deploy-production.yaml  # Deploy to production (with approval)
├── rollback.yaml          # Rollback to previous version
├── e2e-tests.yaml         # End-to-end tests
├── security-scan.yaml     # Security scanning
└── release.yaml           # Create GitHub releases
```

### Key Pipeline Features

| Feature | Description |
|---------|-------------|
| **Multi-arch builds** | Builds for both amd64 and arm64 |
| **Parallel testing** | Runs tests across services in parallel |
| **Canary deployments** | 10% traffic before full rollout |
| **Automated rollback** | Auto-rollback on health check failures |
| **Database backups** | Full backup before production deploys |
| **E2E validation** | Playwright tests after deployment |

---

## Monitoring & Observability

### Monitoring Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OBSERVABILITY STACK                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          METRICS                                      │   │
│  │                                                                        │   │
│  │   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐          │   │
│  │   │   Service   │─────▶│ Prometheus  │─────▶│   Grafana   │          │   │
│  │   │   Metrics   │      │             │      │ Dashboards  │          │   │
│  │   │   (:9090)   │      │  (scraping) │      │             │          │   │
│  │   └─────────────┘      └─────────────┘      └─────────────┘          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          TRACING                                      │   │
│  │                                                                        │   │
│  │   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐          │   │
│  │   │   Service   │─────▶│OpenTelemetry│─────▶│   Jaeger    │          │   │
│  │   │   Spans     │      │  Collector  │      │     UI      │          │   │
│  │   │             │      │             │      │             │          │   │
│  │   └─────────────┘      └─────────────┘      └─────────────┘          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          LOGGING                                      │   │
│  │                                                                        │   │
│  │   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐          │   │
│  │   │   Service   │─────▶│  Fluent Bit │─────▶│    Loki     │          │   │
│  │   │    Logs     │      │             │      │             │          │   │
│  │   │   (stdout)  │      │ (collector) │      │  (storage)  │          │   │
│  │   └─────────────┘      └─────────────┘      └─────────────┘          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         ALERTING                                      │   │
│  │                                                                        │   │
│  │   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐          │   │
│  │   │ Prometheus  │─────▶│AlertManager │─────▶│Slack/PagerD │          │   │
│  │   │   Rules     │      │             │      │   uty       │          │   │
│  │   └─────────────┘      └─────────────┘      └─────────────┘          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| ServiceDown | Pod not ready > 1m | Critical |
| HighErrorRate | Error rate > 5% | Warning |
| HighErrorRateCritical | Error rate > 20% | Critical |
| HighLatency | P99 > 2s | Warning |
| HighLatencyCritical | P99 > 5s | Critical |
| DiskSpaceLow | Disk usage > 80% | Warning |
| MemoryHigh | Memory usage > 90% | Warning |

---

## Security Configuration

### Security Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY LAYERS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAYER 1: NETWORK                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  • TLS 1.3 for all external traffic                                  │   │
│  │  • Network policies (default deny)                                    │   │
│  │  • Private subnets for data stores                                    │   │
│  │  • WAF for API endpoints                                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LAYER 2: AUTHENTICATION                                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  • JWT tokens with short expiry                                       │   │
│  │  • OAuth 2.0 for third-party integrations                             │   │
│  │  • API key rotation                                                    │   │
│  │  • Multi-factor authentication (optional)                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LAYER 3: AUTHORIZATION                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  • Role-based access control (RBAC)                                   │   │
│  │  • Tenant isolation                                                    │   │
│  │  • Resource-level permissions                                          │   │
│  │  • Audit logging                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LAYER 4: DATA PROTECTION                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  • Encryption at rest (KMS)                                           │   │
│  │  • Encryption in transit (TLS)                                        │   │
│  │  • Secrets management (External Secrets)                              │   │
│  │  • Data masking in logs                                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LAYER 5: CONTAINER SECURITY                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  • Non-root containers                                                │   │
│  │  • Read-only root filesystem                                          │   │
│  │  • No privilege escalation                                            │   │
│  │  • Dropped capabilities                                               │   │
│  │  • Seccomp profiles                                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pod Security Context (Production)

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

containerSecurityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
```

---

## Troubleshooting

### Common Issues and Solutions

#### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n aswa -o wide

# Check pod events
kubectl describe pod <pod-name> -n aswa

# Check logs
kubectl logs <pod-name> -n aswa --previous

# Common causes:
# - Image pull errors: Check registry credentials
# - Resource limits: Increase requests/limits
# - Liveness probe failures: Check health endpoints
```

#### Database Connection Issues

```bash
# Test connectivity from pod
kubectl exec -it <pod> -n aswa -- nc -zv postgresql.aswa-data 5432

# Check secrets
kubectl get secret aswa-secrets -n aswa -o yaml

# Verify connection string format
postgresql://user:password@host:5432/database?sslmode=require
```

#### High Latency

```bash
# Check resource usage
kubectl top pods -n aswa

# Check HPA status
kubectl get hpa -n aswa

# Scale manually if needed
kubectl scale deployment api-gateway -n aswa --replicas=5

# Check for slow queries
# Connect to PostgreSQL and run:
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

#### Certificate Issues

```bash
# Check certificate status
kubectl get certificates -n aswa

# Check cert-manager logs
kubectl logs -n cert-manager deploy/cert-manager

# Manually renew certificate
kubectl delete certificate aswa-tls -n aswa
kubectl apply -f ingress.yaml
```

### Useful Commands

```bash
# View all resources in namespace
kubectl get all -n aswa

# Check resource quotas
kubectl describe resourcequota -n aswa

# View recent events
kubectl get events -n aswa --sort-by=.lastTimestamp

# Port forward for debugging
kubectl port-forward svc/api-gateway 8080:8080 -n aswa

# Execute shell in pod
kubectl exec -it deploy/api-gateway -n aswa -- /bin/sh

# View Helm release status
helm status aswa -n aswa

# Rollback Helm release
helm rollback aswa <revision> -n aswa
```

---

## Quick Reference

### Environment URLs

| Environment | API URL | Dashboard URL |
|-------------|---------|---------------|
| Development | http://localhost:8080 | http://localhost:3000 |
| Staging | https://api.staging.aswa.io | https://app.staging.aswa.io |
| Production | https://api.aswa.io | https://app.aswa.io |

### Port Reference

| Service | Port | Metrics Port |
|---------|------|--------------|
| API Gateway | 8080 | 9090 |
| Ingestion Service | 8001 | 9091 |
| Query Service | 8002 | 9092 |
| Insight Engine | 8003 | 9093 |
| Web Dashboard | 3000 | - |
| Agent Service | 8090 | 9094 |
| Notification Service | 8005 | 9095 |

### Health Check Endpoints

```bash
# All services expose:
GET /health         # Basic health
GET /health/ready   # Readiness (for K8s)
GET /health/live    # Liveness (for K8s)
```

---

## Support

For issues and questions:
- **Documentation**: `/docs/`
- **Issues**: https://github.com/your-org/aswa/issues
- **Slack**: #aswa-support

---

*Last Updated: January 2026*
