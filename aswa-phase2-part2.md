# ASWA Phase 2 Part 2: Connectors & Vector Store

## Task 2.2: Data Source Connectors (continued)

### Subtask 2.2.3: Slack Connector

**Claude Code Prompt:**
```
Create the Slack connector at /services/ingestion-service/src/aswa_ingestion/connectors/slack.py.

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

class SlackConnector(BaseConnector):
    """Connector for Slack API."""
    
    SOURCE_TYPE = "slack"
    SCOPES = [
        "channels:history", "channels:read",
        "groups:history", "groups:read", 
        "im:history", "im:read",
        "mpim:history", "mpim:read",
        "users:read"
    ]
    
    def __init__(self, config: ConnectorConfig, tenant_id: UUID):
        super().__init__(config, tenant_id)
        self.client: AsyncWebClient | None = None
        self.users_cache: dict[str, dict] = {}
    
    async def authenticate(self) -> bool:
        """
        Authenticate using Bot token from config.
        Config should contain:
        - credentials.bot_token
        """
        try:
            self.client = AsyncWebClient(token=self.config.credentials["bot_token"])
            # Test authentication
            response = await self.client.auth_test()
            self.team_id = response["team_id"]
            self.team_name = response["team"]
            return True
        except SlackApiError as e:
            logger.error("Slack authentication failed", error=str(e))
            return False
    
    async def test_connection(self) -> ConnectionTestResult:
        start = time.monotonic()
        try:
            response = await self.client.auth_test()
            return ConnectionTestResult(
                success=True,
                message=f"Connected to {response['team']}",
                details={"team": response["team"], "user": response["user"]},
                latency_ms=int((time.monotonic() - start) * 1000)
            )
        except SlackApiError as e:
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
        Fetch messages from all accessible channels.
        
        Cursor format: {"channels": {"C123": "ts123", ...}, "channel_list_cursor": "..."}
        """
        # Get list of channels
        channels = await self._get_channels()
        
        # Parse cursor
        channel_cursors = {}
        if cursor and cursor.cursor_type == "channel_cursors":
            channel_cursors = json.loads(cursor.value)
        
        for channel in channels:
            channel_id = channel["id"]
            oldest_ts = channel_cursors.get(channel_id, "0")
            
            async for batch, latest_ts in self._fetch_channel_messages(channel, oldest_ts, batch_size):
                channel_cursors[channel_id] = latest_ts
                new_cursor = SyncCursor(
                    cursor_type="channel_cursors",
                    value=json.dumps(channel_cursors),
                    timestamp=datetime.utcnow()
                )
                yield batch, new_cursor
    
    async def _get_channels(self) -> list[dict]:
        """Get all accessible channels."""
        channels = []
        cursor = None
        
        while True:
            response = await self.client.conversations_list(
                types="public_channel,private_channel",
                limit=200,
                cursor=cursor
            )
            channels.extend(response["channels"])
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        
        # Filter by config settings if specified
        include_patterns = self.config.settings.get("include_channels", [])
        exclude_patterns = self.config.settings.get("exclude_channels", [])
        
        if include_patterns:
            channels = [c for c in channels if any(fnmatch(c["name"], p) for p in include_patterns)]
        if exclude_patterns:
            channels = [c for c in channels if not any(fnmatch(c["name"], p) for p in exclude_patterns)]
        
        return channels
    
    async def _fetch_channel_messages(
        self,
        channel: dict,
        oldest_ts: str,
        batch_size: int
    ) -> AsyncIterator[tuple[list[NormalizedDocument], str]]:
        """Fetch messages from a single channel."""
        cursor = None
        latest_ts = oldest_ts
        
        while True:
            try:
                response = await self.client.conversations_history(
                    channel=channel["id"],
                    oldest=oldest_ts,
                    limit=batch_size,
                    cursor=cursor
                )
            except SlackApiError as e:
                if e.response["error"] == "not_in_channel":
                    # Try to join channel
                    await self.client.conversations_join(channel=channel["id"])
                    continue
                elif e.response["error"] == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)
                    continue
                else:
                    logger.error("Failed to fetch channel", channel=channel["name"], error=str(e))
                    break
            
            messages = response.get("messages", [])
            if not messages:
                break
            
            docs = []
            for msg in messages:
                if msg.get("subtype") in ["channel_join", "channel_leave", "bot_message"]:
                    continue
                
                doc = await self._message_to_document(msg, channel)
                if doc:
                    docs.append(doc)
                    if float(msg["ts"]) > float(latest_ts):
                        latest_ts = msg["ts"]
            
            if docs:
                yield docs, latest_ts
            
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor or not response.get("has_more"):
                break
    
    async def _message_to_document(self, msg: dict, channel: dict) -> NormalizedDocument | None:
        """Convert Slack message to NormalizedDocument."""
        try:
            user = await self._get_user(msg.get("user", "unknown"))
            
            # Handle thread replies
            thread_ts = msg.get("thread_ts")
            reply_count = msg.get("reply_count", 0)
            
            # Build content with thread context
            content = msg.get("text", "")
            if thread_ts and thread_ts != msg["ts"]:
                content = f"[Reply in thread] {content}"
            
            # Resolve user mentions
            content = await self._resolve_mentions(content)
            
            timestamp = datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc)
            
            return NormalizedDocument(
                source_id=self.SOURCE_TYPE,
                document_id=f"{channel['id']}:{msg['ts']}",
                content=content,
                content_type="message",
                title=f"#{channel['name']} - {user.get('real_name', 'Unknown')}",
                metadata={
                    "channel_id": channel["id"],
                    "channel_name": channel["name"],
                    "user_id": msg.get("user"),
                    "user_name": user.get("real_name"),
                    "thread_ts": thread_ts,
                    "reply_count": reply_count,
                    "reactions": msg.get("reactions", []),
                    "attachments": len(msg.get("attachments", [])),
                    "files": len(msg.get("files", []))
                },
                timestamp=timestamp,
                version_hash=hashlib.md5(content.encode()).hexdigest()
            )
        except Exception as e:
            logger.error("Failed to convert message", error=str(e))
            return None
    
    async def _get_user(self, user_id: str) -> dict:
        """Get user info with caching."""
        if user_id not in self.users_cache:
            try:
                response = await self.client.users_info(user=user_id)
                self.users_cache[user_id] = response["user"]
            except:
                self.users_cache[user_id] = {"real_name": "Unknown"}
        return self.users_cache[user_id]
    
    async def _resolve_mentions(self, text: str) -> str:
        """Replace <@U123> mentions with user names."""
        import re
        pattern = r'<@(U[A-Z0-9]+)>'
        matches = re.findall(pattern, text)
        for user_id in matches:
            user = await self._get_user(user_id)
            text = text.replace(f"<@{user_id}>", f"@{user.get('real_name', user_id)}")
        return text
    
    async def handle_webhook(self, payload: dict) -> list[NormalizedDocument]:
        """Handle Slack Events API webhook."""
        event = payload.get("event", {})
        event_type = event.get("type")
        
        if event_type == "message" and not event.get("subtype"):
            channel_info = await self.client.conversations_info(channel=event["channel"])
            doc = await self._message_to_document(event, channel_info["channel"])
            return [doc] if doc else []
        
        return []
    
    async def fetch_document_content(self, external_id: str) -> bytes:
        """Fetch raw message JSON."""
        channel_id, ts = external_id.split(":")
        response = await self.client.conversations_history(
            channel=channel_id,
            oldest=ts,
            latest=ts,
            inclusive=True,
            limit=1
        )
        if response["messages"]:
            return json.dumps(response["messages"][0]).encode()
        raise NotFoundError(f"Message {external_id} not found")

Create /services/ingestion-service/tests/connectors/test_slack.py:
- Test authentication
- Test channel listing with filters
- Test message fetching with pagination
- Test cursor handling
- Test webhook handling
- Test rate limit handling
- Test user mention resolution

Mock slack_sdk.web.async_client.AsyncWebClient.
```

