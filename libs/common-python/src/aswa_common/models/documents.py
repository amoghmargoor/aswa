"""Document models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class NormalizedDocument(BaseModel):
    """Normalized document model for ingestion."""

    source_id: str
    document_id: str
    content: str
    content_type: Literal["email", "message", "document", "transcript"]
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    version_hash: str

    @field_validator("version_hash")
    @classmethod
    def validate_hash(cls, v: str) -> str:
        """Validate that hash is 32-char hex string (MD5).

        Args:
            v: The hash value

        Returns:
            Validated hash

        Raises:
            ValueError: If hash is invalid
        """
        if not (len(v) == 32 and all(c in "0123456789abcdef" for c in v.lower())):
            raise ValueError("version_hash must be a 32-character hexadecimal string")
        return v.lower()
