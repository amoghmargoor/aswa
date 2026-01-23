# ASWA Phase 1: Foundation (Weeks 1-2)

## Monorepo Structure Overview

```
aswa/
├── .github/workflows/           # CI/CD pipelines
├── build.gradle.kts             # Root Gradle (Java)
├── pyproject.toml               # Root Poetry (Python)
├── docker-compose.yml           # Local development
├── Makefile                     # Common commands
├── infrastructure/              # Helm, K8s, Docker
│   ├── helm/aswa/
│   ├── docker/
│   └── k8s/
├── libs/                        # Shared libraries
│   ├── common-java/
│   └── common-python/
├── services/                    # Microservices
│   ├── api-gateway/             # Java
│   ├── ingestion-service/       # Python
│   ├── insight-engine/          # Python
│   ├── query-service/           # Python
│   ├── notification-service/    # Java
│   ├── integration-service/     # Java
│   └── slack-bot/               # Python
├── workers/                     # Background workers
│   ├── document-processor/      # Python
│   └── pattern-analyzer/        # Python
├── migrations/postgresql/       # Database migrations
└── scripts/                     # Utility scripts
```

---

## Task 1.1: Initialize Monorepo Structure

### Subtask 1.1.1: Create Root Project Configuration

**Claude Code Prompt:**
```
Create the root configuration for a Java/Python monorepo named "aswa" for an enterprise AI insight aggregation platform.

Create these files:

1. /settings.gradle.kts:
- Gradle 8.5+ with Kotlin DSL
- Include Java subprojects: libs:common-java, services:api-gateway, services:notification-service, services:integration-service
- Enable type-safe project accessors
- Configure plugin management for Spring Boot 3.2.x, Kotlin, Spotless

2. /build.gradle.kts:
- Java 21 toolchain
- Plugins: java, jacoco, spotless (Google Java Format), errorprone
- Subprojects block with common dependencies: SLF4J 2.x, Logback 1.4.x, Micrometer 1.12.x, JUnit 5.10.x, Mockito 5.x, AssertJ 3.x
- JaCoCo minimum 80% coverage
- Spotless with Google Java Format
- Custom tasks: checkAll, testAll

3. /gradle.properties:
- org.gradle.parallel=true
- org.gradle.caching=true
- Version properties for all dependencies

4. /pyproject.toml (Poetry workspace):
- Python >=3.11,<3.13
- Dev dependencies: pytest>=8.0, pytest-asyncio>=0.23, pytest-cov>=4.1, black>=24.0, ruff>=0.2, mypy>=1.8, pre-commit>=3.6
- pytest: asyncio_mode=auto, testpaths=["tests"]
- black: line-length=100
- ruff: select=["E","F","W","I","N","UP","B","C4","SIM"]
- mypy: strict=true, ignore_missing_imports=true

5. /Makefile with targets:
- setup: Install all dependencies (gradle, poetry)
- build: Build all services
- test: Run all tests with coverage
- test-java: Run Java tests only
- test-python: Run Python tests only
- lint: Run all linters
- format: Format all code
- docker-build: Build all Docker images
- docker-push: Push to registry
- helm-lint: Lint Helm charts
- clean: Clean all build artifacts
- help: Show all targets with descriptions

6. /.pre-commit-config.yaml:
- trailing-whitespace, end-of-file-fixer, check-yaml, check-json
- black (Python)
- ruff (Python)
- gradle spotlessCheck

7. /.gitignore (comprehensive for Java, Python, IDE, env files)

8. /README.md:
- Project overview: "ASWA - AI-driven insight aggregation platform"
- Prerequisites: Java 21, Python 3.11+, Docker 24+, Kubernetes 1.28+, Helm 3.x
- Quick start with make setup && make build && make test
- Architecture overview
- Development workflow

9. /.env.example with all required environment variables

All configs must follow 12-factor app principles.
```

---

### Subtask 1.1.2: Create Shared Java Library

