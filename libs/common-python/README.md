# ASWA Common Python Library

Shared utilities and models for ASWA Python services.

## Installation

```bash
poetry install
```

## Usage

### Exception Handling

```python
from aswa_common import AswaError, ErrorCode, ValidationError

# Raise specific error
raise ValidationError("Invalid email format", details={"field": "email"})

# Catch and convert to API response
try:
    # ... some operation
except AswaError as e:
    return e.to_api_response()
```

### Models

```python
from aswa_common.models import TenantContext, ApiResponse, PageRequest

# Create tenant context
context = TenantContext(
    tenant_id=UUID("..."),
    user_id=UUID("..."),
    roles={"admin", "user"}
)

# Check permissions
if context.is_admin():
    # ... admin logic

# Create API response
response = ApiResponse.ok(data={"result": "success"})
```

### Logging

```python
from aswa_common.logging import configure_logging, get_logger, LoggerContextVar

# Configure logging once at startup
configure_logging("my-service", log_level="INFO", json_output=True)

# Get logger
logger = get_logger(__name__)

# Set request context
LoggerContextVar.set(request_id="req-123", tenant_id=UUID("..."))

# Log with automatic context
logger.info("Processing request", extra={"key": "value"})
```

### Configuration

```python
from aswa_common.config import DatabaseSettings, RedisSettings

# Load from environment
db_settings = DatabaseSettings()
print(db_settings.async_url)

redis_settings = RedisSettings()
print(redis_settings.url)
```

### Resilience

```python
from aswa_common.resilience import retry_with_backoff, CircuitBreaker

# Retry with exponential backoff
@retry_with_backoff(max_attempts=3, base_delay=1.0)
async def fetch_data():
    # ... operation that might fail
    pass

# Circuit breaker
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)

async def call_external_service():
    return await breaker.call(external_api_call, arg1, arg2)
```

### HTTP Client

```python
from aswa_common.clients import BaseHttpClient

async with BaseHttpClient("https://api.example.com") as client:
    response = await client.get("/endpoint")
    data = response.json()
```

### Utilities

```python
from aswa_common.utils.hashing import md5_hash, sha256_hash
from aswa_common.utils.validation import validate_email, validate_uuid

# Hashing
content_hash = md5_hash("some content")
secure_hash = sha256_hash("secure content")

# Validation
email = validate_email("user@example.com")  # Raises ValidationError if invalid
user_id = validate_uuid("123e4567-e89b-12d3-a456-426614174000")
```

## Testing

```bash
pytest
pytest --cov=aswa_common --cov-report=html
```

## Development

```bash
# Format code
black .

# Lint
ruff check .

# Type check
mypy .
```
