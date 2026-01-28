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
