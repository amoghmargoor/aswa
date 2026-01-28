# Task 3.2.2: Prompt Templates for Each Extraction Type

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The Pydantic extraction models have been created in `/services/insight-engine/src/aswa_insight/models/` (from Task 3.2.1).

The LLM client is at `/services/insight-engine/src/aswa_insight/llm/client.py` with the `complete_structured()` method that uses the instructor library for structured extraction.

## Objective

Create well-engineered prompt templates for each extraction type (entities, risks, opportunities, patterns). These prompts should:
1. Produce high-quality, consistent extractions
2. Be optimized for the instructor library
3. Include few-shot examples where beneficial
4. Handle edge cases gracefully

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/prompts/__init__.py`
Export all prompt templates and the prompt manager.

### 2. Create `/services/insight-engine/src/aswa_insight/prompts/base.py`
Base prompt template infrastructure:

```python
from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class PromptTemplate(ABC):
    """Base class for extraction prompt templates."""

    # Template name for logging/metrics
    name: str

    # The response model for instructor
    response_model: Type[BaseModel]

    # Maximum tokens for this extraction type
    max_tokens: int = 4096

    # Temperature for extraction (0 = deterministic)
    temperature: float = 0.0

    @abstractmethod
    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Get the system prompt for this extraction type."""
        ...

    @abstractmethod
    def get_user_prompt(self, text: str, context: dict[str, Any] | None = None) -> str:
        """Get the user prompt with the text to analyze."""
        ...

    def get_messages(self, text: str, context: dict[str, Any] | None = None) -> list[dict]:
        """Build the messages list for the LLM."""
        return [
            {"role": "system", "content": self.get_system_prompt(context)},
            {"role": "user", "content": self.get_user_prompt(text, context)},
        ]

    def truncate_text(self, text: str, max_chars: int = 100000) -> str:
        """Truncate text if too long, preserving structure."""
        if len(text) <= max_chars:
            return text

        # Truncate with indicator
        truncated = text[:max_chars]
        last_period = truncated.rfind('.')
        if last_period > max_chars * 0.8:
            truncated = truncated[:last_period + 1]

        return truncated + "\n\n[Text truncated due to length...]"


class PromptManager:
    """Manager for accessing and using prompt templates."""

    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template."""
        self._templates[template.name] = template

    def get(self, name: str) -> PromptTemplate:
        """Get a template by name."""
        if name not in self._templates:
            raise ValueError(f"Unknown prompt template: {name}")
        return self._templates[name]

    def list_templates(self) -> list[str]:
        """List all registered templates."""
        return list(self._templates.keys())


# Global prompt manager instance
prompt_manager = PromptManager()
```

### 3. Create `/services/insight-engine/src/aswa_insight/prompts/entity_prompts.py`
Entity extraction prompts:

```python
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
```

### 4. Create `/services/insight-engine/src/aswa_insight/prompts/risk_prompts.py`
Risk extraction prompts with severity/likelihood guidance:

```python
from aswa_insight.models.risks import RiskExtractionResult
from .base import PromptTemplate, prompt_manager


