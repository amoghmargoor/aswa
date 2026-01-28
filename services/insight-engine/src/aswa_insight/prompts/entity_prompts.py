from aswa_insight.models.entities import EntityExtractionResult
from .base import PromptTemplate, prompt_manager


class EntityExtractionPrompt(PromptTemplate):
    """Prompt template for entity extraction."""

    name = "entity_extraction"
    response_model = EntityExtractionResult
    max_tokens = 8192

    SYSTEM_PROMPT = '''You are an expert entity extraction system. Your task is to identify and extract all significant entities from the provided text.

## Entity Types to Extract
- PERSON: Individuals mentioned by name or title
- ORGANIZATION: Companies, agencies, institutions, teams
- LOCATION: Places, regions, addresses, facilities
- PRODUCT: Products, services, offerings
- TECHNOLOGY: Technologies, platforms, tools, systems
- EVENT: Conferences, launches, incidents, milestones
- DATE: Specific dates, time periods, deadlines
- MONEY: Financial amounts, budgets, valuations
- PERCENTAGE: Percentages, rates, proportions
- REGULATION: Laws, regulations, standards, policies
- METRIC: KPIs, measurements, performance indicators
- OTHER: Other significant entities

## Guidelines
1. Extract entities that are substantively mentioned, not just passing references
2. Provide a brief, factual description based only on information in the text
3. Include alternative names/aliases when mentioned
4. Assign confidence based on clarity and context:
   - 0.9-1.0: Explicitly named and clearly identified
   - 0.7-0.9: Clearly referenced but some inference needed
   - 0.5-0.7: Implicitly mentioned or context-dependent
   - Below 0.5: Uncertain or ambiguous
5. Capture key attributes (e.g., role, size, industry for organizations)
6. Include source references with exact quoted text

## Relationship Extraction
Identify relationships between entities when they are explicitly or strongly implied:
- WORKS_FOR: Employment or contractor relationship
- OWNS: Ownership or controlling interest
- PARTNER_OF: Partnership or alliance
- COMPETITOR_OF: Competitive relationship
- LOCATED_IN: Physical or operational location
- PART_OF: Subsidiary or division relationship
- MANAGES: Management or oversight
- RELATED_TO: Other significant relationship

Only extract relationships with confidence >= 0.6.'''

    USER_PROMPT_TEMPLATE = '''Extract all significant entities and their relationships from the following text.

{context_section}

## Text to Analyze
```
{text}
```

Extract entities with their types, descriptions, aliases, and confidence scores. Also identify any relationships between the extracted entities.'''

    def get_system_prompt(self, context: dict | None = None) -> str:
        return self.SYSTEM_PROMPT

    def get_user_prompt(self, text: str, context: dict | None = None) -> str:
        context_section = ""
        if context:
            if context.get("document_type"):
                context_section += f"Document type: {context['document_type']}\n"
            if context.get("industry"):
                context_section += f"Industry context: {context['industry']}\n"
            if context.get("focus_entities"):
                context_section += f"Focus on these entity types: {', '.join(context['focus_entities'])}\n"

        if context_section:
            context_section = f"## Context\n{context_section}"

        return self.USER_PROMPT_TEMPLATE.format(
            text=self.truncate_text(text),
            context_section=context_section
        )


# Register the template
prompt_manager.register(EntityExtractionPrompt())