---

### Subtask 2.2.4: Google Drive Connector

**Claude Code Prompt:**
```
Create the Google Drive connector at /services/ingestion-service/src/aswa_ingestion/connectors/gdrive.py.

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

class GoogleDriveConnector(BaseConnector):
    """Connector for Google Drive API."""
    
    SOURCE_TYPE = "gdrive"
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    
    SUPPORTED_MIME_TYPES = {
        "application/pdf": ".pdf",
        "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/html": ".html"
    }
    
    def __init__(self, config: ConnectorConfig, tenant_id: UUID):
        super().__init__(config, tenant_id)
        self.credentials: Credentials | None = None
        self.service = None
    
    async def authenticate(self) -> bool:
        try:
            self.credentials = Credentials(
                token=self.config.credentials["access_token"],
                refresh_token=self.config.credentials.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.config.credentials["client_id"],
                client_secret=self.config.credentials["client_secret"],
                scopes=self.SCOPES
            )
            self.service = build("drive", "v3", credentials=self.credentials)
            return True
        except Exception as e:
            logger.error("Google Drive authentication failed", error=str(e))
            return False
    
    async def test_connection(self) -> ConnectionTestResult:
        start = time.monotonic()
        try:
            about = self.service.about().get(fields="user").execute()
            return ConnectionTestResult(
                success=True,
                message=f"Connected as {about['user']['emailAddress']}",
                details={"email": about["user"]["emailAddress"]},
                latency_ms=int((time.monotonic() - start) * 1000)
            )
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e), latency_ms=int((time.monotonic() - start) * 1000))
    
    async def fetch_documents(
        self,
        cursor: SyncCursor | None = None,
        batch_size: int = 100
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """
        Fetch files from Google Drive.
        Uses Changes API for incremental sync.
        """
        if cursor and cursor.cursor_type == "page_token":
            async for batch, new_cursor in self._fetch_changes(cursor, batch_size):
                yield batch, new_cursor
        else:
            async for batch, new_cursor in self._fetch_all(cursor, batch_size):
                yield batch, new_cursor
    
    async def _fetch_all(
        self,
        cursor: SyncCursor | None,
        batch_size: int
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """Full sync: list all files."""
        page_token = cursor.value if cursor and cursor.cursor_type == "list_page" else None
        
        # Build query
        query_parts = ["trashed = false"]
        
        # Filter by folder if specified
        if folder_id := self.config.settings.get("folder_id"):
            query_parts.append(f"'{folder_id}' in parents")
        
        # Filter by mime types
        mime_conditions = [f"mimeType = '{mt}'" for mt in self.SUPPORTED_MIME_TYPES.keys()]
        query_parts.append(f"({' or '.join(mime_conditions)})")
        
        query = " and ".join(query_parts)
        
        while True:
            response = self.service.files().list(
                q=query,
                pageSize=batch_size,
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, owners, webViewLink)",
                orderBy="modifiedTime desc"
            ).execute()
            
            files = response.get("files", [])
            if not files:
                # Get start page token for future incremental syncs
                start_token = self.service.changes().getStartPageToken().execute()
                yield [], SyncCursor(
                    cursor_type="page_token",
                    value=start_token["startPageToken"],
                    timestamp=datetime.utcnow()
                )
                break
            
            docs = []
            for file in files:
                doc = await self._file_to_document(file)
                if doc:
                    docs.append(doc)
            
            page_token = response.get("nextPageToken")
            if page_token:
                new_cursor = SyncCursor(cursor_type="list_page", value=page_token, timestamp=datetime.utcnow())
            else:
                start_token = self.service.changes().getStartPageToken().execute()
                new_cursor = SyncCursor(cursor_type="page_token", value=start_token["startPageToken"], timestamp=datetime.utcnow())
            
            yield docs, new_cursor
            
            if not page_token:
                break
    
    async def _fetch_changes(
        self,
        cursor: SyncCursor,
        batch_size: int
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """Incremental sync using Changes API."""
        page_token = cursor.value
        
        while True:
            response = self.service.changes().list(
                pageToken=page_token,
                pageSize=batch_size,
                fields="nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, modifiedTime, size, owners, webViewLink))"
            ).execute()
            
            changes = response.get("changes", [])
            docs = []
            
            for change in changes:
                if change.get("removed"):
                    # TODO: Handle deleted files
                    continue
                
                file = change.get("file")
                if file and file.get("mimeType") in self.SUPPORTED_MIME_TYPES:
                    doc = await self._file_to_document(file)
                    if doc:
                        docs.append(doc)
            
            new_page_token = response.get("nextPageToken") or response.get("newStartPageToken")
            new_cursor = SyncCursor(cursor_type="page_token", value=new_page_token, timestamp=datetime.utcnow())
            
            yield docs, new_cursor
            
            if not response.get("nextPageToken"):
                break
            page_token = response["nextPageToken"]
    
    async def _file_to_document(self, file: dict) -> NormalizedDocument | None:
        """Convert Drive file to NormalizedDocument."""
        try:
            content = await self._download_file(file)
            if not content:
                return None
            
            # For text content, decode
            content_text = ""
            if isinstance(content, bytes):
                try:
                    content_text = content.decode("utf-8")
                except:
                    # Binary file, will be processed by parser
                    content_text = f"[Binary file: {file['name']}]"
            
            modified_time = datetime.fromisoformat(file["modifiedTime"].replace("Z", "+00:00"))
            
            return NormalizedDocument(
                source_id=self.SOURCE_TYPE,
                document_id=file["id"],
                content=content_text,
                content_type="document",
                title=file["name"],
                metadata={
                    "mime_type": file["mimeType"],
                    "size": file.get("size"),
                    "owners": [o.get("emailAddress") for o in file.get("owners", [])],
                    "web_link": file.get("webViewLink"),
                    "modified_time": file["modifiedTime"]
                },
                timestamp=modified_time,
                version_hash=hashlib.md5(content if isinstance(content, bytes) else content.encode()).hexdigest()
            )
        except Exception as e:
            logger.error("Failed to convert file", file_id=file["id"], error=str(e))
            return None
    
    async def _download_file(self, file: dict) -> bytes | None:
        """Download file content."""
        try:
            mime_type = file["mimeType"]
            
            if mime_type.startswith("application/vnd.google-apps."):
                # Export Google Docs
                export_mime = self.SUPPORTED_MIME_TYPES.get(mime_type)
                if not export_mime:
                    return None
                request = self.service.files().export_media(fileId=file["id"], mimeType=export_mime)
            else:
                request = self.service.files().get_media(fileId=file["id"])
            
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            return buffer.getvalue()
        except Exception as e:
            logger.error("Failed to download file", file_id=file["id"], error=str(e))
            return None
    
    async def fetch_document_content(self, external_id: str) -> bytes:
        file = self.service.files().get(fileId=external_id, fields="id,name,mimeType").execute()
        content = await self._download_file(file)
        if not content:
            raise NotFoundError(f"File {external_id} not found or not downloadable")
        return content

Create /services/ingestion-service/tests/connectors/test_gdrive.py with comprehensive tests.
```