**Claude Code Prompt:**
```
Create the shared Java library at /libs/common-java/ for the aswa monorepo.

1. /libs/common-java/build.gradle.kts:
- Apply java-library plugin
- Dependencies:
  - api: slf4j-api:2.0.11, jackson-databind:2.16.x, jackson-datatype-jsr310, micrometer-core:1.12.x
  - implementation: caffeine:3.1.x, resilience4j-circuitbreaker:2.2.x, resilience4j-retry, resilience4j-ratelimiter
  - testImplementation: junit-jupiter:5.10.x, mockito-core:5.x, assertj-core:3.x, testcontainers:1.19.x

2. /libs/common-java/src/main/java/com/aswa/common/exception/:

AswaException.java:
- Extends RuntimeException
- Fields: ErrorCode errorCode, Map<String, Object> metadata, String requestId
- Builder pattern
- Constructors for message, cause, errorCode combinations

ErrorCode.java (enum):
- VALIDATION_ERROR(400), NOT_FOUND(404), UNAUTHORIZED(401), FORBIDDEN(403)
- CONFLICT(409), RATE_LIMITED(429), EXTERNAL_SERVICE_ERROR(502), INTERNAL_ERROR(500)
- Fields: int httpStatus, String code
- Method: toApiError()

3. /libs/common-java/src/main/java/com/aswa/common/model/:

TenantContext.java (record):
- UUID tenantId, UUID userId, Set<String> roles, Map<String, String> metadata
- Static factory: of(tenantId, userId, roles)
- Method: hasRole(String role), isAdmin()

ApiResponse.java (generic record):
- boolean success, T data, ApiError error, Instant timestamp, String requestId
- Static factories: success(data), error(ApiError), error(ErrorCode, message)

ApiError.java (record):
- String code, String message, Map<String, Object> details

PageRequest.java (record):
- int page (default 0), int size (default 20, max 100), String sortBy, SortDirection direction
- Validation in compact constructor
- Method: toSpringPageable()

PageResponse.java (generic record):
- List<T> content, long totalElements, int totalPages, int currentPage, int pageSize
- Static factory: of(Page<T> springPage)

4. /libs/common-java/src/main/java/com/aswa/common/config/:

ResilienceConfig.java:
- Static factory methods:
  - createCircuitBreaker(name, failureRateThreshold, waitDuration)
  - createRetry(name, maxAttempts, waitDuration)
  - createRateLimiter(name, limitForPeriod, limitRefreshPeriod)
- Default configurations with sensible production values

5. /libs/common-java/src/main/java/com/aswa/common/logging/:

LoggingContext.java:
- Static methods: setRequestId(String), setTenantId(UUID), setUserId(UUID), setTraceId(String)
- Method: clear()
- Uses MDC internally

StructuredLogger.java:
- Wraps SLF4J Logger
- Methods: info(message, fields...), error(message, throwable, fields...)
- Automatically includes MDC context
- Field class for type-safe key-value pairs

6. /libs/common-java/src/main/java/com/aswa/common/util/:

JsonUtils.java:
- Singleton ObjectMapper configured: FAIL_ON_UNKNOWN_PROPERTIES=false, JavaTimeModule registered, ISO dates
- Methods: toJson(Object), fromJson(String, Class), fromJson(String, TypeReference)

HashUtils.java:
- Methods: md5(String), md5(byte[]), sha256(String), sha256(byte[])
- Return hex-encoded strings

ValidationUtils.java:
- Methods: requireNotBlank(String, fieldName), requireNotNull(Object, fieldName), requireValidEmail(String), requireValidUuid(String)
- Throw AswaException with VALIDATION_ERROR

7. /libs/common-java/src/main/resources/logback.xml:
- JSON encoder for production (net.logstash.logback.encoder.LogstashEncoder)
- Console encoder for dev (based on ASWA_ENV environment variable)
- Include MDC fields: requestId, tenantId, userId, traceId

8. /libs/common-java/src/test/java/com/aswa/common/:
- Unit tests for every class achieving 90%+ coverage
- ErrorCodeTest.java, AswaExceptionTest.java
- ApiResponseTest.java, PageRequestTest.java, PageResponseTest.java
- ResilienceConfigTest.java (verify configurations)
- LoggingContextTest.java (verify MDC operations)
- JsonUtilsTest.java (serialization edge cases)
- HashUtilsTest.java (known hash values)
- ValidationUtilsTest.java (valid and invalid inputs)

Use JUnit 5 @ParameterizedTest where appropriate.
Every class must have Javadoc.
Use @NonNull/@Nullable annotations from JSpecify.
```

---

### Subtask 1.1.3: Create Shared Python Library

