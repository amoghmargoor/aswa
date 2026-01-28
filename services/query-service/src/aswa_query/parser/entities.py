import re
from typing import Any
import structlog

from .models import ExtractedEntity, EntityType

logger = structlog.get_logger()


# Entity patterns
ENTITY_PATTERNS = {
    EntityType.MONEY: [
        r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|M|B|K))?",
        r"(?:USD|EUR|GBP)\s*[\d,]+(?:\.\d{2})?",
        r"[\d,]+(?:\.\d{2})?\s*(?:dollars|euros|pounds)",
    ],
    EntityType.PERCENTAGE: [
        r"\d+(?:\.\d+)?%",
        r"\d+(?:\.\d+)?\s*percent",
    ],
    EntityType.DATE: [
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\bQ[1-4]\s*\d{4}\b",
        r"\b(?:FY|fiscal year)\s*\d{4}\b",
    ],
}

# Common organization suffixes
ORG_SUFFIXES = [
    "Inc", "Corp", "Corporation", "LLC", "Ltd", "Company", "Co",
    "Group", "Holdings", "Partners", "Associates", "Industries",
]


class EntityExtractor:
    """Extract named entities from queries."""

    def __init__(self):
        self._compiled_patterns: dict[EntityType, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns."""
        for entity_type, patterns in ENTITY_PATTERNS.items():
            self._compiled_patterns[entity_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def extract(self, query: str) -> list[ExtractedEntity]:
        """Extract entities from query.

        Args:
            query: The query text

        Returns:
            List of extracted entities
        """
        entities = []

        # Pattern-based extraction
        for entity_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(query):
                    entities.append(ExtractedEntity(
                        text=match.group(),
                        entity_type=entity_type,
                        confidence=0.9,
                        start_pos=match.start(),
                        end_pos=match.end(),
                    ))

        # Organization detection
        entities.extend(self._extract_organizations(query))

        # Remove overlapping entities (keep higher confidence)
        entities = self._remove_overlaps(entities)

        logger.debug(
            "Entities extracted",
            query=query[:50],
            entity_count=len(entities),
        )

        return entities

    def _extract_organizations(self, query: str) -> list[ExtractedEntity]:
        """Extract organization names."""
        entities = []

        # Look for capitalized words followed by org suffixes
        org_pattern = rf"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+({'|'.join(ORG_SUFFIXES)})\b"
        for match in re.finditer(org_pattern, query):
            entities.append(ExtractedEntity(
                text=match.group(),
                entity_type=EntityType.ORGANIZATION,
                confidence=0.85,
                start_pos=match.start(),
                end_pos=match.end(),
            ))

        # Look for quoted company names
        quoted_pattern = r'"([^"]+)"'
        for match in re.finditer(quoted_pattern, query):
            entities.append(ExtractedEntity(
                text=match.group(1),
                entity_type=EntityType.ORGANIZATION,
                confidence=0.7,
                start_pos=match.start(),
                end_pos=match.end(),
            ))

        return entities

    def _remove_overlaps(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Remove overlapping entities, keeping higher confidence ones."""
        if len(entities) <= 1:
            return entities

        # Sort by start position
        sorted_entities = sorted(entities, key=lambda e: (e.start_pos, -e.confidence))
        result = []
        last_end = -1

        for entity in sorted_entities:
            if entity.start_pos >= last_end:
                result.append(entity)
                last_end = entity.end_pos

        return result

    def normalize_entity(self, entity: ExtractedEntity) -> str:
        """Normalize entity text."""
        text = entity.text.strip()

        if entity.entity_type == EntityType.MONEY:
            # Normalize money amounts
            text = text.replace(",", "").replace("$", "").strip()
            if "million" in text.lower() or "M" in text:
                text = text.replace("million", "").replace("M", "").strip()
                try:
                    value = float(text) * 1_000_000
                    text = str(value)
                except ValueError:
                    pass

        elif entity.entity_type == EntityType.PERCENTAGE:
            text = text.replace("%", "").replace("percent", "").strip()

        return text
