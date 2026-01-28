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