**Claude Code Prompt:**
```
Create the shared Python library at /libs/common-python/ for the aswa monorepo.

1. /libs/common-python/pyproject.toml:
- name = "aswa-common"
- version = "0.1.0"
- python = ">=3.11,<3.13"
- dependencies:
  - pydantic>=2.6
  - pydantic-settings>=2.1
  - structlog>=24.1
  - tenacity>=8.2
  - redis>=5.0
  - httpx>=0.26
  - prometheus-client>=0.19
- dev-dependencies:
  - pytest>=8.0
  - pytest-asyncio>=0.23
  - pytest-cov>=4.1
  - respx>=0.20
  - fakeredis>=2.21

2. /libs/common-python/src/aswa_common/__init__.py:
- Export: AswaError, TenantContext, ApiResponse, configure_logging

3. /libs/common-python/src/aswa_common/exceptions.py:

class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    @property
    def http_status(self) -> int: ...

class AswaError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None, cause: Exception | None = None): ...
    
    def to_api_response(self) -> dict: ...

class ValidationError(AswaError): ...  # Defaults to VALIDATION_ERROR
class NotFoundError(AswaError): ...    # Defaults to NOT_FOUND
class UnauthorizedError(AswaError): ... # Defaults to UNAUTHORIZED
class RateLimitError(AswaError): ...   # Defaults to RATE_LIMITED
class ExternalServiceError(AswaError): ... # Defaults to EXTERNAL_SERVICE_ERROR

4. /libs/common-python/src/aswa_common/models/__init__.py:
- Export all models

/libs/common-python/src/aswa_common/models/tenant.py:
class TenantContext(BaseModel):
    tenant_id: UUID
    user_id: UUID | None = None
    roles: set[str] = Field(default_factory=set)
    metadata: dict[str, str] = Field(default_factory=dict)
    
    def has_role(self, role: str) -> bool: ...
    def is_admin(self) -> bool: ...

/libs/common-python/src/aswa_common/models/responses.py:
class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiError | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str | None = None
    
    @classmethod
    def ok(cls, data: T) -> "ApiResponse[T]": ...
    
    @classmethod
    def fail(cls, error: AswaError) -> "ApiResponse[None]": ...

class PageRequest(BaseModel):
    page: int = Field(default=0, ge=0)
    size: int = Field(default=20, ge=1, le=100)
    sort_by: str | None = None
    sort_direction: Literal["asc", "desc"] = "desc"

class PageResponse(BaseModel, Generic[T]):
    content: list[T]
    total_elements: int
    total_pages: int
    current_page: int
    page_size: int

/libs/common-python/src/aswa_common/models/documents.py:
class NormalizedDocument(BaseModel):
    source_id: str
    document_id: str
    content: str
    content_type: Literal["email", "message", "document", "transcript"]
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    version_hash: str
    
    @field_validator("version_hash")
    def validate_hash(cls, v): ...  # Must be 32-char hex

5. /libs/common-python/src/aswa_common/config/settings.py:
class BaseSettings(PydanticBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    app_name: str = "aswa"
    environment: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False
    log_level: str = "INFO"

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    host: str = "localhost"
    port: int = 5432
    name: str = "aswa"
    user: str = "aswa"
    password: SecretStr
    pool_size: int = 5
    max_overflow: int = 10
    
    @property
    def async_url(self) -> str: ...  # postgresql+asyncpg://...

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    host: str = "localhost"
    port: int = 6379
    password: SecretStr | None = None
    db: int = 0
    
    @property
    def url(self) -> str: ...

class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    provider: Literal["bedrock", "azure_openai"] = "bedrock"
    model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    aws_region: str = "us-east-1"
    azure_endpoint: str | None = None
    azure_api_key: SecretStr | None = None
    max_tokens: int = 4096
    temperature: float = 0.0

6. /libs/common-python/src/aswa_common/logging/setup.py:
import structlog

def configure_logging(service_name: str, log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog with JSON output for production."""
    # Configure processors: add_log_level, TimeStamper, JSONRenderer (or ConsoleRenderer for dev)
    # Add context processors for request_id, tenant_id, user_id

class LoggerContextVar:
    """Context variables for request-scoped logging."""
    request_id: ContextVar[str | None]
    tenant_id: ContextVar[UUID | None]
    user_id: ContextVar[UUID | None]
    
    @classmethod
    def set(cls, **kwargs): ...
    
    @classmethod
    def clear(cls): ...

def get_logger(name: str) -> structlog.BoundLogger: ...

7. /libs/common-python/src/aswa_common/resilience.py:
from tenacity import ...

def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator factory for exponential backoff with jitter."""
    ...

class CircuitBreaker:
    """Simple circuit breaker implementation."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0): ...
    async def call(self, func: Callable, *args, **kwargs): ...
    @property
    def is_open(self) -> bool: ...

8. /libs/common-python/src/aswa_common/metrics.py:
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

class MetricsRegistry:
    def __init__(self, service_name: str, registry: CollectorRegistry | None = None): ...
    
    def counter(self, name: str, description: str, labels: list[str] = None) -> Counter: ...
    def histogram(self, name: str, description: str, labels: list[str] = None, buckets: list[float] = None) -> Histogram: ...
    def gauge(self, name: str, description: str, labels: list[str] = None) -> Gauge: ...

def timed(histogram: Histogram, labels: dict = None) -> Callable:
    """Decorator to time async functions and record to histogram."""
    ...

9. /libs/common-python/src/aswa_common/clients/base.py:
class BaseHttpClient:
    """Base HTTP client with retry, circuit breaker, and observability."""
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        circuit_breaker: CircuitBreaker | None = None,
        metrics: MetricsRegistry | None = None
    ): ...
    
    async def get(self, path: str, params: dict = None, headers: dict = None) -> httpx.Response: ...
    async def post(self, path: str, json: dict = None, headers: dict = None) -> httpx.Response: ...
    async def put(self, path: str, json: dict = None, headers: dict = None) -> httpx.Response: ...
    async def delete(self, path: str, headers: dict = None) -> httpx.Response: ...
    
    async def close(self): ...
    async def __aenter__(self): ...
    async def __aexit__(self, ...): ...

10. /libs/common-python/src/aswa_common/utils/:

hashing.py:
def md5_hash(content: str | bytes) -> str: ...
def sha256_hash(content: str | bytes) -> str: ...
async def md5_hash_file(file_path: Path) -> str: ...

validation.py:
def validate_email(email: str) -> str: ...  # Returns validated or raises ValidationError
def validate_uuid(value: str) -> UUID: ...
def validate_not_blank(value: str, field_name: str) -> str: ...

11. /libs/common-python/tests/:

conftest.py:
- Fixtures: tenant_context, api_response, mock_redis (fakeredis), event_loop

test_exceptions.py:
- Test all exception classes
- Test error code HTTP status mapping
- Test to_api_response()

test_models.py:
- Test TenantContext, ApiResponse, PageRequest, PageResponse, NormalizedDocument
- Test validation, serialization, factory methods

test_logging.py:
- Test configure_logging
- Test context variables
- Test JSON output format

test_resilience.py:
- Test retry decorator with mock failures
- Test circuit breaker state transitions

test_clients.py:
- Test BaseHttpClient with respx mocking
- Test retry behavior
- Test circuit breaker integration

All tests must use pytest-asyncio, achieve 90%+ coverage.
All code must have type hints and docstrings.
```

