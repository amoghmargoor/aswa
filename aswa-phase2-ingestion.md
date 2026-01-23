# ASWA Phase 2: Ingestion Pipeline (Weeks 3-4)

## Task 2.1: Ingestion Service Core

### Subtask 2.1.1: Create Ingestion Service Structure

**Claude Code Prompt:**
```
Create the Python ingestion service at /services/ingestion-service/.

1. /services/ingestion-service/pyproject.toml:
[tool.poetry]
name = "aswa-ingestion"
version = "0.1.0"
python = ">=3.11,<3.13"

[tool.poetry.dependencies]
python = ">=3.11,<3.13"
aswa-common = { path = "../../libs/common-python", develop = true }
fastapi = ">=0.109"
uvicorn = { extras = ["standard"], version = ">=0.27" }
aioboto3 = ">=12.0"  # For AWS Bedrock
httpx = ">=0.26"
redis = ">=5.0"
qdrant-client = ">=1.7"
unstructured = { extras = ["pdf", "docx", "md"], version = ">=0.12" }
tiktoken = ">=0.5"
python-multipart = ">=0.0.6"
aiofiles = ">=23.2"
croniter = ">=2.0"

[tool.poetry.group.dev.dependencies]
pytest = ">=8.0"
pytest-asyncio = ">=0.23"
pytest-cov = ">=4.1"
httpx = ">=0.26"
fakeredis = ">=2.21"
moto = { extras = ["s3"], version = ">=5.0" }

2. /services/ingestion-service/src/aswa_ingestion/__init__.py

3. /services/ingestion-service/src/aswa_ingestion/main.py:
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB connections, Redis, Qdrant client
    # Register background scheduler for sync jobs
    yield
    # Shutdown: Close connections gracefully

app = FastAPI(
    title="ASWA Ingestion Service",
    version="0.1.0",
    lifespan=lifespan
)

# Include routers
# Add exception handlers
# Add middleware (logging, metrics, tenant context)

4. /services/ingestion-service/src/aswa_ingestion/config.py:
from aswa_common.config import BaseSettings, DatabaseSettings, RedisSettings, LLMSettings

class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGESTION_")
    
    # Service config
    service_name: str = "aswa-ingestion"
    worker_concurrency: int = 4
    batch_size: int = 50
    
    # Chunking config
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_chunks_per_doc: int = 100
    
    # Vector DB
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "documents"
    
    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 100
    
    # Storage
    blob_storage_type: Literal["local", "s3"] = "local"
    blob_storage_path: str = "/data/blobs"
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"

class Settings:
    ingestion: IngestionSettings = IngestionSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    llm: LLMSettings = LLMSettings()

settings = Settings()

5. /services/ingestion-service/src/aswa_ingestion/api/:

__init__.py

health.py:
@router.get("/health")
async def health(): ...

@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)): ...

sync.py:
@router.post("/data-sources/{source_id}/sync")
async def trigger_sync(source_id: UUID, tenant_ctx: TenantContext = Depends(get_tenant_context)): ...

@router.get("/data-sources/{source_id}/sync/status")
async def get_sync_status(source_id: UUID): ...

@router.get("/sync-jobs")
async def list_sync_jobs(page: PageRequest = Depends()): ...

@router.get("/sync-jobs/{job_id}")
async def get_sync_job(job_id: UUID): ...

documents.py:
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    data_source_id: UUID,
    tenant_ctx: TenantContext = Depends(get_tenant_context)
): ...

@router.post("/documents/{doc_id}/reprocess")
async def reprocess_document(doc_id: UUID): ...

6. /services/ingestion-service/src/aswa_ingestion/services/:

__init__.py

sync_service.py:
class SyncService:
    """Orchestrates data source synchronization."""
    
    def __init__(self, db: AsyncSession, redis: Redis, connector_factory: ConnectorFactory): ...
    
    async def start_sync(self, data_source_id: UUID, tenant_id: UUID, full_sync: bool = False) -> SyncJob: ...
    async def get_sync_status(self, job_id: UUID) -> SyncJobStatus: ...
    async def cancel_sync(self, job_id: UUID) -> None: ...
    
    async def _run_sync(self, job: SyncJob, data_source: DataSource) -> None:
        # Get connector for source type
        # Iterate through documents with cursor
        # Deduplicate by content hash
        # Queue documents for processing
        # Update cursor and job status

document_service.py:
class DocumentService:
    """Handles document storage and retrieval."""
    
    def __init__(self, db: AsyncSession, blob_storage: BlobStorage): ...
    
    async def store_document(self, doc: NormalizedDocument, tenant_id: UUID, data_source_id: UUID) -> Document: ...
    async def get_document(self, doc_id: UUID, tenant_id: UUID) -> Document | None: ...
    async def check_duplicate(self, content_hash: str, tenant_id: UUID) -> Document | None: ...
    async def update_status(self, doc_id: UUID, status: str, error: str | None = None) -> None: ...

7. Create comprehensive tests in /services/ingestion-service/tests/:
- conftest.py with fixtures (mock DB, Redis, services)
- test_main.py - app startup/shutdown
- test_api_health.py - health endpoints
- test_api_sync.py - sync trigger and status
- test_sync_service.py - sync orchestration logic
- test_document_service.py - document CRUD and dedup

All code must have:
- Type hints
- Docstrings
- Structured logging
- Prometheus metrics
- Error handling with AswaError
```