class RiskExtractionPrompt(PromptTemplate):
    """Prompt template for risk extraction."""

    name = "risk_extraction"
    response_model = RiskExtractionResult
    max_tokens = 8192

    SYSTEM_PROMPT = '''You are an expert risk analyst. Your task is to identify and assess all significant risks mentioned or implied in the provided text.

## Risk Categories
- FINANCIAL: Revenue, cost, cash flow, investment risks
- OPERATIONAL: Process, supply chain, execution risks
- STRATEGIC: Market position, competition, business model risks
- COMPLIANCE: Regulatory, legal, policy compliance risks
- SECURITY: Cybersecurity, physical security, data protection risks
- REPUTATIONAL: Brand, public perception, stakeholder trust risks
- MARKET: Market conditions, demand, pricing risks
- TECHNOLOGY: Technical debt, obsolescence, integration risks
- LEGAL: Litigation, contractual, IP risks
- ENVIRONMENTAL: Climate, sustainability, environmental impact risks

## Severity Assessment
- CRITICAL: Existential threat, potential business failure
- HIGH: Significant impact on major objectives or financials
- MEDIUM: Notable impact on operations or performance
- LOW: Minor impact, easily manageable
- INFORMATIONAL: Awareness item, minimal direct impact

## Likelihood Assessment
- ALMOST_CERTAIN: >90% probability, expected to occur
- LIKELY: 60-90% probability, more likely than not
- POSSIBLE: 30-60% probability, could occur
- UNLIKELY: 10-30% probability, not expected but possible
- RARE: <10% probability, exceptional circumstances only

## Time Horizon
- IMMEDIATE: < 1 month
- SHORT_TERM: 1-6 months
- MEDIUM_TERM: 6-18 months
- LONG_TERM: > 18 months

## Guidelines
1. Extract both explicit risks and those implied by the context
2. Provide specific, actionable descriptions
3. Base severity/likelihood on evidence in the text
4. Include the potential impact and affected areas
5. Suggest mitigation strategies when possible
6. Link risks to related entities mentioned in the text
7. Confidence should reflect how clearly the risk is articulated:
   - 0.9-1.0: Explicitly stated risk with clear details
   - 0.7-0.9: Clearly implied or industry-standard risk
   - 0.5-0.7: Inferred from context
   - Below 0.5: Speculative or weakly supported'''

    USER_PROMPT_TEMPLATE = '''Analyze the following text and extract all significant risks.

{context_section}

## Text to Analyze
```
{text}
```

For each risk, provide:
- A clear, specific title
- Detailed description of the risk
- Category, severity, and likelihood assessment
- Time horizon for risk materialization
- Potential impact and affected areas
- Related entities
- Suggested mitigations (if applicable)
- Confidence score based on evidence clarity'''

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
            if context.get("risk_focus"):
                context_section += f"Focus areas: {', '.join(context['risk_focus'])}\n"

        if context_section:
            context_section = f"## Context\n{context_section}"

        return self.USER_PROMPT_TEMPLATE.format(
            text=self.truncate_text(text),
            context_section=context_section
        )


# Register the template
prompt_manager.register(RiskExtractionPrompt())
```

### 5. Create `/services/insight-engine/src/aswa_insight/prompts/opportunity_prompts.py`
Opportunity extraction prompts:

```python
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
```

### 6. Create `/services/insight-engine/src/aswa_insight/prompts/pattern_prompts.py`
Pattern extraction prompts:

```python
from aswa_insight.models.patterns import PatternExtractionResult
from .base import PromptTemplate, prompt_manager


