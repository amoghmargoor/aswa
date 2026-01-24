"""Document parser for various file formats."""

import asyncio
import mimetypes
import tempfile
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from aswa_common.logging import get_logger

logger = get_logger(__name__)


class DocumentElement(BaseModel):
    """A single element extracted from a document."""

    type: Literal[
        "title",
        "narrative_text",
        "list_item",
        "table",
        "image",
        "header",
        "footer",
        "code",
        "formula",
    ]
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    page_number: int | None = None


class ParsedDocument(BaseModel):
    """Result of parsing a document."""

    text: str
    elements: list[DocumentElement]
    metadata: dict[str, Any] = Field(default_factory=dict)
    language: str | None = None
    word_count: int = 0


class DocumentParser:
    """Parse various document formats into structured text.

    Uses the unstructured library to extract text and structure
    from PDF, DOCX, HTML, plain text, and email files.
    """

    SUPPORTED_TYPES: dict[str, str] = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/html": "html",
        "text/plain": "text",
        "message/rfc822": "email",
        "text/markdown": "markdown",
        "application/msword": "doc",
        "text/csv": "csv",
    }

    def __init__(
        self,
        ocr_enabled: bool = True,
        ocr_languages: list[str] | None = None,
    ) -> None:
        """Initialize document parser.

        Args:
            ocr_enabled: Whether to use OCR for scanned PDFs
            ocr_languages: Languages to use for OCR (default: ["eng"])
        """
        self.ocr_enabled = ocr_enabled
        self.ocr_languages = ocr_languages or ["eng"]

    async def parse(
        self,
        content: bytes,
        content_type: str,
        filename: str | None = None,
    ) -> ParsedDocument:
        """Parse document content into structured elements.

        Args:
            content: Raw document bytes
            content_type: MIME type of the document
            filename: Optional filename for type detection

        Returns:
            ParsedDocument with extracted text, elements, and metadata

        Raises:
            ValueError: If content type is not supported
        """
        logger.info(
            f"Parsing document: content_type={content_type}, "
            f"size={len(content)} bytes, filename={filename}"
        )

        # Detect content type if not provided or generic
        if content_type in ("application/octet-stream", ""):
            content_type = self._detect_content_type(content, filename)

        if content_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported content type: {content_type}")

        doc_type = self.SUPPORTED_TYPES[content_type]

        # Run parsing in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        elements = await loop.run_in_executor(
            None,
            self._parse_content,
            content,
            doc_type,
            filename,
        )

        # Build parsed document
        parsed = self._build_parsed_document(elements)

        logger.info(
            f"Parsed document: {len(parsed.elements)} elements, "
            f"{parsed.word_count} words"
        )

        return parsed

    async def parse_file(self, file_path: Path) -> ParsedDocument:
        """Parse a document from file path.

        Args:
            file_path: Path to the document file

        Returns:
            ParsedDocument with extracted content
        """
        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))

        if content_type is None:
            content_type = "application/octet-stream"

        return await self.parse(
            content=content,
            content_type=content_type,
            filename=file_path.name,
        )

    def _detect_content_type(
        self,
        content: bytes,
        filename: str | None,
    ) -> str:
        """Detect content type from content and filename.

        Args:
            content: Raw content bytes
            filename: Optional filename

        Returns:
            Detected MIME type
        """
        # Try filename first
        if filename:
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type:
                return guessed_type

        # Magic number detection
        if content.startswith(b"%PDF"):
            return "application/pdf"
        if content.startswith(b"PK"):
            # Could be DOCX, XLSX, etc.
            if filename and filename.endswith(".docx"):
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if content.startswith(b"<!DOCTYPE html") or content.startswith(b"<html"):
            return "text/html"
        if content.startswith(b"From:") or content.startswith(b"MIME-Version"):
            return "message/rfc822"

        # Default to plain text
        return "text/plain"

    def _parse_content(
        self,
        content: bytes,
        doc_type: str,
        filename: str | None,
    ) -> list[Any]:
        """Parse content using unstructured library.

        This runs synchronously and should be called from a thread pool.

        Args:
            content: Raw content bytes
            doc_type: Document type identifier
            filename: Optional filename

        Returns:
            List of unstructured elements
        """
        # Import here to avoid import time overhead
        from unstructured.partition.auto import partition
        from unstructured.partition.pdf import partition_pdf
        from unstructured.partition.docx import partition_docx
        from unstructured.partition.html import partition_html
        from unstructured.partition.text import partition_text
        from unstructured.partition.email import partition_email
        from unstructured.partition.md import partition_md

        # Write content to temp file for parsing
        suffix = f".{doc_type}" if doc_type != "text" else ".txt"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            if doc_type == "pdf":
                elements = partition_pdf(
                    filename=temp_path,
                    strategy="auto",
                    infer_table_structure=True,
                    languages=self.ocr_languages if self.ocr_enabled else None,
                )
            elif doc_type == "docx":
                elements = partition_docx(filename=temp_path)
            elif doc_type == "html":
                elements = partition_html(filename=temp_path)
            elif doc_type == "text":
                elements = partition_text(filename=temp_path)
            elif doc_type == "email":
                elements = partition_email(filename=temp_path)
            elif doc_type == "markdown":
                elements = partition_md(filename=temp_path)
            else:
                # Fallback to auto detection
                elements = partition(filename=temp_path)

            return list(elements)

        except Exception as e:
            logger.exception(f"Failed to parse document: {e}")
            raise ValueError(f"Failed to parse document: {e}") from e

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    def _build_parsed_document(self, elements: list[Any]) -> ParsedDocument:
        """Build ParsedDocument from unstructured elements.

        Args:
            elements: List of unstructured elements

        Returns:
            ParsedDocument instance
        """
        doc_elements: list[DocumentElement] = []
        all_text_parts: list[str] = []
        metadata: dict[str, Any] = {}

        for element in elements:
            # Get element type
            element_type = self._map_element_type(element.category)

            # Get text content
            text = str(element)
            if not text.strip():
                continue

            all_text_parts.append(text)

            # Extract element metadata
            elem_metadata: dict[str, Any] = {}
            page_number = None

            if hasattr(element, "metadata"):
                if hasattr(element.metadata, "page_number"):
                    page_number = element.metadata.page_number
                if hasattr(element.metadata, "filename"):
                    metadata["filename"] = element.metadata.filename
                if hasattr(element.metadata, "languages"):
                    metadata["languages"] = element.metadata.languages

            doc_elements.append(
                DocumentElement(
                    type=element_type,
                    text=text,
                    metadata=elem_metadata,
                    page_number=page_number,
                )
            )

        # Build full text
        full_text = "\n\n".join(all_text_parts)
        word_count = len(full_text.split())

        # Detect language from metadata or content
        language = None
        if "languages" in metadata and metadata["languages"]:
            language = metadata["languages"][0]

        return ParsedDocument(
            text=full_text,
            elements=doc_elements,
            metadata=metadata,
            language=language,
            word_count=word_count,
        )

    def _map_element_type(
        self,
        category: str,
    ) -> Literal[
        "title",
        "narrative_text",
        "list_item",
        "table",
        "image",
        "header",
        "footer",
        "code",
        "formula",
    ]:
        """Map unstructured element category to our element types.

        Args:
            category: Unstructured element category

        Returns:
            Mapped element type
        """
        category_lower = category.lower() if category else ""

        mapping = {
            "title": "title",
            "narrative_text": "narrative_text",
            "narrativetext": "narrative_text",
            "uncategorizedtext": "narrative_text",
            "listitem": "list_item",
            "list_item": "list_item",
            "table": "table",
            "image": "image",
            "figure": "image",
            "header": "header",
            "footer": "footer",
            "codeblock": "code",
            "code": "code",
            "formula": "formula",
        }

        return mapping.get(category_lower, "narrative_text")
