# Task 7.5.1: Local Development - Docker Compose

## Context

You are setting up local development environment for ASWA at `/infrastructure/docker/`. This task focuses on Docker Compose configuration for local development.

## Objective

Create Docker Compose configurations that:
1. Run all services locally
2. Configure development databases
3. Enable hot reloading
4. Support debugging
5. Simulate production-like environment

## Requirements

### 1. Create `/infrastructure/docker/docker-compose.yaml`
```yaml
version: '3.8'

services:
  # API Gateway
  api-gateway:
    build:
      context: ../..
      dockerfile: services/api-gateway/Dockerfile
      target: development
    ports:
      - "8000:8000"
      - "5005:5005"  # Debug port
    environment:
      - SPRING_PROFILES_ACTIVE=development
      - DATABASE_URL=postgresql://aswa:aswa@postgres:5432/aswa
      - REDIS_URL=redis://redis:6379
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - INGESTION_SERVICE_URL=http://ingestion-service:8001
      - QUERY_SERVICE_URL=http://query-service:8002
      - INSIGHT_SERVICE_URL=http://insight-service:8003
      - JWT_SECRET=dev-jwt-secret-not-for-production
      - LOG_LEVEL=DEBUG
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
    volumes:
      - ../../services/api-gateway/src:/app/src:ro
      - ../../libs/common-java/src:/libs/common-java/src:ro
      - gradle-cache:/root/.gradle
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - aswa-network

  # Ingestion Service
  ingestion-service:
    build:
      context: ../..
      dockerfile: services/ingestion-service/Dockerfile
      target: development
    ports:
      - "8001:8001"
      - "5678:5678"  # Debugpy port
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql+asyncpg://aswa:aswa@postgres:5432/aswa
      - REDIS_URL=redis://redis:6379
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - INSIGHT_SERVICE_URL=http://insight-service:8003
      - S3_ENDPOINT=http://minio:9000
      - S3_BUCKET=aswa-documents
      - AWS_ACCESS_KEY_ID=minioadmin
      - AWS_SECRET_ACCESS_KEY=minioadmin
      - LOG_LEVEL=DEBUG
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
    volumes:
      - ../../services/ingestion-service/src:/app/src
      - ../../libs/common-python/src:/app/libs/common-python/src
      - uploads:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
      minio:
        condition: service_healthy
    networks:
      - aswa-network

  # Query Service
  query-service:
    build:
      context: ../..
      dockerfile: services/query-service/Dockerfile
      target: development
    ports:
      - "8002:8002"
      - "5679:5678"  # Debugpy port
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql+asyncpg://aswa:aswa@postgres:5432/aswa
      - REDIS_URL=redis://redis:6379
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - LOG_LEVEL=DEBUG
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
    volumes:
      - ../../services/query-service/src:/app/src
      - ../../libs/common-python/src:/app/libs/common-python/src
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    networks:
      - aswa-network

  # Insight Service
  insight-service:
    build:
      context: ../..
      dockerfile: services/insight-service/Dockerfile
      target: development
    ports:
      - "8003:8003"
      - "5680:5678"  # Debugpy port
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql+asyncpg://aswa:aswa@postgres:5432/aswa
      - REDIS_URL=redis://redis:6379
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - LOG_LEVEL=DEBUG
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
    volumes:
      - ../../services/insight-service/src:/app/src
      - ../../libs/common-python/src:/app/libs/common-python/src
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    networks:
      - aswa-network

  # Web Dashboard
  web-dashboard:
    build:
      context: ../../services/web-dashboard
      dockerfile: Dockerfile
      target: development
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000
    volumes:
      - ../../services/web-dashboard/src:/app/src
      - ../../services/web-dashboard/public:/app/public
      - /app/node_modules
    networks:
      - aswa-network

  # PostgreSQL
  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=aswa
      - POSTGRES_PASSWORD=aswa
      - POSTGRES_DB=aswa
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aswa"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - aswa-network

  # Redis
  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - aswa-network

  # Elasticsearch
  elasticsearch:
    image: elasticsearch:8.11.0
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 10s
      timeout: 10s
      retries: 10
    networks:
      - aswa-network

  # MinIO (S3-compatible storage)
  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"  # Console
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - minio-data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - aswa-network

  # MinIO bucket setup
  minio-setup:
    image: minio/mc
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set myminio http://minio:9000 minioadmin minioadmin;
      mc mb myminio/aswa-documents --ignore-existing;
      mc anonymous set public myminio/aswa-documents;
      exit 0;
      "
    networks:
      - aswa-network

  # Jaeger (Tracing)
  jaeger:
    image: jaegertracing/all-in-one:1.50
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - aswa-network

  # Mailpit (Email testing)
  mailpit:
    image: axllent/mailpit
    ports:
      - "1025:1025"  # SMTP
      - "8025:8025"  # Web UI
    networks:
      - aswa-network

volumes:
  postgres-data:
  redis-data:
  elasticsearch-data:
  minio-data:
  uploads:
  gradle-cache:

networks:
  aswa-network:
    driver: bridge
```