---

### Subtask 2.1.2: Document Processing Pipeline

**Claude Code Prompt:**
```
Create the document processing pipeline at /services/ingestion-service/src/aswa_ingestion/processing/.

1. /services/ingestion-service/src/aswa_ingestion/processing/__init__.py

2. /services/ingestion-service/src/aswa_ingestion/processing/parser.py:
from unstructured.partition.auto import partition
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.html import partition_html
from unstructured.partition.text import partition_text
from unstructured.partition.email import partition_email

class DocumentParser:
    """Parse various document formats into structured text."""
    
    SUPPORTED_TYPES = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/html": "html",
        "text/plain": "text",
        "message/rfc822": "email",
        "text/markdown": "markdown"
    }
    
    def __init__(self, ocr_enabled: bool = True, ocr_languages: list[str] = ["eng"]): ...
    
    async def parse(self, content: bytes, content_type: str, filename: str | None = None) -> ParsedDocument:
        """
        Parse document content into structured elements.
        
        Returns:
            ParsedDocument with:
            - text: Full extracted text
            - elements: List of document elements (titles, paragraphs, tables, etc.)
            - metadata: Extracted metadata (author, date, etc.)
            - language: Detected language
            - word_count: Total word count
        """
        ...
    
    async def parse_file(self, file_path: Path) -> ParsedDocument: ...
    
    def _detect_content_type(self, content: bytes, filename: str | None) -> str: ...

class ParsedDocument(BaseModel):
    text: str
    elements: list[DocumentElement]
    metadata: dict[str, Any]
    language: str | None
    word_count: int
    
class DocumentElement(BaseModel):
    type: Literal["title", "narrative_text", "list_item", "table", "image", "header", "footer"]
    text: str
    metadata: dict[str, Any] = {}
    page_number: int | None = None

3. /services/ingestion-service/src/aswa_ingestion/processing/chunker.py:
import tiktoken

class TextChunker:
    """Split text into chunks suitable for embedding."""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        tokenizer: str = "cl100k_base"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(tokenizer)
    
    def chunk(self, text: str, preserve_sentences: bool = True) -> list[TextChunk]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Input text to chunk
            preserve_sentences: Try to break at sentence boundaries
            
        Returns:
            List of TextChunk with content, token_count, start_char, end_char
        """
        ...
    
    def chunk_with_metadata(self, parsed_doc: ParsedDocument) -> list[TextChunk]:
        """
        Chunk document preserving element boundaries where possible.
        Include element type in chunk metadata.
        """
        ...
    
    def count_tokens(self, text: str) -> int: ...

class TextChunk(BaseModel):
    content: str
    token_count: int
    start_char: int
    end_char: int
    metadata: dict[str, Any] = {}

class SemanticChunker(TextChunker):
    """Advanced chunker that uses semantic similarity to find chunk boundaries."""
    
    def __init__(self, embedding_client: EmbeddingClient, similarity_threshold: float = 0.5, **kwargs): ...
    
    async def chunk_semantic(self, text: str) -> list[TextChunk]:
        """Split at points where semantic similarity drops below threshold."""
        ...

4. /services/ingestion-service/src/aswa_ingestion/processing/embedder.py:
import aioboto3
from openai import AsyncAzureOpenAI

class EmbeddingClient:
    """Generate embeddings using AWS Bedrock or Azure OpenAI."""
    
    def __init__(self, settings: LLMSettings): ...
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for single text."""
        ...
    
    async def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """Generate embeddings for multiple texts with batching."""
        # Handle rate limiting with exponential backoff
        # Log metrics for latency and token usage
        ...
    
    async def _embed_bedrock(self, texts: list[str]) -> list[list[float]]: ...
    async def _embed_azure(self, texts: list[str]) -> list[list[float]]: ...

5. /services/ingestion-service/src/aswa_ingestion/processing/deduplicator.py:
from datasketch import MinHash, MinHashLSH

class DocumentDeduplicator:
    """Detect duplicate and near-duplicate documents."""
    
    def __init__(self, similarity_threshold: float = 0.8, num_perm: int = 128): ...
    
    def compute_hash(self, content: str) -> str:
        """Compute MD5 hash for exact duplicate detection."""
        ...
    
    def compute_minhash(self, content: str) -> MinHash:
        """Compute MinHash signature for near-duplicate detection."""
        ...
    
    def is_near_duplicate(self, minhash: MinHash, existing_hashes: list[MinHash]) -> bool:
        """Check if document is near-duplicate of any existing document."""
        ...
    
    async def check_duplicate(
        self, 
        content: str, 
        tenant_id: UUID,
        db: AsyncSession
    ) -> DuplicateCheckResult:
        """
        Check for exact and near duplicates in database.
        
        Returns:
            DuplicateCheckResult with is_duplicate, duplicate_type, duplicate_id
        """
        ...

class DuplicateCheckResult(BaseModel):
    is_duplicate: bool
    duplicate_type: Literal["exact", "near", "none"]
    duplicate_id: UUID | None = None
    similarity_score: float | None = None

6. /services/ingestion-service/src/aswa_ingestion/processing/pipeline.py:
class DocumentProcessingPipeline:
    """End-to-end document processing pipeline."""
    
    def __init__(
        self,
        parser: DocumentParser,
        chunker: TextChunker,
        embedder: EmbeddingClient,
        deduplicator: DocumentDeduplicator,
        vector_store: VectorStore,
        db: AsyncSession
    ): ...
    
    async def process(self, document: Document) -> ProcessingResult:
        """
        Process a single document through the full pipeline:
        1. Parse document content
        2. Check for duplicates
        3. Chunk text
        4. Generate embeddings
        5. Store vectors in Qdrant
        6. Update document status
        
        Returns:
            ProcessingResult with chunks_created, vectors_stored, processing_time
        """
        ...
    
    async def process_batch(self, documents: list[Document]) -> list[ProcessingResult]:
        """Process multiple documents concurrently."""
        ...
    
    async def reprocess(self, document_id: UUID) -> ProcessingResult:
        """Delete existing chunks/vectors and reprocess document."""
        ...

class ProcessingResult(BaseModel):
    document_id: UUID
    success: bool
    chunks_created: int
    vectors_stored: int
    processing_time_ms: int
    error: str | None = None

7. /services/ingestion-service/tests/processing/:
- test_parser.py - test parsing various formats, OCR, error handling
- test_chunker.py - test chunking logic, overlap, token counting
- test_embedder.py - test embedding with mocked API responses
- test_deduplicator.py - test exact and near-duplicate detection
- test_pipeline.py - test full pipeline integration

Include test fixtures for sample documents (PDF, DOCX, HTML, email).
Test error scenarios (corrupt files, unsupported formats).
Mock external services (Bedrock/Azure, Qdrant).
```

