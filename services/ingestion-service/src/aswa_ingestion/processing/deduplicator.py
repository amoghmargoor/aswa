"""Document deduplication for detecting exact and near-duplicate documents."""

import hashlib
from typing import Literal
from uuid import UUID

from datasketch import MinHash, MinHashLSH
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.logging import get_logger

logger = get_logger(__name__)


class DuplicateCheckResult(BaseModel):
    """Result of duplicate checking."""

    is_duplicate: bool
    duplicate_type: Literal["exact", "near", "none"]
    duplicate_id: UUID | None = None
    similarity_score: float | None = None


class DocumentDeduplicator:
    """Detect duplicate and near-duplicate documents.

    Uses MD5 hash for exact duplicate detection and MinHash
    with Locality Sensitive Hashing for near-duplicate detection.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        num_perm: int = 128,
        ngram_size: int = 5,
    ) -> None:
        """Initialize deduplicator.

        Args:
            similarity_threshold: Jaccard similarity threshold for near-duplicates
            num_perm: Number of permutations for MinHash
            ngram_size: Size of n-grams for shingling
        """
        self.similarity_threshold = similarity_threshold
        self.num_perm = num_perm
        self.ngram_size = ngram_size

        # LSH index for fast near-duplicate lookup
        self._lsh = MinHashLSH(
            threshold=similarity_threshold,
            num_perm=num_perm,
        )
        self._minhash_cache: dict[str, MinHash] = {}

        logger.debug(
            f"DocumentDeduplicator initialized: threshold={similarity_threshold}, "
            f"num_perm={num_perm}, ngram_size={ngram_size}"
        )

    def compute_hash(self, content: str) -> str:
        """Compute MD5 hash for exact duplicate detection.

        Args:
            content: Document content

        Returns:
            MD5 hash string
        """
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def compute_sha256(self, content: bytes | str) -> str:
        """Compute SHA-256 hash for content.

        Args:
            content: Document content (bytes or string)

        Returns:
            SHA-256 hash string
        """
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def compute_minhash(self, content: str) -> MinHash:
        """Compute MinHash signature for near-duplicate detection.

        Uses n-gram shingling to create a set representation
        of the document, then computes MinHash signature.

        Args:
            content: Document content

        Returns:
            MinHash signature
        """
        # Normalize content
        content = content.lower().strip()

        # Create shingles (n-grams)
        shingles = self._get_shingles(content)

        # Create MinHash
        minhash = MinHash(num_perm=self.num_perm)
        for shingle in shingles:
            minhash.update(shingle.encode("utf-8"))

        return minhash

    def is_near_duplicate(
        self,
        minhash: MinHash,
        existing_hashes: list[tuple[str, MinHash]],
    ) -> tuple[bool, str | None, float | None]:
        """Check if document is near-duplicate of any existing document.

        Args:
            minhash: MinHash of new document
            existing_hashes: List of (doc_id, minhash) tuples

        Returns:
            Tuple of (is_duplicate, duplicate_id, similarity_score)
        """
        for doc_id, existing_minhash in existing_hashes:
            similarity = minhash.jaccard(existing_minhash)

            if similarity >= self.similarity_threshold:
                logger.debug(
                    f"Found near-duplicate: doc_id={doc_id}, "
                    f"similarity={similarity:.3f}"
                )
                return True, doc_id, similarity

        return False, None, None

    def add_to_index(self, doc_id: str, minhash: MinHash) -> None:
        """Add document to LSH index for fast lookup.

        Args:
            doc_id: Document identifier
            minhash: MinHash signature
        """
        try:
            self._lsh.insert(doc_id, minhash)
            self._minhash_cache[doc_id] = minhash
        except ValueError:
            # Already in index
            pass

    def remove_from_index(self, doc_id: str) -> None:
        """Remove document from LSH index.

        Args:
            doc_id: Document identifier
        """
        try:
            self._lsh.remove(doc_id)
            self._minhash_cache.pop(doc_id, None)
        except KeyError:
            pass

    def query_similar(self, minhash: MinHash) -> list[str]:
        """Query LSH index for similar documents.

        Args:
            minhash: MinHash signature to query

        Returns:
            List of similar document IDs
        """
        return list(self._lsh.query(minhash))

    async def check_duplicate(
        self,
        content: str,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> DuplicateCheckResult:
        """Check for exact and near duplicates in database.

        Args:
            content: Document content
            tenant_id: Tenant ID for isolation
            db: Database session

        Returns:
            DuplicateCheckResult with duplicate status
        """
        from aswa_common.db.models import Document

        logger.debug("Checking for duplicates")

        # Step 1: Check exact duplicate by hash
        content_hash = self.compute_sha256(content)

        stmt = select(Document).where(
            Document.content_hash == content_hash,
            Document.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Found exact duplicate: {existing.id}")
            return DuplicateCheckResult(
                is_duplicate=True,
                duplicate_type="exact",
                duplicate_id=existing.id,
                similarity_score=1.0,
            )

        # Step 2: Check near-duplicate using MinHash
        minhash = self.compute_minhash(content)

        # Query LSH index first (in-memory, fast)
        similar_ids = self.query_similar(minhash)

        if similar_ids:
            # Verify similarity with actual MinHash comparison
            for doc_id in similar_ids:
                if doc_id in self._minhash_cache:
                    existing_minhash = self._minhash_cache[doc_id]
                    similarity = minhash.jaccard(existing_minhash)

                    if similarity >= self.similarity_threshold:
                        logger.info(
                            f"Found near-duplicate: {doc_id}, "
                            f"similarity={similarity:.3f}"
                        )
                        return DuplicateCheckResult(
                            is_duplicate=True,
                            duplicate_type="near",
                            duplicate_id=UUID(doc_id),
                            similarity_score=similarity,
                        )

        # No duplicates found
        return DuplicateCheckResult(
            is_duplicate=False,
            duplicate_type="none",
            duplicate_id=None,
            similarity_score=None,
        )

    def _get_shingles(self, text: str) -> set[str]:
        """Create n-gram shingles from text.

        Args:
            text: Input text

        Returns:
            Set of shingle strings
        """
        # Remove extra whitespace
        text = " ".join(text.split())

        if len(text) < self.ngram_size:
            return {text}

        shingles: set[str] = set()
        for i in range(len(text) - self.ngram_size + 1):
            shingle = text[i : i + self.ngram_size]
            shingles.add(shingle)

        return shingles

    def estimate_similarity(self, content1: str, content2: str) -> float:
        """Estimate Jaccard similarity between two documents.

        Args:
            content1: First document content
            content2: Second document content

        Returns:
            Estimated Jaccard similarity
        """
        minhash1 = self.compute_minhash(content1)
        minhash2 = self.compute_minhash(content2)
        return minhash1.jaccard(minhash2)

    def clear_index(self) -> None:
        """Clear the LSH index."""
        self._lsh = MinHashLSH(
            threshold=self.similarity_threshold,
            num_perm=self.num_perm,
        )
        self._minhash_cache.clear()