---

### Subtask 2.2.5: Salesforce Connector

**Claude Code Prompt:**
```
Create the Salesforce connector at /services/ingestion-service/src/aswa_ingestion/connectors/salesforce.py.

from simple_salesforce import Salesforce as SalesforceClient
from simple_salesforce.exceptions import SalesforceAuthenticationFailed

class SalesforceConnector(BaseConnector):
    """Connector for Salesforce API."""
    
    SOURCE_TYPE = "salesforce"
    
    # Objects to sync
    DEFAULT_OBJECTS = ["Account", "Contact", "Opportunity", "Lead", "Case", "Task", "Note"]
    
    def __init__(self, config: ConnectorConfig, tenant_id: UUID):
        super().__init__(config, tenant_id)
        self.client: SalesforceClient | None = None
    
    async def authenticate(self) -> bool:
        """
        Authenticate using OAuth or username/password.
        Config can contain:
        - credentials.access_token + credentials.instance_url (OAuth)
        - credentials.username + credentials.password + credentials.security_token (User/Pass)
        """
        try:
            if "access_token" in self.config.credentials:
                self.client = SalesforceClient(
                    instance_url=self.config.credentials["instance_url"],
                    session_id=self.config.credentials["access_token"]
                )
            else:
                self.client = SalesforceClient(
                    username=self.config.credentials["username"],
                    password=self.config.credentials["password"],
                    security_token=self.config.credentials["security_token"],
                    domain=self.config.credentials.get("domain", "login")
                )
            
            # Test connection
            self.client.describe()
            return True
        except SalesforceAuthenticationFailed as e:
            logger.error("Salesforce authentication failed", error=str(e))
            return False
    
    async def test_connection(self) -> ConnectionTestResult:
        start = time.monotonic()
        try:
            identity = self.client.restful("connect/organization")
            return ConnectionTestResult(
                success=True,
                message=f"Connected to {identity.get('name', 'Salesforce')}",
                details={"org_id": identity.get("orgId")},
                latency_ms=int((time.monotonic() - start) * 1000)
            )
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e), latency_ms=int((time.monotonic() - start) * 1000))
    
    async def fetch_documents(
        self,
        cursor: SyncCursor | None = None,
        batch_size: int = 100
    ) -> AsyncIterator[tuple[list[NormalizedDocument], SyncCursor | None]]:
        """Fetch records from configured Salesforce objects."""
        objects = self.config.settings.get("objects", self.DEFAULT_OBJECTS)
        
        # Parse cursor
        object_cursors = {}
        if cursor and cursor.cursor_type == "object_cursors":
            object_cursors = json.loads(cursor.value)
        
        for obj_name in objects:
            last_modified = object_cursors.get(obj_name, "1970-01-01T00:00:00Z")
            
            async for batch, new_timestamp in self._fetch_object(obj_name, last_modified, batch_size):
                object_cursors[obj_name] = new_timestamp
                new_cursor = SyncCursor(
                    cursor_type="object_cursors",
                    value=json.dumps(object_cursors),
                    timestamp=datetime.utcnow()
                )
                yield batch, new_cursor
    
    async def _fetch_object(
        self,
        object_name: str,
        since: str,
        batch_size: int
    ) -> AsyncIterator[tuple[list[NormalizedDocument], str]]:
        """Fetch records from a single Salesforce object."""
        # Get object description for field list
        try:
            desc = getattr(self.client, object_name).describe()
        except Exception as e:
            logger.error("Failed to describe object", object=object_name, error=str(e))
            return
        
        # Build field list (text fields only)
        text_fields = ["Id", "Name", "LastModifiedDate", "CreatedDate"]
        for field in desc["fields"]:
            if field["type"] in ["string", "textarea", "email", "phone", "url"]:
                text_fields.append(field["name"])
        
        fields = ", ".join(set(text_fields))
        
        # Query with SOQL
        query = f"""
            SELECT {fields}
            FROM {object_name}
            WHERE LastModifiedDate > {since}
            ORDER BY LastModifiedDate ASC
        """
        
        latest_timestamp = since
        
        try:
            result = self.client.query(query)
            
            while True:
                records = result.get("records", [])
                if not records:
                    break
                
                docs = []
                for record in records:
                    doc = self._record_to_document(record, object_name)
                    if doc:
                        docs.append(doc)
                        if record.get("LastModifiedDate", "") > latest_timestamp:
                            latest_timestamp = record["LastModifiedDate"]
                
                if docs:
                    yield docs, latest_timestamp
                
                if result.get("done"):
                    break
                
                result = self.client.query_more(result["nextRecordsUrl"], identifier_is_url=True)
                
        except Exception as e:
            logger.error("Failed to query object", object=object_name, error=str(e))
    
    def _record_to_document(self, record: dict, object_name: str) -> NormalizedDocument | None:
        """Convert Salesforce record to NormalizedDocument."""
        try:
            # Build content from all text fields
            content_parts = []
            for key, value in record.items():
                if key.startswith("attributes") or not value:
                    continue
                if isinstance(value, str) and len(value) > 10:
                    content_parts.append(f"{key}: {value}")
            
            content = "\n".join(content_parts)
            
            modified_time = datetime.fromisoformat(record["LastModifiedDate"].replace("Z", "+00:00"))
            
            return NormalizedDocument(
                source_id=self.SOURCE_TYPE,
                document_id=f"{object_name}:{record['Id']}",
                content=content,
                content_type="note",
                title=f"{object_name}: {record.get('Name', record['Id'])}",
                metadata={
                    "object_type": object_name,
                    "salesforce_id": record["Id"],
                    "created_date": record.get("CreatedDate"),
                    "last_modified": record["LastModifiedDate"]
                },
                timestamp=modified_time,
                version_hash=hashlib.md5(content.encode()).hexdigest()
            )
        except Exception as e:
            logger.error("Failed to convert record", error=str(e))
            return None
    
    async def fetch_document_content(self, external_id: str) -> bytes:
        object_name, record_id = external_id.split(":")
        record = getattr(self.client, object_name).get(record_id)
        return json.dumps(record).encode()

Create /services/ingestion-service/tests/connectors/test_salesforce.py with mocked simple_salesforce.
```

