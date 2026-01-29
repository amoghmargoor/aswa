"""Intent extraction service using LLM."""

import json
import time
from typing import Any

import structlog
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from aswa_agents.config import get_settings
from aswa_agents.generation.models import (
    ExtractedEntity,
    ExtractedIntent,
    IntentExtractionResult,
    IntentType,
)
from aswa_agents.generation.prompts import (
    INTENT_EXTRACTION_SYSTEM_PROMPT,
    INTENT_EXTRACTION_USER_TEMPLATE,
    REFINEMENT_PROMPT_TEMPLATE,
)
from aswa_agents.utils.metrics import NLP_GENERATIONS_TOTAL, NLP_GENERATION_DURATION

logger = structlog.get_logger()


class IntentExtractionError(Exception):
    """Error during intent extraction."""
    pass


class IntentExtractor:
    """Extracts structured intents from natural language agent descriptions."""

    def __init__(self):
        self.settings = get_settings()
        self._logger = logger.bind(component="IntentExtractor")

        if self.settings.llm_provider == "anthropic":
            self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
            self._model = self.settings.default_model
        elif self.settings.llm_provider == "openai":
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
            self._model = "gpt-4-turbo-preview"
        else:
            raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def extract(
        self,
        user_input: str,
        previous_intents: IntentExtractionResult | None = None,
    ) -> IntentExtractionResult:
        """Extract intents from user input."""
        start_time = time.time()

        try:
            if previous_intents:
                prompt = REFINEMENT_PROMPT_TEMPLATE.format(
                    original_input=previous_intents.original_input,
                    previous_intents=json.dumps(
                        [i.model_dump() for i in previous_intents.all_intents],
                        default=str,
                    ),
                    new_input=user_input,
                )
            else:
                prompt = INTENT_EXTRACTION_USER_TEMPLATE.format(user_input=user_input)

            raw_response = await self._call_llm(prompt)
            result = self._parse_response(raw_response, user_input)

            processing_time = int((time.time() - start_time) * 1000)
            result.processing_time_ms = processing_time

            NLP_GENERATIONS_TOTAL.labels(tenant_id="system", status="success").inc()
            NLP_GENERATION_DURATION.observe(processing_time / 1000)

            self._logger.info(
                "Intent extraction completed",
                input_length=len(user_input),
                trigger_count=len(result.trigger_intents),
                action_count=len(result.action_intents),
                confidence=result.overall_confidence,
                processing_time_ms=processing_time,
            )

            return result

        except Exception as e:
            NLP_GENERATIONS_TOTAL.labels(tenant_id="system", status="error").inc()
            self._logger.error("Intent extraction failed", error=str(e), input_length=len(user_input))
            raise IntentExtractionError(f"Failed to extract intents: {e}") from e

    async def _call_llm(self, prompt: str) -> dict[str, Any]:
        """Call the LLM and get response."""
        if self.settings.llm_provider == "anthropic":
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=INTENT_EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
        else:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": INTENT_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content)
        except json.JSONDecodeError as e:
            self._logger.error("Failed to parse LLM response as JSON", content=content[:500])
            raise IntentExtractionError(f"Invalid JSON response: {e}")

    def _parse_response(self, raw_response: dict[str, Any], original_input: str) -> IntentExtractionResult:
        """Parse raw LLM response into structured result."""
        trigger_intents = [self._parse_intent(i) for i in raw_response.get("trigger_intents", []) if self._parse_intent(i)]
        action_intents = [self._parse_intent(i) for i in raw_response.get("action_intents", []) if self._parse_intent(i)]
        condition_intents = [self._parse_intent(i) for i in raw_response.get("condition_intents", []) if self._parse_intent(i)]

        all_questions = raw_response.get("clarification_questions", [])
        for intent in trigger_intents + action_intents + condition_intents:
            all_questions.extend(intent.clarification_questions)

        needs_clarification = raw_response.get("needs_clarification", False) or len(all_questions) > 0

        return IntentExtractionResult(
            original_input=original_input,
            normalized_input=raw_response.get("normalized_input", original_input),
            trigger_intents=trigger_intents,
            action_intents=action_intents,
            condition_intents=condition_intents,
            overall_confidence=raw_response.get("overall_confidence", 0.0),
            needs_clarification=needs_clarification,
            clarification_questions=list(set(all_questions)),
            raw_llm_response=raw_response,
        )

    def _parse_intent(self, intent_data: dict[str, Any]) -> ExtractedIntent | None:
        """Parse a single intent from raw data."""
        try:
            intent_type_str = intent_data.get("type", "unknown")
            try:
                intent_type = IntentType(intent_type_str)
            except ValueError:
                intent_type = IntentType.UNKNOWN

            entities = [
                ExtractedEntity(
                    type=e.get("type", "unknown"),
                    value=e.get("value", ""),
                    confidence=e.get("confidence", 0.5),
                )
                for e in intent_data.get("entities", [])
            ]

            return ExtractedIntent(
                type=intent_type,
                confidence=intent_data.get("confidence", 0.5),
                description=intent_data.get("description", ""),
                parameters=intent_data.get("parameters", {}),
                entities=entities,
                requires_clarification=intent_data.get("requires_clarification", False),
                clarification_questions=intent_data.get("clarification_questions", []),
                source_text=intent_data.get("source_text", ""),
            )
        except Exception as e:
            self._logger.warning("Failed to parse intent", error=str(e), data=intent_data)
            return None

    async def validate_intents(self, result: IntentExtractionResult) -> tuple[bool, list[str]]:
        """Validate extracted intents for completeness."""
        issues = []

        if not result.has_trigger:
            issues.append("No trigger identified. What should start this agent?")

        if not result.has_actions:
            issues.append("No actions identified. What should the agent do?")

        for intent in result.all_intents:
            if intent.confidence < 0.5:
                issues.append(f"Low confidence for {intent.type.value}: {intent.description}")

        for intent in result.trigger_intents:
            if intent.type == IntentType.TRIGGER_ON_SCHEDULE:
                if "schedule" not in intent.parameters:
                    issues.append("Schedule trigger needs a schedule (e.g., 'daily at 9am')")
            elif intent.type == IntentType.TRIGGER_ON_EMAIL:
                if "inbox" not in intent.parameters and not intent.entities:
                    issues.append("Email trigger: which inbox or email address?")

        return len(issues) == 0, issues