---

## Task 1.2: Database Layer Setup

### Subtask 1.2.1: PostgreSQL Schema and Migrations

**Claude Code Prompt:**
```
Create the PostgreSQL database schema and migration setup at /migrations/postgresql/.

1. /migrations/postgresql/V001__initial_schema.sql:

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Tenants
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    settings JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'manager', 'member', 'viewer')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'deleted')),
    settings JSONB NOT NULL DEFAULT '{}',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

-- Data Sources
CREATE TABLE data_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('gmail', 'outlook', 'slack', 'teams', 'gdrive', 'sharepoint', 'salesforce', 'zoho', 'confluence', 'notion', 'zoom', 'custom')),
    name VARCHAR(255) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    credentials_encrypted BYTEA,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'error', 'deleted')),
    last_sync_at TIMESTAMPTZ,
    sync_cursor TEXT,
    error_message TEXT,
    sync_frequency_minutes INT NOT NULL DEFAULT 60,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Documents
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    data_source_id UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    external_id VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    title VARCHAR(1000),
    content TEXT,
    content_type VARCHAR(100) NOT NULL CHECK (content_type IN ('email', 'message', 'document', 'transcript', 'note', 'ticket')),
    source_url TEXT,
    source_metadata JSONB NOT NULL DEFAULT '{}',
    processed_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (processed_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
    processed_at TIMESTAMPTZ,
    error_message TEXT,
    word_count INT,
    language VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, data_source_id, external_id)
);

-- Document Chunks
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    token_count INT NOT NULL,
    vector_id VARCHAR(100),
    start_char INT,
    end_char INT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- Insights
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    insight_type VARCHAR(50) NOT NULL CHECK (insight_type IN ('entity', 'risk', 'opportunity', 'pattern', 'relationship', 'trend', 'anomaly')),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    content JSONB NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    severity VARCHAR(50) CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    category VARCHAR(100),
    tags TEXT[] DEFAULT '{}',
    source_documents UUID[] NOT NULL,
    evidence_snippets TEXT[],
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'dismissed', 'resolved')),
    user_feedback VARCHAR(50) CHECK (user_feedback IN ('confirmed', 'rejected', 'modified')),
    feedback_by UUID REFERENCES users(id),
    feedback_comment TEXT,
    feedback_at TIMESTAMPTZ,
    vector_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Entity Relationships
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_insight_id UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    target_insight_id UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,
    direction VARCHAR(20) NOT NULL DEFAULT 'directed' CHECK (direction IN ('directed', 'bidirectional')),
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_insight_id, target_insight_id, relationship_type)
);

-- Alert Configurations
CREATE TABLE alert_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    pattern_query TEXT NOT NULL,
    conditions JSONB NOT NULL DEFAULT '{}',
    notification_channels JSONB NOT NULL,
    frequency VARCHAR(50) NOT NULL DEFAULT 'realtime' CHECK (frequency IN ('realtime', 'hourly', 'daily', 'weekly')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'deleted')),
    last_triggered_at TIMESTAMPTZ,
    trigger_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Alert History
CREATE TABLE alert_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_config_id UUID NOT NULL REFERENCES alert_configs(id) ON DELETE CASCADE,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    matched_insights UUID[] NOT NULL,
    notification_status JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'
);

-- Audit Logs (append-only)
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- API Keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    key_prefix VARCHAR(10) NOT NULL,
    scopes TEXT[] NOT NULL,
    rate_limit_per_hour INT NOT NULL DEFAULT 1000,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sync Jobs (for tracking ingestion)
CREATE TABLE sync_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    data_source_id UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    documents_processed INT DEFAULT 0,
    documents_created INT DEFAULT 0,
    documents_updated INT DEFAULT 0,
    documents_skipped INT DEFAULT 0,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- All indexes (in a separate section for clarity)
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant_role ON users(tenant_id, role);

CREATE INDEX idx_data_sources_tenant ON data_sources(tenant_id);
CREATE INDEX idx_data_sources_tenant_type ON data_sources(tenant_id, source_type);
CREATE INDEX idx_data_sources_status ON data_sources(status) WHERE status = 'active';

CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_source ON documents(data_source_id);
CREATE INDEX idx_documents_status ON documents(processed_status);
CREATE INDEX idx_documents_tenant_hash ON documents(tenant_id, content_hash);
CREATE INDEX idx_documents_tenant_created ON documents(tenant_id, created_at DESC);
CREATE INDEX idx_documents_content_fts ON documents USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')));

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_vector ON document_chunks(vector_id) WHERE vector_id IS NOT NULL;

CREATE INDEX idx_insights_tenant ON insights(tenant_id);
CREATE INDEX idx_insights_tenant_type ON insights(tenant_id, insight_type);
CREATE INDEX idx_insights_tenant_created ON insights(tenant_id, created_at DESC);
CREATE INDEX idx_insights_status ON insights(status) WHERE status = 'active';
CREATE INDEX idx_insights_content_fts ON insights USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));

CREATE INDEX idx_relationships_source ON entity_relationships(source_insight_id);
CREATE INDEX idx_relationships_target ON entity_relationships(target_insight_id);

CREATE INDEX idx_alerts_tenant ON alert_configs(tenant_id);
CREATE INDEX idx_alerts_status ON alert_configs(status) WHERE status = 'active';

CREATE INDEX idx_alert_history_config ON alert_history(alert_config_id);
CREATE INDEX idx_alert_history_time ON alert_history(triggered_at DESC);

CREATE INDEX idx_audit_tenant_time ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id) WHERE user_id IS NOT NULL;

CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);

CREATE INDEX idx_sync_jobs_source ON sync_jobs(data_source_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_data_sources_updated_at BEFORE UPDATE ON data_sources FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_insights_updated_at BEFORE UPDATE ON insights FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_alert_configs_updated_at BEFORE UPDATE ON alert_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

2. /migrations/postgresql/V002__seed_dev_data.sql:
- Insert demo tenant (id: fixed UUID for dev, name: "Demo Company", slug: "demo")
- Insert demo admin user
- Insert demo data source (Gmail mock)
- Add comments explaining this is dev-only

3. /scripts/db-migrate.sh:
#!/bin/bash
# Usage: ./db-migrate.sh [migrate|rollback|info] [env]
# Runs Flyway migrations against target environment

4. /docker/postgres/init.sql:
CREATE USER aswa WITH PASSWORD 'aswa_dev_password';
CREATE DATABASE aswa OWNER aswa;
GRANT ALL PRIVILEGES ON DATABASE aswa TO aswa;

5. Update /docker-compose.yml to add:
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: aswa
      POSTGRES_PASSWORD: aswa_dev_password
      POSTGRES_DB: aswa
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aswa"]
      interval: 5s
      timeout: 5s
      retries: 5

All SQL must have comments for complex logic.
Use appropriate CHECK constraints.
Ensure all foreign keys have ON DELETE behavior specified.
```