---

## Task 2.3: Vector Store Integration

### Subtask 2.3.1: Qdrant Vector Store

**Claude Code Prompt:**
```
Create the vector store integration at /services/ingestion-service/src/aswa_ingestion/vectorstore/.

1. /services/ingestion-service/src/aswa_ingestion/vectorstore/__init__.py:
from .qdrant import QdrantVectorStore
from .base import VectorStore

2. /services/ingestion-service/src/aswa_ingestion/vectorstore/base.py:
from abc import ABC, abstractmethod

class VectorRecord(BaseModel):
    id: str
    vector: list[float]
    payload: dict[str, Any]

class SearchResult(BaseModel):
    id: str
    score: float
    payload: dict[str, Any]

class VectorStore(ABC):
    @abstractmethod
    async def create_collection(self, name: str, vector_size: int) -> None: ...
    
    @abstractmethod
    async def collection_exists(self, name: str) -> bool: ...
    
    @abstractmethod
    async def upsert(self, collection: str, records: list[VectorRecord]) -> int: ...
    
    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[SearchResult]: ...
    
    @abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> int: ...
    
    @abstractmethod
    async def delete_by_filter(self, collection: str, filters: dict[str, Any]) -> int: ...

3. /services/ingestion-service/src/aswa_ingestion/vectorstore/qdrant.py:
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, 
    Filter, FieldCondition, MatchValue, MatchAny,
    UpdateStatus, PayloadSchemaType
)

class QdrantVectorStore(VectorStore):
    """Qdrant vector database integration."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        api_key: str | None = None,
        https: bool = False
    ):
        self.client = AsyncQdrantClient(
            host=host,
            port=port,
            api_key=api_key,
            https=https
        )
        self._metrics = MetricsRegistry("qdrant")