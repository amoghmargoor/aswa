import re
from typing import Any
import structlog

from .models import QueryIntent

logger = structlog.get_logger()


# Intent patterns
INTENT_PATTERNS = {
    QueryIntent.SUMMARY: [
        r"\b(summarize|summary|overview|brief|highlight)\b",
        r"\bwhat (is|are) the (main|key|important)\b",
        r"\bgive me (a|an) (overview|summary)\b",
    ],
    QueryIntent.COMPARISON: [
        r"\b(compare|comparison|versus|vs\.?|differ|difference)\b",
        r"\bhow does .+ compare to\b",
        r"\bwhat('s| is) the difference between\b",
    ],
    QueryIntent.TREND: [
        r"\b(trend|trending|over time|growth|decline|change)\b",
        r"\bhow has .+ changed\b",
        r"\b(increase|decrease|rise|fall) in\b",
    ],
    QueryIntent.RISK: [
        r"\b(risk|danger|threat|concern|issue|problem|vulnerability)\b",
        r"\bwhat (could|might|may) go wrong\b",
        r"\bpotential (issues|problems)\b",
    ],
    QueryIntent.OPPORTUNITY: [
        r"\b(opportunity|opportunities|potential|growth|upside)\b",
        r"\bwhat (can|could) we (do|improve)\b",
        r"\bareas for (improvement|growth)\b",
    ],
    QueryIntent.ENTITY: [
        r"\bwho is\b",
        r"\bwhat (is|are) .+ (company|organization|person)\b",
        r"\btell me about\b",
    ],
    QueryIntent.LIST: [
        r"\b(list|enumerate|show me all|what are all)\b",
        r"\bhow many\b",
        r"\bgive me a list\b",
    ],
    QueryIntent.EXPLANATION: [
        r"\b(why|explain|how does|how do)\b",
        r"\bwhat causes\b",
        r"\breason for\b",
    ],
}


class IntentClassifier:
    """Classify query intent using patterns and heuristics."""

    def __init__(self):
        self._compiled_patterns: dict[QueryIntent, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns."""
        for intent, patterns in INTENT_PATTERNS.items():
            self._compiled_patterns[intent] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def classify(self, query: str) -> tuple[QueryIntent, float]:
        """Classify query intent.

        Args:
            query: The query text

        Returns:
            Tuple of (intent, confidence)
        """
        query_lower = query.lower()
        scores: dict[QueryIntent, float] = {}

        # Pattern matching
        for intent, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    scores[intent] = scores.get(intent, 0) + 0.3

        # Keyword boosting
        scores = self._apply_keyword_boost(query_lower, scores)

        # Question word analysis
        scores = self._analyze_question_words(query_lower, scores)

        if not scores:
            return QueryIntent.FACTUAL, 0.5

        # Get highest scoring intent
        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent], 1.0)

        logger.debug(
            "Intent classified",
            query=query[:50],
            intent=best_intent,
            confidence=confidence,
        )

        return best_intent, confidence

    def _apply_keyword_boost(
        self,
        query: str,
        scores: dict[QueryIntent, float],
    ) -> dict[QueryIntent, float]:
        """Boost scores based on keywords."""
        keyword_boosts = {
            QueryIntent.RISK: ["risk", "threat", "danger", "problem", "concern"],
            QueryIntent.OPPORTUNITY: ["opportunity", "growth", "potential", "improve"],
            QueryIntent.SUMMARY: ["summary", "summarize", "overview", "brief"],
            QueryIntent.TREND: ["trend", "over time", "changed", "growth rate"],
        }

        for intent, keywords in keyword_boosts.items():
            for keyword in keywords:
                if keyword in query:
                    scores[intent] = scores.get(intent, 0) + 0.2

        return scores

    def _analyze_question_words(
        self,
        query: str,
        scores: dict[QueryIntent, float],
    ) -> dict[QueryIntent, float]:
        """Analyze question words for intent hints."""
        if query.startswith("who"):
            scores[QueryIntent.ENTITY] = scores.get(QueryIntent.ENTITY, 0) + 0.3
        elif query.startswith("why"):
            scores[QueryIntent.EXPLANATION] = scores.get(QueryIntent.EXPLANATION, 0) + 0.3
        elif query.startswith("how many"):
            scores[QueryIntent.LIST] = scores.get(QueryIntent.LIST, 0) + 0.3
        elif query.startswith("what are the"):
            scores[QueryIntent.LIST] = scores.get(QueryIntent.LIST, 0) + 0.2

        return scores

    def get_all_scores(self, query: str) -> dict[QueryIntent, float]:
        """Get scores for all intents."""
        query_lower = query.lower()
        scores: dict[QueryIntent, float] = {}

        for intent, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    scores[intent] = scores.get(intent, 0) + 0.3

        scores = self._apply_keyword_boost(query_lower, scores)
        scores = self._analyze_question_words(query_lower, scores)

        return scores