class PatternExtractionPrompt(PromptTemplate):
    """Prompt template for pattern extraction."""

    name = "pattern_extraction"
    response_model = PatternExtractionResult
    max_tokens = 8192

    SYSTEM_PROMPT = '''You are a data analyst specializing in pattern recognition. Your task is to identify significant patterns, trends, and anomalies from the provided text.

## Pattern Types
- TREND: Directional movement over time (growth, decline, etc.)
- CORRELATION: Relationships between variables
- ANOMALY: Unusual or unexpected observations
- CYCLE: Recurring patterns (seasonal, periodic)
- THRESHOLD: Crossing of significant levels
- COMPARISON: Relative differences between groups
- DISTRIBUTION: How values are spread
- SEQUENCE: Order-dependent patterns

## Trend Directions
- INCREASING: Upward trend
- DECREASING: Downward trend
- STABLE: Flat or minimal change
- VOLATILE: High variability
- CYCLICAL: Recurring up/down pattern

## Frequency
- DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY
- IRREGULAR: Non-standard frequency
- ONE_TIME: Single occurrence

## Guidelines
1. Look for quantitative and qualitative patterns
2. Identify trends with supporting data points
3. Note correlations and potential causations
4. Flag anomalies and their significance
5. Extract specific metrics and percentages
6. Consider the time period covered
7. Assess statistical significance when possible
8. Explain implications for decision-making
9. Confidence reflects data quality:
   - 0.9-1.0: Clear pattern with multiple data points
   - 0.7-0.9: Pattern with some supporting evidence
   - 0.5-0.7: Pattern inferred from limited data
   - Below 0.5: Potential pattern, needs verification'''

    USER_PROMPT_TEMPLATE = '''Analyze the following text and extract significant patterns, trends, and insights.

{context_section}

## Text to Analyze
```
{text}
```

For each pattern, provide:
- Clear, descriptive title
- Detailed description of the pattern
- Pattern type and direction (if applicable)
- Frequency (if recurring)
- Magnitude or scale
- Time period covered
- Relevant data points
- Related entities
- Implications and significance
- Statistical significance (if determinable)
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
            if context.get("time_period"):
                context_section += f"Time period: {context['time_period']}\n"
            if context.get("metrics_focus"):
                context_section += f"Focus metrics: {', '.join(context['metrics_focus'])}\n"

        if context_section:
            context_section = f"## Context\n{context_section}"

        return self.USER_PROMPT_TEMPLATE.format(
            text=self.truncate_text(text),
            context_section=context_section
        )


# Register the template
prompt_manager.register(PatternExtractionPrompt())
```

### 7. Create `/services/insight-engine/src/aswa_insight/prompts/combined_prompts.py`
A combined extraction prompt for efficiency:

```python
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
```

## Test Requirements

### Create `/services/insight-engine/tests/prompts/__init__.py`

### Create `/services/insight-engine/tests/prompts/test_base.py`
```python
class TestPromptTemplate:
    def test_truncate_text_short(self):
        """Test truncation on short text."""

    def test_truncate_text_long(self):
        """Test truncation on long text."""

    def test_truncate_preserves_sentence(self):
        """Test truncation at sentence boundary."""

    def test_get_messages_structure(self):
        """Test messages list structure."""

class TestPromptManager:
    def test_register_template(self):
        """Test registering a template."""

    def test_get_registered_template(self):
        """Test getting registered template."""

    def test_get_unknown_template(self):
        """Test error on unknown template."""

    def test_list_templates(self):
        """Test listing templates."""
```

### Create `/services/insight-engine/tests/prompts/test_entity_prompts.py`
```python
class TestEntityExtractionPrompt:
    def test_system_prompt_content(self):
        """Test system prompt includes required guidance."""

    def test_user_prompt_includes_text(self):
        """Test user prompt includes the text."""

    def test_user_prompt_with_context(self):
        """Test context is included in prompt."""

    def test_response_model_is_correct(self):
        """Test response model is EntityExtractionResult."""

    def test_prompt_registered(self):
        """Test prompt is registered in manager."""
```

### Create similar test files for other prompts:
- `/services/insight-engine/tests/prompts/test_risk_prompts.py`
- `/services/insight-engine/tests/prompts/test_opportunity_prompts.py`
- `/services/insight-engine/tests/prompts/test_pattern_prompts.py`
- `/services/insight-engine/tests/prompts/test_combined_prompts.py`

### Create `/services/insight-engine/tests/prompts/test_integration.py`
Integration tests with mock LLM:
```python
class TestPromptIntegration:
    @pytest.mark.asyncio
    async def test_entity_extraction_with_mock_llm(self, mock_llm_client):
        """Test entity prompt produces valid extraction."""

    @pytest.mark.asyncio
    async def test_risk_extraction_with_mock_llm(self, mock_llm_client):
        """Test risk prompt produces valid extraction."""

    @pytest.mark.asyncio
    async def test_combined_extraction_with_mock_llm(self, mock_llm_client):
        """Test combined prompt produces valid extraction."""
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/prompts/ -v`
2. Verify imports: `python -c "from aswa_insight.prompts import prompt_manager; print(prompt_manager.list_templates())"`
3. Check prompt quality by reviewing generated prompts manually
