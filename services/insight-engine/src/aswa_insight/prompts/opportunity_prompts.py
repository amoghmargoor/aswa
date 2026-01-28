from aswa_insight.models.opportunities import OpportunityExtractionResult
from .base import PromptTemplate, prompt_manager


class OpportunityExtractionPrompt(PromptTemplate):
    """Prompt template for opportunity extraction."""

    name = "opportunity_extraction"
    response_model = OpportunityExtractionResult
    max_tokens = 8192

    SYSTEM_PROMPT = '''You are a strategic business analyst specializing in opportunity identification. Your task is to identify actionable opportunities from the provided text.

## Opportunity Categories
- GROWTH: Revenue growth, market share expansion
- COST_REDUCTION: Cost savings, efficiency gains
- EFFICIENCY: Process improvement, automation
- INNOVATION: New products, services, or approaches
- MARKET_EXPANSION: New markets, segments, geographies
- PARTNERSHIP: Strategic alliances, joint ventures
- ACQUISITION: M&A targets, talent acquisition
- PRODUCT: Product enhancement, new features
- TALENT: Skills development, team building
- TECHNOLOGY: Technology adoption, digital transformation

## Impact Assessment
- TRANSFORMATIONAL: Game-changing, strategic shift
- HIGH: Significant positive impact on objectives
- MEDIUM: Notable improvement in specific areas
- LOW: Incremental improvement

## Effort Assessment
- MINIMAL: Quick wins, little investment needed
- LOW: Limited resources, short timeline
- MEDIUM: Moderate resources, several months
- HIGH: Significant investment, 6-12 months
- VERY_HIGH: Major initiative, multi-year effort

## Guidelines
1. Focus on actionable, specific opportunities
2. Look for both explicit mentions and implied opportunities
3. Consider competitive advantages and market trends
4. Assess realistic impact and effort levels
5. Identify prerequisites and dependencies
6. Note any associated risks
7. Suggest concrete action items
8. Confidence reflects evidence strength:
   - 0.9-1.0: Explicitly stated opportunity with supporting data
   - 0.7-0.9: Clearly implied from context
   - 0.5-0.7: Reasonable inference from trends/patterns
   - Below 0.5: Speculative'''

    USER_PROMPT_TEMPLATE = '''Analyze the following text and extract actionable business opportunities.

{context_section}

## Text to Analyze
```
{text}
```

For each opportunity, provide:
- Clear, specific title
- Detailed description
- Category, impact, and effort assessment
- Time to value
- Prerequisites and dependencies
- Associated risks
- Concrete action items
- Related entities
- Confidence score'''

    def get_system_prompt(self, context: dict | None = None) -> str:
        return self.SYSTEM_PROMPT

    def get_user_prompt(self, text: str, context: dict | None = None) -> str:
        context_section = ""
        if context:
            if context.get("document_type"):
                context_section += f"Document type: {context['document_type']}\n"
            if context.get("industry"):
                context_section += f"Industry: {context['industry']}\n"
            if context.get("company"):
                context_section += f"Company: {context['company']}\n"
            if context.get("strategic_priorities"):
                context_section += f"Strategic priorities: {', '.join(context['strategic_priorities'])}\n"

        if context_section:
            context_section = f"## Context\n{context_section}"

        return self.USER_PROMPT_TEMPLATE.format(
            text=self.truncate_text(text),
            context_section=context_section
        )


# Register the template
prompt_manager.register(OpportunityExtractionPrompt())
