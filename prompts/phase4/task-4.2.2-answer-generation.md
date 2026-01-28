# Task 4.2.2: Answer Generation with Citations

## Context

You are working on the ASWA query-service at `/services/query-service/`. The retrieval pipeline (Task 4.2.1) provides relevant context. Now we need to generate answers using an LLM with proper citations.

## Objective

Create an answer generation service that:
1. Generates answers using retrieved context
2. Includes citations to source documents
3. Handles different query types (factual, summary, comparison)
4. Validates answer quality and relevance
5. Provides confidence scoring

## Requirements

### 1. Create `/services/query-service/src/aswa_query/generation/__init__.py`
```python
from .generator import AnswerGenerator, GeneratedAnswer
from .prompts import PromptBuilder, SystemPrompts
from .citations import CitationExtractor, Citation
from .validator import AnswerValidator, ValidationResult

__all__ = [
    "AnswerGenerator",
    "GeneratedAnswer",
    "PromptBuilder",
    "SystemPrompts",
    "CitationExtractor",
    "Citation",
    "AnswerValidator",
    "ValidationResult",
]
```

### 2. Create `/services/query-service/src/aswa_query/generation/models.py`
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class Citation:
    """A citation to a source."""
    index: int
    document_id: UUID | None
    document_name: str
    page_number: int | None = None
    excerpt: str = ""
    relevance_score: float = 0.0

    def format(self) -> str:
        ref = f"[{self.index}]"
        if self.page_number:
            return f"{ref} {self.document_name}, p.{self.page_number}"
        return f"{ref} {self.document_name}"


@dataclass
class GeneratedAnswer:
    """A generated answer with citations."""
    id: UUID = field(default_factory=uuid4)
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    query: str = ""
    reasoning: str | None = None
    generation_time_ms: int = 0
    token_count: int = 0
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_citations(self) -> bool:
        return len(self.citations) > 0

    def format_with_citations(self) -> str:
        """Format answer with citation references."""
        result = self.answer
        if self.citations:
            result += "\n\nSources:\n"
            for citation in self.citations:
                result += f"  {citation.format()}\n"
        return result


@dataclass
class ValidationResult:
    """Result of answer validation."""
    is_valid: bool
    confidence: float
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
```

### 3. Create `/services/query-service/src/aswa_query/generation/prompts.py`
```python
from typing import Any

from aswa_query.parser.models import QueryIntent
from aswa_query.retrieval.models import ContextWindow


class SystemPrompts:
    """System prompts for different generation tasks."""

    BASE = """You are an AI assistant analyzing business documents and providing accurate, helpful answers.

Your responses should:
- Be factual and based only on the provided context
- Include specific citations using [1], [2], etc. format
- Acknowledge when information is incomplete or uncertain
- Be concise but comprehensive

If you cannot answer based on the context, say so clearly."""

    FACTUAL = """Answer the question directly and concisely based on the provided context.
Use specific citations [1], [2], etc. to reference sources.
If the answer isn't in the context, state that clearly."""

    SUMMARY = """Provide a comprehensive summary of the key points from the context.
Organize the summary logically with clear sections if appropriate.
Cite sources for each major point using [1], [2], etc."""

    COMPARISON = """Compare and contrast the items mentioned in the question.
Structure your response with clear categories of comparison.
Use citations to support each comparison point."""

    RISK = """Identify and explain the risks based on the provided context.
For each risk:
- Describe what the risk is
- Explain potential impact
- Note any mentioned mitigations
Use citations [1], [2], etc. for each risk identified."""

    OPPORTUNITY = """Identify opportunities and potential benefits from the context.
For each opportunity:
- Describe the opportunity
- Explain potential value
- Note any requirements or considerations
Use citations [1], [2], etc. for each opportunity."""

    TREND = """Analyze trends and patterns from the provided context.
Describe:
- What trends are visible
- Direction of change
- Potential implications
Support your analysis with specific citations."""

    @classmethod
    def get_for_intent(cls, intent: QueryIntent) -> str:
        """Get system prompt for query intent."""
        intent_prompts = {
            QueryIntent.FACTUAL: cls.FACTUAL,
            QueryIntent.SUMMARY: cls.SUMMARY,
            QueryIntent.COMPARISON: cls.COMPARISON,
            QueryIntent.RISK: cls.RISK,
            QueryIntent.OPPORTUNITY: cls.OPPORTUNITY,
            QueryIntent.TREND: cls.TREND,
        }
        return intent_prompts.get(intent, cls.FACTUAL)


