import re
from typing import Any
from uuid import UUID
import hashlib
import structlog

from .models import ParsedQuery, QueryIntent, ExtractedEntity, QueryFilter, TimeRange
from .intent import IntentClassifier
from .entities import EntityExtractor
from .filters import FilterExtractor
from .temporal import TemporalParser

logger = structlog.get_logger()


# Stop words to remove during normalization
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "from", "up", "down", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "and", "but", "if", "or", "because", "as", "until", "while",
    "please", "tell", "me", "show", "give", "find", "get", "i", "want",
}


class QueryParser:
    """Parse natural language queries into structured representations."""

    def __init__(
        self,
        intent_classifier: IntentClassifier | None = None,
        entity_extractor: EntityExtractor | None = None,
        filter_extractor: FilterExtractor | None = None,
        temporal_parser: TemporalParser | None = None,
    ):
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.filter_extractor = filter_extractor or FilterExtractor()
        self.temporal_parser = temporal_parser or TemporalParser()

    def parse(
        self,
        query: str,
        document_scope: list[UUID] | None = None,
    ) -> ParsedQuery:
        """Parse a natural language query.

        Args:
            query: The query text
            document_scope: Optional document IDs to scope the query

        Returns:
            ParsedQuery with all extracted components
        """
        # Normalize query
        normalized = self._normalize_query(query)

        # Classify intent
        intent, confidence = self.intent_classifier.classify(query)

        # Extract entities
        entities = self.entity_extractor.extract(query)

        # Extract filters
        filters = self.filter_extractor.extract(query)

        # Parse temporal expressions
        time_range = self.temporal_parser.parse(query)

        # Extract keywords
        keywords = self._extract_keywords(normalized)

        # Expand terms (synonyms, related terms)
        expanded = self._expand_terms(keywords)

        parsed = ParsedQuery(
            original_query=query,
            normalized_query=normalized,
            intent=intent,
            confidence=confidence,
            entities=entities,
            filters=filters,
            time_range=time_range,
            keywords=keywords,
            expanded_terms=expanded,
            document_scope=document_scope,
        )

        logger.info(
            "Query parsed",
            intent=intent,
            confidence=confidence,
            entity_count=len(entities),
            filter_count=len(filters),
            has_temporal=time_range is not None,
        )

        return parsed

    def _normalize_query(self, query: str) -> str:
        """Normalize query text."""
        # Convert to lowercase
        normalized = query.lower().strip()

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized)

        # Remove punctuation except for meaningful ones
        normalized = re.sub(r"[^\w\s\-\.\?\$%]", "", normalized)

        return normalized

    def _extract_keywords(self, normalized_query: str) -> list[str]:
        """Extract meaningful keywords from query."""
        words = normalized_query.split()
        keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        return keywords

    def _expand_terms(self, keywords: list[str]) -> list[str]:
        """Expand keywords with synonyms and related terms."""
        # Synonym mappings
        synonyms = {
            "risk": ["threat", "danger", "concern", "issue"],
            "opportunity": ["potential", "upside", "growth"],
            "company": ["organization", "firm", "corporation", "business"],
            "increase": ["growth", "rise", "gain", "improvement"],
            "decrease": ["decline", "drop", "reduction", "fall"],
            "revenue": ["sales", "income", "earnings"],
            "profit": ["earnings", "income", "margin"],
            "cost": ["expense", "spending", "expenditure"],
        }

        expanded = []
        for keyword in keywords:
            if keyword in synonyms:
                expanded.extend(synonyms[keyword])

        return list(set(expanded))

    def get_query_hash(self, parsed: ParsedQuery) -> str:
        """Generate hash for query caching."""
        components = [
            parsed.normalized_query,
            parsed.intent.value,
            str(sorted([f.field for f in parsed.filters])),
            str(parsed.document_scope) if parsed.document_scope else "",
        ]
        content = ":".join(components)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_search_query(self, parsed: ParsedQuery) -> dict[str, Any]:
        """Convert parsed query to search parameters."""
        return {
            "query_text": parsed.normalized_query,
            "keywords": parsed.keywords + parsed.expanded_terms,
            "filters": [
                {"field": f.field, "operator": f.operator, "value": f.value}
                for f in parsed.filters
            ],
            "time_range": {
                "start": parsed.time_range.start.isoformat() if parsed.time_range and parsed.time_range.start else None,
                "end": parsed.time_range.end.isoformat() if parsed.time_range and parsed.time_range.end else None,
            } if parsed.time_range else None,
            "document_ids": [str(d) for d in parsed.document_scope] if parsed.document_scope else None,
        }