---

## Task 2.2: Data Source Connectors

### Subtask 2.2.1: Connector Framework

**Claude Code Prompt:**
```
Create the connector framework at /services/ingestion-service/src/aswa_ingestion/connectors/.

1. /services/ingestion-service/src/aswa_ingestion/connectors/__init__.py:
from .base import BaseConnector, ConnectorFactory
from .gmail import GmailConnector
from .slack import SlackConnector
from .gdrive import GoogleDriveConnector
# Export all connectors

2. /services/ingestion-service/src/aswa_ingestion/connectors/base.py:
from abc import ABC, abstractmethod
from typing import AsyncIterator

class ConnectorConfig(BaseModel):
    """Base configuration for all connectors."""
    credentials: dict[str, Any]
    settings: dict[str, Any] = {}

class SyncCursor(BaseModel):
    """Cursor for incremental synchronization."""
    cursor_type: str
    value: str
    timestamp: datetime

class BaseConnector(ABC):
    """Abstract base class for all data source connectors."""
    
    SOURCE_TYPE: str  # Override in subclass
    
    def __init__(self, config: ConnectorConfig, tenant_id: UUID): ...
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Validate credentials and establish connection."""
        ...
    
    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Test connection and return diagnostic information."""
        ...
    
    @abstractmethod
    async def fetch_documents(
        self, 
        cursor: SyncCursor | None = None,
        batch_size: int = 100
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """
        Fetch documents incrementally.
        
        Yields batches of documents with updated cursor.
        """
        ...
    
    @abstractmethod
    async def fetch_document_content(self, external_id: str) -> bytes:
        """Fetch raw content for a specific document."""
        ...
    
    async def handle_webhook(self, payload: dict) -> list[NormalizedDocument]:
        """Handle webhook notifications (optional, not all connectors support)."""
        raise NotImplementedError("Webhook not supported for this connector")
    
    async def close(self) -> None:
        """Clean up resources."""
        pass

class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    details: dict[str, Any] = {}
    latency_ms: int

class ConnectorFactory:
    """Factory for creating connector instances."""
    
    _connectors: dict[str, type[BaseConnector]] = {}
    
    @classmethod
    def register(cls, connector_class: type[BaseConnector]) -> None: ...
    
    @classmethod
    def create(cls, source_type: str, config: ConnectorConfig, tenant_id: UUID) -> BaseConnector: ...
    
    @classmethod
    def get_supported_types(cls) -> list[str]: ...

# Register connectors
ConnectorFactory.register(GmailConnector)
ConnectorFactory.register(SlackConnector)
ConnectorFactory.register(GoogleDriveConnector)

3. /services/ingestion-service/src/aswa_ingestion/connectors/oauth.py:
class OAuthManager:
    """Manage OAuth token lifecycle."""
    
    def __init__(self, redis: Redis, encryption_key: bytes): ...
    
    async def store_tokens(
        self, 
        tenant_id: UUID, 
        source_type: str, 
        tokens: OAuthTokens
    ) -> None:
        """Store encrypted tokens in Redis."""
        ...
    
    async def get_tokens(self, tenant_id: UUID, source_type: str) -> OAuthTokens | None: ...
    
    async def refresh_if_needed(
        self, 
        tenant_id: UUID, 
        source_type: str,
        refresh_callback: Callable
    ) -> OAuthTokens:
        """Refresh tokens if expired."""
        ...
    
    async def revoke_tokens(self, tenant_id: UUID, source_type: str) -> None: ...

class OAuthTokens(BaseModel):
    access_token: SecretStr
    refresh_token: SecretStr | None
    expires_at: datetime
    token_type: str = "Bearer"
    scope: str | None = None

4. /services/ingestion-service/tests/connectors/:
- test_base.py - test ConnectorFactory, base class contracts
- test_oauth.py - test token storage, encryption, refresh
- conftest.py - fixtures for mock connectors

All connectors must:
- Handle rate limiting with exponential backoff
- Log all API calls with latency metrics
- Support incremental sync via cursors
- Encrypt credentials at rest
- Validate configurations on init
```

