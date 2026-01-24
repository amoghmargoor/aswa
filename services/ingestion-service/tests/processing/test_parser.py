"""Tests for document parser."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_ingestion.processing.parser import (
    DocumentParser,
    ParsedDocument,
    DocumentElement,
)


class TestDocumentParser:
    """Tests for DocumentParser class."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create parser instance."""
        return DocumentParser(ocr_enabled=True, ocr_languages=["eng"])

    def test_supported_content_types(self, parser: DocumentParser) -> None:
        """Test that parser has expected supported types."""
        assert "application/pdf" in parser.SUPPORTED_TYPES
        assert "text/plain" in parser.SUPPORTED_TYPES
        assert "text/html" in parser.SUPPORTED_TYPES
        assert "message/rfc822" in parser.SUPPORTED_TYPES

    def test_detect_content_type_pdf(self, parser: DocumentParser) -> None:
        """Test PDF content type detection from magic bytes."""
        content = b"%PDF-1.4 some pdf content"
        detected = parser._detect_content_type(content, None)
        assert detected == "application/pdf"

    def test_detect_content_type_html(self, parser: DocumentParser) -> None:
        """Test HTML content type detection."""
        content = b"<!DOCTYPE html><html><body>Test</body></html>"
        detected = parser._detect_content_type(content, None)
        assert detected == "text/html"

    def test_detect_content_type_html_variant(self, parser: DocumentParser) -> None:
        """Test HTML content type detection from html tag."""
        content = b"<html><head></head><body>Test</body></html>"
        detected = parser._detect_content_type(content, None)
        assert detected == "text/html"

    def test_detect_content_type_email(self, parser: DocumentParser) -> None:
        """Test email content type detection."""
        content = b"From: test@example.com\nTo: other@example.com"
        detected = parser._detect_content_type(content, None)
        assert detected == "message/rfc822"

    def test_detect_content_type_from_filename(self, parser: DocumentParser) -> None:
        """Test content type detection from filename."""
        content = b"some content"
        detected = parser._detect_content_type(content, "document.pdf")
        assert detected == "application/pdf"

    def test_detect_content_type_default(self, parser: DocumentParser) -> None:
        """Test default content type when unknown."""
        content = b"random binary content \x00\x01\x02"
        detected = parser._detect_content_type(content, None)
        assert detected == "text/plain"

    def test_map_element_type_title(self, parser: DocumentParser) -> None:
        """Test element type mapping for title."""
        assert parser._map_element_type("Title") == "title"
        assert parser._map_element_type("TITLE") == "title"

    def test_map_element_type_narrative(self, parser: DocumentParser) -> None:
        """Test element type mapping for narrative text."""
        assert parser._map_element_type("NarrativeText") == "narrative_text"
        assert parser._map_element_type("UncategorizedText") == "narrative_text"

    def test_map_element_type_list_item(self, parser: DocumentParser) -> None:
        """Test element type mapping for list items."""
        assert parser._map_element_type("ListItem") == "list_item"

    def test_map_element_type_unknown(self, parser: DocumentParser) -> None:
        """Test element type mapping for unknown types."""
        assert parser._map_element_type("UnknownType") == "narrative_text"
        assert parser._map_element_type("") == "narrative_text"


class TestParseTextContent:
    """Tests for parsing plain text content."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create parser instance."""
        return DocumentParser()

    @pytest.mark.asyncio
    async def test_parse_plain_text(self, parser: DocumentParser) -> None:
        """Test parsing plain text content."""
        content = b"This is a simple text document.\n\nIt has multiple paragraphs."

        with patch(
            "aswa_ingestion.processing.parser.partition_text"
        ) as mock_partition:
            mock_element = MagicMock()
            mock_element.category = "NarrativeText"
            mock_element.__str__ = MagicMock(
                return_value="This is a simple text document."
            )
            mock_element.metadata = MagicMock()
            mock_element.metadata.page_number = None
            mock_partition.return_value = [mock_element]

            result = await parser.parse(content, "text/plain")

            assert isinstance(result, ParsedDocument)
            assert len(result.elements) > 0
            assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_parse_empty_text(self, parser: DocumentParser) -> None:
        """Test parsing empty text content."""
        content = b""

        with patch(
            "aswa_ingestion.processing.parser.partition_text"
        ) as mock_partition:
            mock_partition.return_value = []

            result = await parser.parse(content, "text/plain")

            assert isinstance(result, ParsedDocument)
            assert result.text == ""
            assert len(result.elements) == 0

    @pytest.mark.asyncio
    async def test_parse_unsupported_type(self, parser: DocumentParser) -> None:
        """Test parsing unsupported content type raises error."""
        content = b"some content"

        with pytest.raises(ValueError, match="Unsupported content type"):
            await parser.parse(content, "application/x-unsupported")


class TestParseWithElements:
    """Tests for parsing with structured elements."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create parser instance."""
        return DocumentParser()

    @pytest.mark.asyncio
    async def test_parse_html_with_structure(self, parser: DocumentParser) -> None:
        """Test parsing HTML with multiple element types."""
        content = b"<html><body><h1>Title</h1><p>Content</p></body></html>"

        with patch(
            "aswa_ingestion.processing.parser.partition_html"
        ) as mock_partition:
            title_element = MagicMock()
            title_element.category = "Title"
            title_element.__str__ = MagicMock(return_value="Title")
            title_element.metadata = MagicMock()
            title_element.metadata.page_number = None

            para_element = MagicMock()
            para_element.category = "NarrativeText"
            para_element.__str__ = MagicMock(return_value="Content")
            para_element.metadata = MagicMock()
            para_element.metadata.page_number = None

            mock_partition.return_value = [title_element, para_element]

            result = await parser.parse(content, "text/html")

            assert len(result.elements) == 2
            assert result.elements[0].type == "title"
            assert result.elements[1].type == "narrative_text"


class TestParseFromFile:
    """Tests for parsing from file path."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create parser instance."""
        return DocumentParser()

    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, parser: DocumentParser) -> None:
        """Test parsing non-existent file raises error."""
        from pathlib import Path

        with pytest.raises(Exception):
            await parser.parse_file(Path("/nonexistent/file.txt"))


class TestBuildParsedDocument:
    """Tests for building parsed document from elements."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create parser instance."""
        return DocumentParser()

    def test_build_with_empty_elements(self, parser: DocumentParser) -> None:
        """Test building document with no elements."""
        result = parser._build_parsed_document([])

        assert result.text == ""
        assert len(result.elements) == 0
        assert result.word_count == 0

    def test_build_with_whitespace_only_elements(
        self, parser: DocumentParser
    ) -> None:
        """Test building document skips whitespace-only elements."""
        element = MagicMock()
        element.category = "NarrativeText"
        element.__str__ = MagicMock(return_value="   \n\t  ")

        result = parser._build_parsed_document([element])

        assert len(result.elements) == 0
