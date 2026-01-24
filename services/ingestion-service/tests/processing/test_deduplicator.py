"""Tests for document deduplicator."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from datasketch import MinHash

from aswa_ingestion.processing.deduplicator import (
    DocumentDeduplicator,
    DuplicateCheckResult,
)


class TestDocumentDeduplicator:
    """Tests for DocumentDeduplicator class."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator(
            similarity_threshold=0.8,
            num_perm=128,
            ngram_size=5,
        )

    def test_init(self, deduplicator: DocumentDeduplicator) -> None:
        """Test deduplicator initialization."""
        assert deduplicator.similarity_threshold == 0.8
        assert deduplicator.num_perm == 128
        assert deduplicator.ngram_size == 5


class TestComputeHash:
    """Tests for hash computation."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator()

    def test_compute_hash_deterministic(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test that hash is deterministic."""
        content = "Test content"
        hash1 = deduplicator.compute_hash(content)
        hash2 = deduplicator.compute_hash(content)

        assert hash1 == hash2

    def test_compute_hash_different_content(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test that different content produces different hash."""
        hash1 = deduplicator.compute_hash("Content A")
        hash2 = deduplicator.compute_hash("Content B")

        assert hash1 != hash2

    def test_compute_sha256(self, deduplicator: DocumentDeduplicator) -> None:
        """Test SHA-256 hash computation."""
        content = "Test content"
        hash_result = deduplicator.compute_sha256(content)

        assert len(hash_result) == 64  # SHA-256 produces 64 hex chars
        assert hash_result == deduplicator.compute_sha256(content)

    def test_compute_sha256_bytes(self, deduplicator: DocumentDeduplicator) -> None:
        """Test SHA-256 hash with bytes input."""
        content = b"Test content"
        hash_result = deduplicator.compute_sha256(content)

        assert len(hash_result) == 64


class TestComputeMinHash:
    """Tests for MinHash computation."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator(num_perm=128, ngram_size=5)

    def test_compute_minhash_returns_minhash(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test that MinHash object is returned."""
        content = "This is test content for hashing."
        minhash = deduplicator.compute_minhash(content)

        assert isinstance(minhash, MinHash)

    def test_compute_minhash_similar_content(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test that similar content produces similar MinHash."""
        content1 = "This is a test document with some content."
        content2 = "This is a test document with some content!"

        minhash1 = deduplicator.compute_minhash(content1)
        minhash2 = deduplicator.compute_minhash(content2)

        similarity = minhash1.jaccard(minhash2)
        assert similarity > 0.8

    def test_compute_minhash_different_content(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test that different content produces different MinHash."""
        content1 = "The quick brown fox jumps over the lazy dog."
        content2 = "Completely different and unrelated content here."

        minhash1 = deduplicator.compute_minhash(content1)
        minhash2 = deduplicator.compute_minhash(content2)

        similarity = minhash1.jaccard(minhash2)
        assert similarity < 0.3

    def test_compute_minhash_normalizes_case(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test that MinHash normalizes case."""
        content1 = "Test Content"
        content2 = "test content"

        minhash1 = deduplicator.compute_minhash(content1)
        minhash2 = deduplicator.compute_minhash(content2)

        similarity = minhash1.jaccard(minhash2)
        assert similarity == 1.0


class TestIsNearDuplicate:
    """Tests for near-duplicate detection."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator(similarity_threshold=0.8)

    def test_is_near_duplicate_true(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test detecting near-duplicate."""
        content = "This is a test document with substantial content."
        minhash = deduplicator.compute_minhash(content)

        similar_content = "This is a test document with substantial content!"
        similar_minhash = deduplicator.compute_minhash(similar_content)

        existing = [("doc-123", similar_minhash)]

        is_dup, doc_id, score = deduplicator.is_near_duplicate(minhash, existing)

        assert is_dup is True
        assert doc_id == "doc-123"
        assert score is not None
        assert score >= 0.8

    def test_is_near_duplicate_false(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test non-duplicate detection."""
        content1 = "This is completely different content about cats."
        content2 = "Unrelated document discussing programming topics."

        minhash1 = deduplicator.compute_minhash(content1)
        minhash2 = deduplicator.compute_minhash(content2)

        existing = [("doc-456", minhash2)]

        is_dup, doc_id, score = deduplicator.is_near_duplicate(minhash1, existing)

        assert is_dup is False
        assert doc_id is None

    def test_is_near_duplicate_empty_list(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test with no existing documents."""
        minhash = deduplicator.compute_minhash("Some content")

        is_dup, doc_id, score = deduplicator.is_near_duplicate(minhash, [])

        assert is_dup is False
        assert doc_id is None
        assert score is None


class TestLSHIndex:
    """Tests for LSH index operations."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator()

    def test_add_to_index(self, deduplicator: DocumentDeduplicator) -> None:
        """Test adding document to index."""
        content = "Test document content."
        minhash = deduplicator.compute_minhash(content)

        deduplicator.add_to_index("doc-1", minhash)

        assert "doc-1" in deduplicator._minhash_cache

    def test_add_duplicate_id(self, deduplicator: DocumentDeduplicator) -> None:
        """Test adding duplicate ID doesn't raise."""
        minhash = deduplicator.compute_minhash("Content")

        deduplicator.add_to_index("doc-1", minhash)
        deduplicator.add_to_index("doc-1", minhash)  # Should not raise

    def test_remove_from_index(self, deduplicator: DocumentDeduplicator) -> None:
        """Test removing document from index."""
        minhash = deduplicator.compute_minhash("Content")
        deduplicator.add_to_index("doc-1", minhash)

        deduplicator.remove_from_index("doc-1")

        assert "doc-1" not in deduplicator._minhash_cache

    def test_remove_nonexistent(self, deduplicator: DocumentDeduplicator) -> None:
        """Test removing non-existent document doesn't raise."""
        deduplicator.remove_from_index("nonexistent")  # Should not raise

    def test_query_similar(self, deduplicator: DocumentDeduplicator) -> None:
        """Test querying similar documents."""
        content = "This is a test document with some content."
        minhash = deduplicator.compute_minhash(content)
        deduplicator.add_to_index("doc-1", minhash)

        similar_content = "This is a test document with some content!"
        similar_minhash = deduplicator.compute_minhash(similar_content)

        results = deduplicator.query_similar(similar_minhash)

        assert "doc-1" in results

    def test_clear_index(self, deduplicator: DocumentDeduplicator) -> None:
        """Test clearing the index."""
        minhash = deduplicator.compute_minhash("Content")
        deduplicator.add_to_index("doc-1", minhash)

        deduplicator.clear_index()

        assert len(deduplicator._minhash_cache) == 0


class TestCheckDuplicate:
    """Tests for full duplicate checking."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator()

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_check_duplicate_exact_found(
        self,
        deduplicator: DocumentDeduplicator,
        mock_db: AsyncMock,
    ) -> None:
        """Test finding exact duplicate."""
        existing_doc = MagicMock()
        existing_doc.id = uuid4()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_doc)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await deduplicator.check_duplicate(
            content="Test content",
            tenant_id=uuid4(),
            db=mock_db,
        )

        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"
        assert result.duplicate_id == existing_doc.id
        assert result.similarity_score == 1.0

    @pytest.mark.asyncio
    async def test_check_duplicate_none_found(
        self,
        deduplicator: DocumentDeduplicator,
        mock_db: AsyncMock,
    ) -> None:
        """Test no duplicate found."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await deduplicator.check_duplicate(
            content="Unique content",
            tenant_id=uuid4(),
            db=mock_db,
        )

        assert result.is_duplicate is False
        assert result.duplicate_type == "none"
        assert result.duplicate_id is None


class TestEstimateSimilarity:
    """Tests for similarity estimation."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator()

    def test_estimate_similarity_identical(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test similarity of identical content."""
        content = "This is the same content."
        similarity = deduplicator.estimate_similarity(content, content)

        assert similarity == 1.0

    def test_estimate_similarity_different(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test similarity of different content."""
        content1 = "The quick brown fox jumps over the lazy dog."
        content2 = "Python is a great programming language for data science."

        similarity = deduplicator.estimate_similarity(content1, content2)

        assert similarity < 0.3


class TestGetShingles:
    """Tests for shingle generation."""

    @pytest.fixture
    def deduplicator(self) -> DocumentDeduplicator:
        """Create deduplicator instance."""
        return DocumentDeduplicator(ngram_size=3)

    def test_get_shingles(self, deduplicator: DocumentDeduplicator) -> None:
        """Test shingle generation."""
        shingles = deduplicator._get_shingles("hello world")

        assert isinstance(shingles, set)
        assert len(shingles) > 0
        assert all(len(s) == 3 for s in shingles)

    def test_get_shingles_short_text(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test shingles for text shorter than ngram size."""
        shingles = deduplicator._get_shingles("hi")

        assert shingles == {"hi"}

    def test_get_shingles_normalizes_whitespace(
        self, deduplicator: DocumentDeduplicator
    ) -> None:
        """Test that shingles normalize whitespace."""
        shingles1 = deduplicator._get_shingles("hello   world")
        shingles2 = deduplicator._get_shingles("hello world")

        assert shingles1 == shingles2


class TestDuplicateCheckResult:
    """Tests for DuplicateCheckResult model."""

    def test_result_no_duplicate(self) -> None:
        """Test result for no duplicate."""
        result = DuplicateCheckResult(
            is_duplicate=False,
            duplicate_type="none",
        )

        assert result.is_duplicate is False
        assert result.duplicate_id is None
        assert result.similarity_score is None

    def test_result_exact_duplicate(self) -> None:
        """Test result for exact duplicate."""
        doc_id = uuid4()
        result = DuplicateCheckResult(
            is_duplicate=True,
            duplicate_type="exact",
            duplicate_id=doc_id,
            similarity_score=1.0,
        )

        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"
        assert result.duplicate_id == doc_id

    def test_result_near_duplicate(self) -> None:
        """Test result for near duplicate."""
        doc_id = uuid4()
        result = DuplicateCheckResult(
            is_duplicate=True,
            duplicate_type="near",
            duplicate_id=doc_id,
            similarity_score=0.85,
        )

        assert result.duplicate_type == "near"
        assert result.similarity_score == 0.85