### 2. Create `/infrastructure/docker/docker-compose.override.yaml`
```yaml
# Override file for local development customization
version: '3.8'

services:
  api-gateway:
    environment:
      # Add local overrides here
      - DEBUG=true
    # Mount additional volumes for development
    volumes:
      - ../../services/api-gateway/build:/app/build:ro

  ingestion-service:
    # Enable debugger
    command: >
      python -m debugpy --listen 0.0.0.0:5678 --wait-for-client
      -m uvicorn aswa_ingestion.main:app --host 0.0.0.0 --port 8001 --reload

  query-service:
    command: >
      python -m debugpy --listen 0.0.0.0:5678 --wait-for-client
      -m uvicorn aswa_query.main:app --host 0.0.0.0 --port 8002 --reload

  insight-service:
    command: >
      python -m debugpy --listen 0.0.0.0:5678 --wait-for-client
      -m uvicorn aswa_insight.main:app --host 0.0.0.0 --port 8003 --reload
```

### 3. Create `/infrastructure/docker/docker-compose.test.yaml`
```yaml
version: '3.8'

services:
  # Test database
  postgres-test:
    image: postgres:15
    ports:
      - "5433:5432"
    environment:
      - POSTGRES_USER=aswa
      - POSTGRES_PASSWORD=aswa
      - POSTGRES_DB=aswa_test
    tmpfs:
      - /var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aswa"]
      interval: 2s
      timeout: 2s
      retries: 5
    networks:
      - aswa-test-network

  # Test Redis
  redis-test:
    image: redis:7
    ports:
      - "6380:6379"
    tmpfs:
      - /data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 2s
      retries: 5
    networks:
      - aswa-test-network

  # Test Elasticsearch
  elasticsearch-test:
    image: elasticsearch:8.11.0
    ports:
      - "9201:9200"
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms256m -Xmx256m"
    tmpfs:
      - /usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - aswa-test-network

  # Test MinIO
  minio-test:
    image: minio/minio
    ports:
      - "9002:9000"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    tmpfs:
      - /data
    command: server /data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 2s
      timeout: 2s
      retries: 5
    networks:
      - aswa-test-network

networks:
  aswa-test-network:
    driver: bridge
```

### 4. Create `/infrastructure/docker/init-db.sql`
```sql
-- Initialize ASWA database

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS documents;
CREATE SCHEMA IF NOT EXISTS insights;
CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS audit;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA documents TO aswa;
GRANT ALL PRIVILEGES ON SCHEMA insights TO aswa;
GRANT ALL PRIVILEGES ON SCHEMA users TO aswa;
GRANT ALL PRIVILEGES ON SCHEMA audit TO aswa;

-- Create tenants table
CREATE TABLE IF NOT EXISTS users.tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create users table
CREATE TABLE IF NOT EXISTS users.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES users.tenants(id),
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, email)
);

-- Create documents table
CREATE TABLE IF NOT EXISTS documents.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    name VARCHAR(500) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT,
    storage_path VARCHAR(1000),
    status VARCHAR(50) DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    uploaded_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_documents_tenant_id ON documents.documents(tenant_id);
CREATE INDEX idx_documents_status ON documents.documents(status);
CREATE INDEX idx_documents_created_at ON documents.documents(created_at DESC);

-- Create insights table
CREATE TABLE IF NOT EXISTS insights.insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    document_id UUID REFERENCES documents.documents(id),
    type VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    severity VARCHAR(50),
    confidence FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_insights_tenant_id ON insights.insights(tenant_id);
CREATE INDEX idx_insights_document_id ON insights.insights(document_id);
CREATE INDEX idx_insights_type ON insights.insights(type);
CREATE INDEX idx_insights_severity ON insights.insights(severity);

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_tenant_id ON audit.audit_log(tenant_id);
CREATE INDEX idx_audit_log_created_at ON audit.audit_log(created_at DESC);

-- Insert default tenant for development
INSERT INTO users.tenants (name, slug, settings)
VALUES ('Development', 'dev', '{"features": ["all"]}')
ON CONFLICT (slug) DO NOTHING;

-- Insert default admin user (password: admin)
INSERT INTO users.users (tenant_id, email, name, password_hash, role)
SELECT id, 'admin@aswa.local', 'Admin User',
       '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.Vzn7Xo5NeZ0Kq6', 'admin'
FROM users.tenants WHERE slug = 'dev'
ON CONFLICT (tenant_id, email) DO NOTHING;
```

### 5. Create `/infrastructure/docker/.env.example`
```bash
# ASWA Local Development Environment Variables

# API Keys (required for LLM features)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LLM_PROVIDER=openai

# Database
POSTGRES_USER=aswa
POSTGRES_PASSWORD=aswa
POSTGRES_DB=aswa

# JWT Secret (development only)
JWT_SECRET=dev-jwt-secret-not-for-production

# Feature flags
ENABLE_DEBUG_ENDPOINTS=true
ENABLE_SWAGGER_UI=true

# Log level
LOG_LEVEL=DEBUG
```

## Verification

1. Copy `.env.example` to `.env` and configure
2. Start services: `docker-compose up -d`
3. Verify all services are healthy: `docker-compose ps`
4. Access web dashboard: http://localhost:3000
5. Access API docs: http://localhost:8000/docs
6. Check Jaeger UI: http://localhost:16686
7. Check Mailpit: http://localhost:8025