---

### Subtask 1.2.2: Python SQLAlchemy Models and Repositories

**Claude Code Prompt:**
```
Create Python SQLAlchemy 2.0 async models and repositories at /libs/common-python/src/aswa_common/db/.

1. /libs/common-python/pyproject.toml - add dependencies:
- sqlalchemy[asyncio]>=2.0.25
- asyncpg>=0.29
- greenlet>=3.0

2. /libs/common-python/src/aswa_common/db/__init__.py:
- Export: AsyncSessionFactory, get_db, Base, and all repository classes

3. /libs/common-python/src/aswa_common/db/engine.py:
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

def create_engine(database_url: str, pool_size: int = 5, max_overflow: int = 10, echo: bool = False) -> AsyncEngine:
    """Create async SQLAlchemy engine with connection pooling."""
    # Configure pool_pre_ping=True for connection health checks
    # Configure pool_recycle=3600 for long-running processes

4. /libs/common-python/src/aswa_common/db/session.py:
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

class AsyncSessionFactory:
    def __init__(self, engine: AsyncEngine): ...
    
    def create_session(self) -> AsyncSession: ...
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for session with automatic commit/rollback."""
        ...

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    ...

5. /libs/common-python/src/aswa_common/db/models/base.py:
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from uuid import UUID

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TenantMixin:
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

6. /libs/common-python/src/aswa_common/db/models/tenant.py:
class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="active")
    
    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    data_sources: Mapped[list["DataSource"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="member")
    status: Mapped[str] = mapped_column(String(50), default="active")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_login_at: Mapped[datetime | None]
    
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

7. /libs/common-python/src/aswa_common/db/models/document.py:
class DataSource(Base, TimestampMixin, TenantMixin):
    __tablename__ = "data_sources"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(50), default="active")
    last_sync_at: Mapped[datetime | None]
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    sync_frequency_minutes: Mapped[int] = mapped_column(default=60)
    
    tenant: Mapped["Tenant"] = relationship(back_populates="data_sources")
    documents: Mapped[list["Document"]] = relationship(back_populates="data_source", cascade="all, delete-orphan")

class Document(Base, TimestampMixin, TenantMixin):
    __tablename__ = "documents"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    data_source_id: Mapped[UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(1000))
    content: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    processed_status: Mapped[str] = mapped_column(String(50), default="pending")
    processed_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int | None]
    language: Mapped[str | None] = mapped_column(String(10))
    
    data_source: Mapped["DataSource"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (UniqueConstraint("tenant_id", "data_source_id", "external_id"),)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    vector_id: Mapped[str | None] = mapped_column(String(100))
    start_char: Mapped[int | None]
    end_char: Mapped[int | None]
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    document: Mapped["Document"] = relationship(back_populates="chunks")
    
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

8. /libs/common-python/src/aswa_common/db/models/insight.py:
class Insight(Base, TimestampMixin, TenantMixin):
    __tablename__ = "insights"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    insight_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB)
    confidence: Mapped[float]
    severity: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    source_documents: Mapped[list[UUID]] = mapped_column(ARRAY(UUID))
    evidence_snippets: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(String(50), default="active")
    user_feedback: Mapped[str | None] = mapped_column(String(50))
    feedback_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    feedback_comment: Mapped[str | None] = mapped_column(Text)
    feedback_at: Mapped[datetime | None]
    vector_id: Mapped[str | None] = mapped_column(String(100))

class EntityRelationship(Base, TenantMixin):
    __tablename__ = "entity_relationships"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_insight_id: Mapped[UUID] = mapped_column(ForeignKey("insights.id", ondelete="CASCADE"))
    target_insight_id: Mapped[UUID] = mapped_column(ForeignKey("insights.id", ondelete="CASCADE"))
    relationship_type: Mapped[str] = mapped_column(String(100))
    direction: Mapped[str] = mapped_column(String(20), default="directed")
    confidence: Mapped[float]
    evidence: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

9. /libs/common-python/src/aswa_common/db/repositories/base.py:
from typing import TypeVar, Generic
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model
    
    async def get_by_id(self, id: UUID) -> T | None: ...
    async def get_all(self, page: PageRequest) -> PageResponse[T]: ...
    async def create(self, entity: T) -> T: ...
    async def update(self, entity: T) -> T: ...
    async def delete(self, id: UUID) -> bool: ...
    async def exists(self, id: UUID) -> bool: ...

class TenantScopedRepository(BaseRepository[T]):
    """Repository that enforces tenant isolation."""
    
    def __init__(self, session: AsyncSession, model: type[T], tenant_id: UUID):
        super().__init__(session, model)
        self.tenant_id = tenant_id
    
    async def get_by_id(self, id: UUID) -> T | None:
        # Always filter by tenant_id
        ...
    
    async def get_all(self, page: PageRequest) -> PageResponse[T]:
        # Always filter by tenant_id
        ...

10. /libs/common-python/src/aswa_common/db/repositories/document_repository.py:
class DocumentRepository(TenantScopedRepository[Document]):
    async def find_by_hash(self, content_hash: str) -> Document | None: ...
    async def find_by_external_id(self, data_source_id: UUID, external_id: str) -> Document | None: ...
    async def find_pending(self, limit: int = 100) -> list[Document]: ...
    async def update_status(self, id: UUID, status: str, error_message: str | None = None) -> None: ...
    async def search_fulltext(self, query: str, page: PageRequest) -> PageResponse[Document]: ...

11. /libs/common-python/src/aswa_common/db/repositories/insight_repository.py:
class InsightRepository(TenantScopedRepository[Insight]):
    async def find_by_type(self, insight_type: str, page: PageRequest) -> PageResponse[Insight]: ...
    async def find_by_documents(self, document_ids: list[UUID]) -> list[Insight]: ...
    async def search_fulltext(self, query: str, page: PageRequest) -> PageResponse[Insight]: ...
    async def update_feedback(self, id: UUID, feedback: str, user_id: UUID, comment: str | None) -> None: ...
    async def aggregate_by_type(self) -> dict[str, int]: ...
    async def find_recent(self, days: int = 7, limit: int = 100) -> list[Insight]: ...

12. /libs/common-python/tests/db/:
- conftest.py with Testcontainers PostgreSQL fixture
- test_models.py - test model creation, relationships
- test_base_repository.py - test CRUD operations
- test_document_repository.py - test document-specific queries
- test_insight_repository.py - test insight-specific queries
- test_tenant_isolation.py - verify tenant isolation is enforced

All tests must be async using pytest-asyncio.
All repositories must log queries at DEBUG level.
Handle IntegrityError and convert to AswaError.
```

