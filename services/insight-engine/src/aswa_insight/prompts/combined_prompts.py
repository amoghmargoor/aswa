from pydantic import BaseModel, Field
from aswa_insight.models.entities import ExtractedEntity, EntityRelationship
from aswa_insight.models.risks import ExtractedRisk
from aswa_insight.models.opportunities import ExtractedOpportunity
from aswa_insight.models.patterns import ExtractedPattern
from .base import PromptTemplate, prompt_manager


class CombinedExtractionResult(BaseModel):
    """Combined result from multi-type extraction."""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[EntityRelationship] = Field(default_factory=list)
    risks: list[ExtractedRisk] = Field(default_factory=list)
    opportunities: list[ExtractedOpportunity] = Field(default_factory=list)
    patterns: list[ExtractedPattern] = Field(default_factory=list)
    summary: str = Field(..., description="Brief summary of key insights")


class CombinedExtractionPrompt(PromptTemplate):
    """Prompt for extracting all insight types in one pass."""

    name = "combined_extraction"
    response_model = CombinedExtractionResult
    max_tokens = 16384

    SYSTEM_PROMPT = '''You are an expert analyst performing comprehensive insight extraction. Extract all significant entities, risks, opportunities, and patterns from the provided text.

## What to Extract

### Entities
People, organizations, locations, products, technologies, events, dates, money, metrics, regulations.

### Risks
Financial, operational, strategic, compliance, security, reputational, market, technology, legal, environmental risks.

### Opportunities
Growth, cost reduction, efficiency, innovation, market expansion, partnership, acquisition, product, talent, technology opportunities.

### Patterns
Trends, correlations, anomalies, cycles, thresholds, comparisons, distributions, sequences.

## Guidelines
1. Be comprehensive but prioritize significant insights
2. Assign realistic confidence scores based on evidence
3. Link insights to related entities
4. Provide actionable descriptions
5. Include source references when possible'''

    USER_PROMPT_TEMPLATE = '''Perform a comprehensive analysis of the following text, extracting all significant insights.

{context_section}

## Text to Analyze
```
{text}
```

Extract:
1. All significant entities with their relationships
2. All identified risks with severity and likelihood
3. All actionable opportunities with impact assessment
4. All notable patterns and trends

End with a brief summary (2-3 sentences) of the key insights.'''

    def get_system_prompt(self, context: dict | None = None) -> str:
        return self.SYSTEM_PROMPT

    def get_user_prompt(self, text: str, context: dict | None = None) -> str:
        context_section = ""
        if context:
            parts = []
            for key, value in context.items():
                if value:
                    parts.append(f"{key}: {value}")
            if parts:
                context_section = "## Context\n" + "\n".join(parts)

        return self.USER_PROMPT_TEMPLATE.format(
            text=self.truncate_text(text),
            context_section=context_section
        )


# Register the template
prompt_manager.register(CombinedExtractionPrompt())
