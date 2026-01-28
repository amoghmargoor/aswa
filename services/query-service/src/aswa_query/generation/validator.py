import json
import re
from typing import Any
import structlog

from aswa_query.retrieval.models import ContextWindow
from .models import ValidationResult, GeneratedAnswer

logger = structlog.get_logger()


class AnswerValidator:
    """Validate generated answers."""

    def __init__(self, llm_client: Any | None = None):
        self.llm_client = llm_client

    def validate_basic(
        self,
        answer: GeneratedAnswer,
        context: ContextWindow,
    ) -> ValidationResult:
        """Perform basic validation checks.

        Args:
            answer: Generated answer
            context: Source context

        Returns:
            ValidationResult
        """
        issues = []
        confidence = 1.0

        # Check if answer is empty
        if not answer.answer or len(answer.answer.strip()) < 10:
            issues.append("Answer is too short or empty")
            confidence *= 0.3

        # Check for citations
        citation_pattern = re.compile(r'\[\d+\]')
        has_citations = bool(citation_pattern.search(answer.answer))

        if not has_citations and context.sources:
            issues.append("Answer lacks citations despite available sources")
            confidence *= 0.7

        # Check for hedging language that might indicate uncertainty
        uncertainty_phrases = [
            "I don't know",
            "I'm not sure",
            "cannot determine",
            "no information",
            "not mentioned",
        ]

        answer_lower = answer.answer.lower()
        uncertainty_count = sum(1 for phrase in uncertainty_phrases if phrase in answer_lower)
        if uncertainty_count > 2:
            issues.append("Answer contains excessive uncertainty language")
            confidence *= 0.6

        # Check answer length is reasonable
        if len(answer.answer) > 5000:
            issues.append("Answer may be excessively long")
            confidence *= 0.9

        return ValidationResult(
            is_valid=len(issues) == 0,
            confidence=confidence,
            issues=issues,
        )

    def validate_citations(
        self,
        answer: GeneratedAnswer,
        max_citation_index: int,
    ) -> ValidationResult:
        """Validate citation references.

        Args:
            answer: Generated answer
            max_citation_index: Maximum valid citation index

        Returns:
            ValidationResult
        """
        issues = []
        confidence = 1.0

        # Extract all citation indices
        citation_pattern = re.compile(r'\[(\d+)\]')
        matches = citation_pattern.findall(answer.answer)
        used_indices = [int(m) for m in matches]

        # Check for invalid indices
        invalid_indices = [i for i in used_indices if i > max_citation_index or i < 1]
        if invalid_indices:
            issues.append(f"Invalid citation indices: {invalid_indices}")
            confidence *= 0.7

        # Check for consecutive text without citations (potential hallucination)
        sentences = answer.answer.split('. ')
        uncited_streak = 0
        max_uncited = 0

        for sentence in sentences:
            if citation_pattern.search(sentence):
                uncited_streak = 0
            else:
                uncited_streak += 1
                max_uncited = max(max_uncited, uncited_streak)

        if max_uncited > 4:
            issues.append(f"Long uncited section ({max_uncited} sentences)")
            confidence *= 0.8

        return ValidationResult(
            is_valid=len(issues) == 0,
            confidence=confidence,
            issues=issues,
        )

    def check_factual_grounding(
        self,
        answer: GeneratedAnswer,
        context: ContextWindow,
    ) -> ValidationResult:
        """Check if answer is grounded in context.

        Args:
            answer: Generated answer
            context: Source context

        Returns:
            ValidationResult
        """
        issues = []
        suggestions = []
        confidence = 1.0

        # Extract key claims from answer
        answer_words = set(answer.answer.lower().split())
        context_words = set(context.content.lower().split())

        # Check word overlap
        if answer_words:
            overlap = len(answer_words & context_words) / len(answer_words)
            if overlap < 0.3:
                issues.append("Answer may contain content not from context")
                confidence *= 0.6
                suggestions.append("Review answer for potential hallucinations")

        # Check for specific numbers/dates not in context
        number_pattern = re.compile(r'\b\d{4,}\b|\$[\d,]+|\d+%')
        answer_numbers = set(number_pattern.findall(answer.answer))
        context_numbers = set(number_pattern.findall(context.content))

        ungrounded_numbers = answer_numbers - context_numbers
        if ungrounded_numbers:
            issues.append(f"Numbers not found in context: {ungrounded_numbers}")
            confidence *= 0.7

        return ValidationResult(
            is_valid=len(issues) == 0,
            confidence=confidence,
            issues=issues,
            suggestions=suggestions,
        )

    async def validate_with_llm(
        self,
        answer: GeneratedAnswer,
        context: ContextWindow,
        query: str,
    ) -> ValidationResult:
        """Use LLM to validate answer quality.

        Args:
            answer: Generated answer
            context: Source context
            query: Original query

        Returns:
            ValidationResult
        """
        if not self.llm_client:
            return ValidationResult(is_valid=True, confidence=0.5)

        from .prompts import PromptBuilder
        prompt_builder = PromptBuilder()
        messages = prompt_builder.build_validation_prompt(query, answer.answer, context)

        try:
            response = await self.llm_client.complete(messages, max_tokens=500)

            # Parse JSON response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return ValidationResult(
                    is_valid=result.get("is_valid", True),
                    confidence=result.get("confidence", 0.5),
                    issues=result.get("issues", []),
                    suggestions=result.get("suggestions", []),
                )

        except Exception as e:
            logger.error("LLM validation failed", error=str(e))

        return ValidationResult(is_valid=True, confidence=0.5)