class PromptBuilder:
    """Build prompts for answer generation."""

    def __init__(self):
        self.system_prompts = SystemPrompts()

    def build_prompt(
        self,
        query: str,
        context: ContextWindow,
        intent: QueryIntent,
        additional_instructions: str | None = None,
    ) -> list[dict[str, str]]:
        """Build complete prompt for LLM.

        Args:
            query: User query
            context: Retrieved context
            intent: Query intent
            additional_instructions: Optional extra instructions

        Returns:
            List of message dicts for LLM
        """
        # Build system prompt
        system = SystemPrompts.BASE + "\n\n" + SystemPrompts.get_for_intent(intent)

        if additional_instructions:
            system += f"\n\nAdditional instructions: {additional_instructions}"

        # Build user prompt with context
        user_content = f"""## Context
{context.content}

## Question
{query}

Please provide a comprehensive answer based on the context above. Include citations using [1], [2], etc. to reference the sources."""

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

    def build_followup_prompt(
        self,
        original_query: str,
        original_answer: str,
        followup_query: str,
        context: ContextWindow,
    ) -> list[dict[str, str]]:
        """Build prompt for follow-up questions."""
        system = SystemPrompts.BASE

        user_content = f"""## Previous Question
{original_query}

## Previous Answer
{original_answer}

## Additional Context
{context.content}

## Follow-up Question
{followup_query}

Please answer the follow-up question, building on the previous answer where relevant. Include citations."""

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

    def build_validation_prompt(
        self,
        query: str,
        answer: str,
        context: ContextWindow,
    ) -> list[dict[str, str]]:
        """Build prompt for answer validation."""
        system = """You are a quality assurance assistant. Evaluate whether the answer is:
1. Accurate based on the context
2. Complete (addresses all parts of the question)
3. Properly cited
4. Free from hallucinations

Respond with a JSON object containing:
{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "issues": ["list of issues if any"],
    "suggestions": ["list of improvement suggestions"]
}"""

        user_content = f"""## Context
{context.content}

## Question
{query}

## Answer to Validate
{answer}

Evaluate this answer."""

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
```

### 4. Create `/services/query-service/src/aswa_query/generation/citations.py`
```python
import re
from typing import Any
from uuid import UUID
import structlog

from aswa_query.retrieval.models import SearchResult, InsightResult
from .models import Citation

logger = structlog.get_logger()


class CitationExtractor:
    """Extract and manage citations in generated answers."""

    def __init__(self):
        self._citation_pattern = re.compile(r'\[(\d+)\]')

    def build_citation_map(
        self,
        chunks: list[SearchResult],
        insights: list[InsightResult],
    ) -> dict[int, Citation]:
        """Build a map of citation indices to sources.

        Args:
            chunks: Document chunks
            insights: Insights

        Returns:
            Dict mapping index to Citation
        """
        citation_map = {}
        index = 1

        # Add chunk citations
        for chunk in chunks:
            citation_map[index] = Citation(
                index=index,
                document_id=chunk.document_id,
                document_name=chunk.document_name or f"Document {chunk.document_id}",
                page_number=chunk.page_number,
                excerpt=chunk.content[:200] if chunk.content else "",
                relevance_score=chunk.score,
            )
            index += 1

        # Add insight citations
        for insight in insights:
            citation_map[index] = Citation(
                index=index,
                document_id=insight.document_id,
                document_name=insight.document_name or f"Insight: {insight.title[:50]}",
                excerpt=insight.description[:200] if insight.description else "",
                relevance_score=insight.score,
            )
            index += 1

        return citation_map

    def extract_used_citations(
        self,
        answer: str,
        citation_map: dict[int, Citation],
    ) -> list[Citation]:
        """Extract citations actually used in the answer.

        Args:
            answer: Generated answer text
            citation_map: Available citations

        Returns:
            List of citations used in answer
        """
        matches = self._citation_pattern.findall(answer)
        used_indices = set(int(m) for m in matches)

        used_citations = []
        for index in sorted(used_indices):
            if index in citation_map:
                used_citations.append(citation_map[index])

        return used_citations

    def renumber_citations(
        self,
        answer: str,
        used_citations: list[Citation],
    ) -> tuple[str, list[Citation]]:
        """Renumber citations sequentially starting from 1.

        Args:
            answer: Answer with citations
            used_citations: Citations used in answer

        Returns:
            Tuple of (updated_answer, renumbered_citations)
        """
        if not used_citations:
            return answer, []

        # Build old->new index mapping
        old_to_new = {}
        renumbered = []

        for new_index, citation in enumerate(used_citations, 1):
            old_to_new[citation.index] = new_index
            new_citation = Citation(
                index=new_index,
                document_id=citation.document_id,
                document_name=citation.document_name,
                page_number=citation.page_number,
                excerpt=citation.excerpt,
                relevance_score=citation.relevance_score,
            )
            renumbered.append(new_citation)

        # Replace old indices with new
        def replace_citation(match):
            old_index = int(match.group(1))
            new_index = old_to_new.get(old_index, old_index)
            return f"[{new_index}]"

        updated_answer = self._citation_pattern.sub(replace_citation, answer)

        return updated_answer, renumbered

    def add_missing_citations(
        self,
        answer: str,
        citation_map: dict[int, Citation],
        threshold: float = 0.8,
    ) -> str:
        """Add citations where text matches source but isn't cited.

        Args:
            answer: Answer text
            citation_map: Available citations
            threshold: Text match threshold

        Returns:
            Answer with added citations
        """
        # Simple implementation: find sentences that match sources
        sentences = answer.split('. ')
        updated_sentences = []

        for sentence in sentences:
            # Check if sentence already has citation
            if self._citation_pattern.search(sentence):
                updated_sentences.append(sentence)
                continue

            # Try to find matching source
            best_match_index = None
            best_match_score = 0

            for index, citation in citation_map.items():
                if not citation.excerpt:
                    continue

                # Simple word overlap check
                sentence_words = set(sentence.lower().split())
                source_words = set(citation.excerpt.lower().split())

                if not sentence_words:
                    continue

                overlap = len(sentence_words & source_words) / len(sentence_words)
                if overlap > best_match_score and overlap >= threshold:
                    best_match_score = overlap
                    best_match_index = index

            if best_match_index:
                sentence = f"{sentence} [{best_match_index}]"

            updated_sentences.append(sentence)

        return '. '.join(updated_sentences)

    def format_citations_section(
        self,
        citations: list[Citation],
    ) -> str:
        """Format citations as a reference section.

        Args:
            citations: List of citations

        Returns:
            Formatted citation section
        """
        if not citations:
            return ""

        lines = ["\n\n---\n**Sources:**"]
        for citation in citations:
            line = f"\n[{citation.index}] {citation.document_name}"
            if citation.page_number:
                line += f", page {citation.page_number}"
            lines.append(line)

        return "".join(lines)
```

### 5. Create `/services/query-service/src/aswa_query/generation/validator.py`
```python
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
```

### 6. Create `/services/query-service/src/aswa_query/generation/generator.py`
```python
import time
from typing import Any
from uuid import UUID
import structlog

from aswa_query.config import Settings
from aswa_query.parser.models import ParsedQuery, QueryIntent
from aswa_query.retrieval.models import RetrievalResult, ContextWindow
from .models import GeneratedAnswer, Citation
from .prompts import PromptBuilder
from .citations import CitationExtractor
from .validator import AnswerValidator

logger = structlog.get_logger()


class AnswerGenerator:
    """Generate answers using LLM with citations."""

    def __init__(
        self,
        settings: Settings,
        llm_client: Any,
        prompt_builder: PromptBuilder | None = None,
        citation_extractor: CitationExtractor | None = None,
        validator: AnswerValidator | None = None,
    ):
        self.settings = settings
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.citation_extractor = citation_extractor or CitationExtractor()
        self.validator = validator or AnswerValidator()

    async def generate(
        self,
        query: ParsedQuery,
        retrieval_result: RetrievalResult,
        context: ContextWindow,
        validate: bool = True,
    ) -> GeneratedAnswer:
        """Generate an answer with citations.

        Args:
            query: Parsed query
            retrieval_result: Retrieved content
            context: Built context window
            validate: Whether to validate answer

        Returns:
            GeneratedAnswer
        """
        start_time = time.time()

        # Build citation map
        citation_map = self.citation_extractor.build_citation_map(
            retrieval_result.document_chunks,
            retrieval_result.insights,
        )

        # Build prompt
        messages = self.prompt_builder.build_prompt(
            query=query.original_query,
            context=context,
            intent=query.intent,
        )

        # Generate answer
        try:
            raw_answer = await self.llm_client.complete(
                messages=messages,
                max_tokens=self.settings.llm_max_tokens,
                temperature=self.settings.llm_temperature,
            )
        except Exception as e:
            logger.error("LLM generation failed", error=str(e))
            return GeneratedAnswer(
                answer="I apologize, but I was unable to generate an answer. Please try again.",
                query=query.original_query,
                confidence=0.0,
            )

        # Extract and process citations
        used_citations = self.citation_extractor.extract_used_citations(
            raw_answer, citation_map
        )

        # Renumber citations
        processed_answer, renumbered_citations = self.citation_extractor.renumber_citations(
            raw_answer, used_citations
        )

        generation_time = int((time.time() - start_time) * 1000)

        answer = GeneratedAnswer(
            answer=processed_answer,
            citations=renumbered_citations,
            query=query.original_query,
            generation_time_ms=generation_time,
            model=self.settings.llm_model,
            metadata={
                "intent": query.intent.value,
                "context_tokens": context.token_count,
                "source_count": len(context.sources),
            },
        )

        # Validate if requested
        if validate:
            validation = self.validator.validate_basic(answer, context)
            answer.confidence = validation.confidence

            if not validation.is_valid:
                logger.warning(
                    "Answer validation issues",
                    issues=validation.issues,
                )

        logger.info(
            "Answer generated",
            query=query.original_query[:50],
            citations=len(renumbered_citations),
            time_ms=generation_time,
            confidence=answer.confidence,
        )

        return answer

    async def generate_summary(
        self,
        retrieval_result: RetrievalResult,
        context: ContextWindow,
        max_length: int = 500,
    ) -> GeneratedAnswer:
        """Generate a summary of retrieved content.

        Args:
            retrieval_result: Retrieved content
            context: Context window
            max_length: Maximum summary length

        Returns:
            GeneratedAnswer with summary
        """
        query = ParsedQuery(
            original_query="Summarize the key points",
            normalized_query="summarize key points",
            intent=QueryIntent.SUMMARY,
            confidence=1.0,
        )

        return await self.generate(query, retrieval_result, context)

    async def generate_followup(
        self,
        original_answer: GeneratedAnswer,
        followup_query: str,
        retrieval_result: RetrievalResult,
        context: ContextWindow,
    ) -> GeneratedAnswer:
        """Generate answer to a follow-up question.

        Args:
            original_answer: Previous answer
            followup_query: Follow-up question
            retrieval_result: New retrieval results
            context: New context window

        Returns:
            GeneratedAnswer for follow-up
        """
        messages = self.prompt_builder.build_followup_prompt(
            original_query=original_answer.query,
            original_answer=original_answer.answer,
            followup_query=followup_query,
            context=context,
        )

        citation_map = self.citation_extractor.build_citation_map(
            retrieval_result.document_chunks,
            retrieval_result.insights,
        )

        raw_answer = await self.llm_client.complete(
            messages=messages,
            max_tokens=self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature,
        )

        used_citations = self.citation_extractor.extract_used_citations(
            raw_answer, citation_map
        )
        processed_answer, renumbered_citations = self.citation_extractor.renumber_citations(
            raw_answer, used_citations
        )

        return GeneratedAnswer(
            answer=processed_answer,
            citations=renumbered_citations,
            query=followup_query,
            model=self.settings.llm_model,
            metadata={"followup_to": str(original_answer.id)},
        )

    async def regenerate_with_feedback(
        self,
        original_answer: GeneratedAnswer,
        feedback: str,
        context: ContextWindow,
    ) -> GeneratedAnswer:
        """Regenerate answer incorporating user feedback.

        Args:
            original_answer: Original answer
            feedback: User feedback
            context: Context window

        Returns:
            Improved GeneratedAnswer
        """
        messages = [
            {"role": "system", "content": "Improve the answer based on user feedback."},
            {"role": "user", "content": f"""## Original Answer
{original_answer.answer}

## User Feedback
{feedback}

## Context
{context.content}

Please provide an improved answer addressing the feedback. Include citations [1], [2], etc."""},
        ]

        raw_answer = await self.llm_client.complete(
            messages=messages,
            max_tokens=self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature,
        )

        return GeneratedAnswer(
            answer=raw_answer,
            query=original_answer.query,
            model=self.settings.llm_model,
            metadata={
                "regenerated_from": str(original_answer.id),
                "feedback": feedback,
            },
        )
```

## Test Requirements

### Create `/services/query-service/tests/generation/__init__.py`

### Create `/services/query-service/tests/generation/test_citations.py`
```python
import pytest
from uuid import uuid4

from aswa_query.generation.citations import CitationExtractor, Citation
from aswa_query.retrieval.models import SearchResult, InsightResult, ContentType


class TestCitationExtractor:
    @pytest.fixture
    def extractor(self):
        return CitationExtractor()

    def test_build_citation_map(self, extractor):
        """Test building citation map."""
        chunks = [
            SearchResult(id="1", content="Content 1", content_type=ContentType.DOCUMENT_CHUNK, score=0.9, document_id=uuid4(), document_name="Doc1.pdf"),
            SearchResult(id="2", content="Content 2", content_type=ContentType.DOCUMENT_CHUNK, score=0.8, document_id=uuid4(), document_name="Doc2.pdf"),
        ]
        insights = [
            InsightResult(id=uuid4(), title="Insight", description="Description", insight_type="risk", confidence=0.8, score=0.85),
        ]

        citation_map = extractor.build_citation_map(chunks, insights)

        assert len(citation_map) == 3
        assert 1 in citation_map
        assert 2 in citation_map
        assert 3 in citation_map

    def test_extract_used_citations(self, extractor):
        """Test extracting used citations."""
        citation_map = {
            1: Citation(index=1, document_id=uuid4(), document_name="Doc1"),
            2: Citation(index=2, document_id=uuid4(), document_name="Doc2"),
            3: Citation(index=3, document_id=uuid4(), document_name="Doc3"),
        }

        answer = "This is from the first source [1]. This is from the third [3]."

        used = extractor.extract_used_citations(answer, citation_map)

        assert len(used) == 2
        assert used[0].index == 1
        assert used[1].index == 3

    def test_renumber_citations(self, extractor):
        """Test citation renumbering."""
        citations = [
            Citation(index=3, document_id=uuid4(), document_name="Doc3"),
            Citation(index=7, document_id=uuid4(), document_name="Doc7"),
        ]

        answer = "Source [3] says this. Source [7] says that."

        updated_answer, renumbered = extractor.renumber_citations(answer, citations)

        assert "[1]" in updated_answer
        assert "[2]" in updated_answer
        assert "[3]" not in updated_answer
        assert renumbered[0].index == 1
        assert renumbered[1].index == 2


class TestCitation:
    def test_format_with_page(self):
        """Test citation formatting with page number."""
        citation = Citation(
            index=1,
            document_id=uuid4(),
            document_name="Report.pdf",
            page_number=42,
        )

        formatted = citation.format()
        assert "[1]" in formatted
        assert "Report.pdf" in formatted
        assert "p.42" in formatted

    def test_format_without_page(self):
        """Test citation formatting without page."""
        citation = Citation(
            index=2,
            document_id=uuid4(),
            document_name="Doc.pdf",
        )

        formatted = citation.format()
        assert "[2]" in formatted
        assert "Doc.pdf" in formatted