---

## Task 1.3: API Gateway Service (Java)

### Subtask 1.3.1: Spring Boot API Gateway Setup

**Claude Code Prompt:**
```
Create the Java API Gateway service at /services/api-gateway/ using Spring Boot 3.2+.

1. /services/api-gateway/build.gradle.kts:
plugins {
    id("org.springframework.boot") version "3.2.2"
    id("io.spring.dependency-management") version "1.1.4"
}

dependencies {
    implementation(project(":libs:common-java"))
    
    // Spring Boot
    implementation("org.springframework.boot:spring-boot-starter-webflux")
    implementation("org.springframework.boot:spring-boot-starter-data-r2dbc")
    implementation("org.springframework.boot:spring-boot-starter-security")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    
    // Database
    implementation("org.postgresql:r2dbc-postgresql")
    implementation("io.r2dbc:r2dbc-pool")
    
    // JWT
    implementation("io.jsonwebtoken:jjwt-api:0.12.3")
    runtimeOnly("io.jsonwebtoken:jjwt-impl:0.12.3")
    runtimeOnly("io.jsonwebtoken:jjwt-jackson:0.12.3")
    
    // OpenAPI
    implementation("org.springdoc:springdoc-openapi-starter-webflux-ui:2.3.0")
    
    // Observability
    implementation("io.micrometer:micrometer-registry-prometheus")
    
    // Test
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.security:spring-security-test")
    testImplementation("io.projectreactor:reactor-test")
    testImplementation("org.testcontainers:postgresql")
    testImplementation("org.testcontainers:r2dbc")
}

2. /services/api-gateway/src/main/java/com/aswa/gateway/GatewayApplication.java:
@SpringBootApplication
@EnableR2dbcRepositories
public class GatewayApplication { ... }

3. /services/api-gateway/src/main/java/com/aswa/gateway/config/:

SecurityConfig.java:
@Configuration
@EnableWebFluxSecurity
public class SecurityConfig {
    @Bean
    public SecurityWebFilterChain securityFilterChain(ServerHttpSecurity http) {
        // Configure JWT authentication
        // Whitelist: /actuator/health, /actuator/prometheus, /v3/api-docs/**, /swagger-ui/**
        // All other endpoints require authentication
        // CORS configuration
        // CSRF disabled for API
    }
    
    @Bean
    public JwtAuthenticationConverter jwtAuthConverter() { ... }
}

WebConfig.java:
@Configuration
public class WebConfig {
    @Bean
    public WebFilter requestLoggingFilter() {
        // Log request method, path, duration
        // Add request ID to MDC
    }
    
    @Bean
    public WebFilter tenantContextFilter() {
        // Extract tenant_id from JWT claims
        // Set TenantContext for request scope
    }
}

R2dbcConfig.java:
@Configuration
public class R2dbcConfig {
    @Bean
    public ConnectionFactory connectionFactory() {
        // Configure R2DBC connection pool
        // Pool size, validation query, timeouts
    }
}

4. /services/api-gateway/src/main/java/com/aswa/gateway/security/:

JwtService.java:
@Service
public class JwtService {
    Mono<Claims> validateToken(String token);
    String generateToken(User user, Tenant tenant);
    String generateRefreshToken(User user);
}

TenantContext.java:
public record TenantContext(UUID tenantId, UUID userId, Set<String> roles) {
    private static final ThreadLocal<TenantContext> CONTEXT = new ThreadLocal<>();
    
    public static void set(TenantContext ctx) { ... }
    public static TenantContext get() { ... }
    public static void clear() { ... }
    public boolean hasRole(String role) { ... }
}

5. /services/api-gateway/src/main/java/com/aswa/gateway/dto/:

Create request/response DTOs:
- TenantDto, CreateTenantRequest, UpdateTenantRequest
- UserDto, CreateUserRequest, UpdateUserRequest
- DataSourceDto, CreateDataSourceRequest
- DocumentDto, DocumentFilterRequest
- InsightDto, InsightFilterRequest
- AlertConfigDto, CreateAlertRequest
- ApiKeyDto, CreateApiKeyRequest
- AuthRequest, AuthResponse, RefreshTokenRequest

All DTOs must:
- Use Java records
- Have Jakarta validation annotations (@NotBlank, @Email, @Size, etc.)
- Have Jackson annotations for JSON handling
- Include OpenAPI @Schema annotations

6. /services/api-gateway/src/main/java/com/aswa/gateway/controller/:

HealthController.java:
@RestController
public class HealthController {
    @GetMapping("/health")
    public Mono<Map<String, String>> health() { ... }
    
    @GetMapping("/ready")
    public Mono<Map<String, Object>> ready() {
        // Check database connectivity
        // Check Redis connectivity
        // Check downstream services
    }
}

AuthController.java:
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {
    @PostMapping("/login")
    public Mono<AuthResponse> login(@Valid @RequestBody AuthRequest request) { ... }
    
    @PostMapping("/refresh")
    public Mono<AuthResponse> refresh(@Valid @RequestBody RefreshTokenRequest request) { ... }
    
    @PostMapping("/logout")
    public Mono<Void> logout() { ... }
}

TenantController.java:
@RestController
@RequestMapping("/api/v1/tenants")
@PreAuthorize("hasRole('SUPER_ADMIN')")
public class TenantController {
    // CRUD for tenants (super admin only)
}

UserController.java:
@RestController
@RequestMapping("/api/v1/users")
public class UserController {
    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public Mono<PageResponse<UserDto>> listUsers(PageRequest pageRequest) { ... }
    
    @GetMapping("/{id}")
    public Mono<UserDto> getUser(@PathVariable UUID id) { ... }
    
    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public Mono<UserDto> createUser(@Valid @RequestBody CreateUserRequest request) { ... }
    
    @PutMapping("/{id}")
    public Mono<UserDto> updateUser(@PathVariable UUID id, @Valid @RequestBody UpdateUserRequest request) { ... }
    
    @GetMapping("/me")
    public Mono<UserDto> getCurrentUser() { ... }
}

DataSourceController.java:
@RestController
@RequestMapping("/api/v1/data-sources")
public class DataSourceController {
    // CRUD for data sources
    // POST /{id}/sync - trigger manual sync
    // GET /{id}/status - get sync status
}

DocumentController.java:
@RestController
@RequestMapping("/api/v1/documents")
public class DocumentController {
    @GetMapping
    public Mono<PageResponse<DocumentDto>> listDocuments(DocumentFilterRequest filter, PageRequest page) { ... }
    
    @GetMapping("/{id}")
    public Mono<DocumentDto> getDocument(@PathVariable UUID id) { ... }
    
    @GetMapping("/{id}/chunks")
    public Flux<DocumentChunkDto> getChunks(@PathVariable UUID id) { ... }
    
    @GetMapping("/search")
    public Mono<PageResponse<DocumentDto>> searchDocuments(@RequestParam String query, PageRequest page) { ... }
}

InsightController.java:
@RestController
@RequestMapping("/api/v1/insights")
public class InsightController {
    @GetMapping
    public Mono<PageResponse<InsightDto>> listInsights(InsightFilterRequest filter, PageRequest page) { ... }
    
    @GetMapping("/{id}")
    public Mono<InsightDto> getInsight(@PathVariable UUID id) { ... }
    
    @PostMapping("/{id}/feedback")
    public Mono<InsightDto> submitFeedback(@PathVariable UUID id, @Valid @RequestBody FeedbackRequest request) { ... }
    
    @GetMapping("/summary")
    public Mono<InsightSummaryDto> getSummary() { ... }
}

AlertController.java:
@RestController
@RequestMapping("/api/v1/alerts")
public class AlertController {
    // CRUD for alert configurations
    // GET /{id}/history - get alert trigger history
}

ApiKeyController.java:
@RestController
@RequestMapping("/api/v1/api-keys")
public class ApiKeyController {
    // CRUD for API keys
    // POST - returns the raw key only once
    // DELETE /{id}/revoke - revoke key
}

7. /services/api-gateway/src/main/java/com/aswa/gateway/exception/:

GlobalExceptionHandler.java:
@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(AswaException.class)
    public Mono<ResponseEntity<ApiResponse<Void>>> handleAswaException(AswaException ex) { ... }
    
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Mono<ResponseEntity<ApiResponse<Void>>> handleValidationException(...) { ... }
    
    @ExceptionHandler(AccessDeniedException.class)
    public Mono<ResponseEntity<ApiResponse<Void>>> handleAccessDenied(...) { ... }
    
    // Handle all other exceptions with INTERNAL_ERROR
}

8. /services/api-gateway/src/main/resources/:

application.yml:
server:
  port: 8080
spring:
  application:
    name: aswa-gateway
  r2dbc:
    url: r2dbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:aswa}
    username: ${DB_USER:aswa}
    password: ${DB_PASSWORD:aswa_dev_password}
    pool:
      initial-size: 5
      max-size: 20
jwt:
  secret: ${JWT_SECRET:dev-secret-key-min-32-chars-long}
  expiration: 3600
  refresh-expiration: 604800
management:
  endpoints:
    web:
      exposure:
        include: health,prometheus,info
  metrics:
    tags:
      application: aswa-gateway

application-dev.yml, application-test.yml, application-prod.yml

9. /services/api-gateway/src/test/java/com/aswa/gateway/:

- AbstractIntegrationTest.java - base class with Testcontainers
- controller/AuthControllerTest.java - test auth flows
- controller/UserControllerTest.java - test CRUD with auth
- controller/DocumentControllerTest.java - test search, pagination
- controller/InsightControllerTest.java - test filtering, feedback
- security/JwtServiceTest.java - test token generation/validation
- security/TenantContextTest.java - test context propagation

Use @WebFluxTest for controller tests.
Use WebTestClient for integration tests.
Mock services using Mockito.
Test authorization with @WithMockUser.
Achieve 80%+ coverage.
```

---

## Task 1.4: Docker and Local Development Setup

### Subtask 1.4.1: Docker Configuration

**Claude Code Prompt:**
```
Create Docker configuration for local development at /infrastructure/docker/ and /docker-compose.yml.

1. /infrastructure/docker/api-gateway/Dockerfile:
# Multi-stage build for Java service
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY gradlew .
COPY gradle gradle
COPY build.gradle.kts settings.gradle.kts ./
COPY libs libs
COPY services/api-gateway services/api-gateway
RUN ./gradlew :services:api-gateway:bootJar --no-daemon

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -S aswa && adduser -S aswa -G aswa
COPY --from=builder /app/services/api-gateway/build/libs/*.jar app.jar
USER aswa
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-XX:+UseContainerSupport", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]

2. /infrastructure/docker/python-base/Dockerfile:
# Base image for Python services
FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists