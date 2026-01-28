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