```

### Create `/services/query-service/tests/generation/test_generator.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_query.generation.generator import AnswerGenerator
from aswa_query.generation.models import GeneratedAnswer
from aswa_query.retrieval.models import RetrievalResult, SearchResult, ContextWindow, ContentType
from aswa_query.parser.models import ParsedQuery, QueryIntent
from aswa_query.config import Settings


class TestAnswerGenerator:
    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.complete = AsyncMock(return_value="This is the answer based on the context [1]. More info [2].")
        return llm

    @pytest.fixture
    def generator(self, settings, mock_llm):
        return AnswerGenerator(settings, mock_llm)

    @pytest.mark.asyncio
    async def test_generate_answer(self, generator, mock_llm):
        """Test basic answer generation."""
        query = ParsedQuery(
            original_query="What are the risks?",
            normalized_query="what are the risks",
            intent=QueryIntent.RISK,
            confidence=0.9,
        )

        retrieval_result = RetrievalResult(
            query="test",
            document_chunks=[
                SearchResult(id="1", content="Risk content", content_type=ContentType.DOCUMENT_CHUNK, score=0.9, document_id=uuid4(), document_name="Doc1.pdf"),
            ],
        )

        context = ContextWindow(
            content="Test context",
            token_count=100,
            sources=["Doc1.pdf"],
        )

        answer = await generator.generate(query, retrieval_result, context)

        assert isinstance(answer, GeneratedAnswer)
        assert len(answer.answer) > 0
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_includes_citations(self, generator):
        """Test that generated answer includes citations."""
        query = ParsedQuery(
            original_query="Test query",
            normalized_query="test query",
            intent=QueryIntent.FACTUAL,
            confidence=0.8,
        )

        retrieval_result = RetrievalResult(
            query="test",
            document_chunks=[
                SearchResult(id="1", content="Content", content_type=ContentType.DOCUMENT_CHUNK, score=0.9, document_id=uuid4(), document_name="Doc.pdf"),
            ],
        )

        context = ContextWindow(content="Context", token_count=50, sources=["Doc.pdf"])

        answer = await generator.generate(query, retrieval_result, context)

        assert answer.has_citations or "[" in answer.answer
```

### Create `/services/query-service/tests/generation/test_validator.py`
```python
import pytest
from uuid import uuid4

from aswa_query.generation.validator import AnswerValidator
from aswa_query.generation.models import GeneratedAnswer
from aswa_query.retrieval.models import ContextWindow


class TestAnswerValidator:
    @pytest.fixture
    def validator(self):
        return AnswerValidator()

    def test_validate_basic_empty_answer(self, validator):
        """Test validation of empty answer."""
        answer = GeneratedAnswer(answer="", query="test")
        context = ContextWindow(content="Some context", token_count=10, sources=[])

        result = validator.validate_basic(answer, context)

        assert not result.is_valid
        assert "too short" in result.issues[0].lower()

    def test_validate_basic_no_citations(self, validator):
        """Test validation when citations missing."""
        answer = GeneratedAnswer(
            answer="This is a detailed answer without any citations.",
            query="test",
        )
        context = ContextWindow(
            content="Source content",
            token_count=50,
            sources=["Doc1.pdf", "Doc2.pdf"],
        )

        result = validator.validate_basic(answer, context)

        assert "citations" in str(result.issues).lower()

    def test_validate_citations_valid(self, validator):
        """Test validation with valid citations."""
        answer = GeneratedAnswer(
            answer="This is correct [1]. This is also correct [2].",
            query="test",
        )

        result = validator.validate_citations(answer, max_citation_index=3)

        assert result.is_valid

    def test_validate_citations_invalid_index(self, validator):
        """Test validation with invalid citation index."""
        answer = GeneratedAnswer(
            answer="This references [10] which doesn't exist.",
            query="test",
        )

        result = validator.validate_citations(answer, max_citation_index=3)

        assert not result.is_valid
        assert any("invalid" in issue.lower() for issue in result.issues)
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/generation/ -v`
2. Verify imports: `python -c "from aswa_query.generation import AnswerGenerator"`
3. Test generation with mock LLM