---

### Subtask 2.2.2: Gmail Connector

**Claude Code Prompt:**
```
Create the Gmail connector at /services/ingestion-service/src/aswa_ingestion/connectors/gmail.py.

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.utils import parsedate_to_datetime

class GmailConnector(BaseConnector):
    """Connector for Gmail API."""
    
    SOURCE_TYPE = "gmail"
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    
    def __init__(self, config: ConnectorConfig, tenant_id: UUID):
        super().__init__(config, tenant_id)
        self.credentials: Credentials | None = None
        self.service = None
        self.user_email: str | None = None
    
    async def authenticate(self) -> bool:
        """
        Authenticate using OAuth credentials from config.
        Config should contain:
        - credentials.access_token
        - credentials.refresh_token
        - credentials.client_id
        - credentials.client_secret
        """
        try:
            self.credentials = Credentials(
                token=self.config.credentials["access_token"],
                refresh_token=self.config.credentials.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.config.credentials["client_id"],
                client_secret=self.config.credentials["client_secret"],
                scopes=self.SCOPES
            )
            
            # Refresh if expired
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            
            # Build service
            self.service = build("gmail", "v1", credentials=self.credentials)
            
            # Get user email
            profile = self.service.users().getProfile(userId="me").execute()
            self.user_email = profile["emailAddress"]
            
            return True
        except Exception as e:
            logger.error("Gmail authentication failed", error=str(e))
            return False
    
    async def test_connection(self) -> ConnectionTestResult:
        """Test Gmail API connection."""
        start = time.monotonic()
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            return ConnectionTestResult(
                success=True,
                message=f"Connected as {profile['emailAddress']}",
                details={"email": profile["emailAddress"], "messages_total": profile.get("messagesTotal")},
                latency_ms=int((time.monotonic() - start) * 1000)
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=str(e),
                latency_ms=int((time.monotonic() - start) * 1000)
            )
    
    async def fetch_documents(
        self,
        cursor: SyncCursor | None = None,
        batch_size: int = 100
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """
        Fetch emails incrementally.
        
        Cursor format: {"history_id": "12345"} or {"page_token": "..."}
        """
        # Use history API for incremental sync if cursor has history_id
        if cursor and cursor.cursor_type == "history_id":
            async for batch, new_cursor in self._fetch_history(cursor, batch_size):
                yield batch, new_cursor
        else:
            # Full sync using messages.list
            async for batch, new_cursor in self._fetch_all(cursor, batch_size):
                yield batch, new_cursor
    
    async def _fetch_all(
        self,
        cursor: SyncCursor | None,
        batch_size: int
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """Fetch all messages using pagination."""
        page_token = cursor.value if cursor and cursor.cursor_type == "page_token" else None
        
        while True:
            # List messages
            response = self.service.users().messages().list(
                userId="me",
                maxResults=batch_size,
                pageToken=page_token,
                q=self.config.settings.get("query", "")  # Optional filter query
            ).execute()
            
            messages = response.get("messages", [])
            if not messages:
                break
            
            # Fetch full message content
            docs = []
            for msg_meta in messages:
                doc = await self._fetch_message(msg_meta["id"])
                if doc:
                    docs.append(doc)
            
            # Create cursor
            page_token = response.get("nextPageToken")
            new_cursor = SyncCursor(
                cursor_type="page_token" if page_token else "history_id",
                value=page_token or str(response.get("historyId", "")),
                timestamp=datetime.utcnow()
            )
            
            yield docs, new_cursor
            
            if not page_token:
                break
    
    async def _fetch_history(
        self,
        cursor: SyncCursor,
        batch_size: int
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """Fetch changed messages since history_id."""
        try:
            response = self.service.users().history().list(
                userId="me",
                startHistoryId=cursor.value,
                historyTypes=["messageAdded"]
            ).execute()
            
            history = response.get("history", [])
            message_ids = set()
            for item in history:
                for msg in item.get("messagesAdded", []):
                    message_ids.add(msg["message"]["id"])
            
            # Fetch messages in batches
            docs = []
            for msg_id in message_ids:
                doc = await self._fetch_message(msg_id)
                if doc:
                    docs.append(doc)
                
                if len(docs) >= batch_size:
                    yield docs, SyncCursor(
                        cursor_type="history_id",
                        value=str(response.get("historyId", cursor.value)),
                        timestamp=datetime.utcnow()
                    )
                    docs = []
            
            if docs:
                yield docs, SyncCursor(
                    cursor_type="history_id",
                    value=str(response.get("historyId", cursor.value)),
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            if "historyId" in str(e).lower():
                # History ID expired, need full resync
                logger.warning("History ID expired, falling back to full sync")
                async for batch, new_cursor in self._fetch_all(None, batch_size):
                    yield batch, new_cursor
            else:
                raise
    
    async def _fetch_message(self, message_id: str) -> NormalizedDocument | None:
        """Fetch and parse a single email message."""
        try:
            msg = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()
            
            # Extract headers
            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            
            # Extract body
            body = self._extract_body(msg["payload"])
            
            # Parse timestamp
            timestamp = datetime.utcnow()
            if "date" in headers:
                try:
                    timestamp = parsedate_to_datetime(headers["date"])
                except:
                    pass
            
            return NormalizedDocument(
                source_id=self.SOURCE_TYPE,
                document_id=message_id,
                content=body,
                content_type="email",
                title=headers.get("subject", "(No Subject)"),
                metadata={
                    "from": headers.get("from"),
                    "to": headers.get("to"),
                    "cc": headers.get("cc"),
                    "date": headers.get("date"),
                    "labels": msg.get("labelIds", []),
                    "thread_id": msg.get("threadId"),
                    "snippet": msg.get("snippet")
                },
                timestamp=timestamp,
                version_hash=hashlib.md5(body.encode()).hexdigest()
            )
        except Exception as e:
            logger.error("Failed to fetch message", message_id=message_id, error=str(e))
            return None
    
    def _extract_body(self, payload: dict) -> str:
        """Extract text body from email payload."""
        body_text = ""
        
        if "body" in payload and payload["body"].get("data"):
            body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        
        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain" and part.get("body", {}).get("data"):
                    body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    break
                elif mime_type == "text/html" and not body_text:
                    html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    # Simple HTML to text conversion
                    body_text = self._html_to_text(html)
                elif mime_type.startswith("multipart/"):
                    body_text = self._extract_body(part)
        
        return body_text
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        from html.parser import HTMLParser
        # Simple implementation - strip tags
        ...
    
    async def fetch_document_content(self, external_id: str) -> bytes:
        """Fetch raw email content."""
        msg = self.service.users().messages().get(
            userId="me",
            id=external_id,
            format="raw"
        ).execute()
        return base64.urlsafe_b64decode(msg["raw"])

Create /services/ingestion-service/tests/connectors/test_gmail.py:
- Test authentication flow
- Test fetch_documents with mocked API responses
- Test incremental sync with history API
- Test cursor handling
- Test error recovery (expired history ID)
- Test rate limiting behavior

Use unittest.mock to mock Google API client.
```

---

### Subtask 2.2.3: Slack Connector

**Claude Code Prompt:**
```
Create the Slack connector at /services/ingestion-service/src/aswa_ingestion/connectors/slack.py.

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

class SlackConnector