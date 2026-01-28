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
