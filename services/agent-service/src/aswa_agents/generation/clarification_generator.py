"""Generates clarification questions from intents and matches."""

from typing import Any

import structlog

from aswa_agents.generation.capabilities import CapabilityMatchResult
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.clarification import (
    ClarificationOption,
    ClarificationQuestion,
    ClarificationResponse,
    ClarificationType,
)
from aswa_agents.generation.models import IntentExtractionResult, IntentType

logger = structlog.get_logger()


class ClarificationGenerator:
    """Generates structured clarification questions."""

    def __init__(self, tenant_connectors: list[str] | None = None):
        self.tenant_connectors = tenant_connectors or []
        self._logger = logger.bind(component="ClarificationGenerator")

    def generate_questions(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult | None = None,
    ) -> list[ClarificationQuestion]:
        """Generate clarification questions based on intents and matches."""
        questions = []

        if not intents.has_trigger:
            questions.append(self._generate_missing_trigger_question())

        if not intents.has_actions:
            questions.append(self._generate_missing_action_question())

        for intent in intents.all_intents:
            if intent.requires_clarification:
                for q_text in intent.clarification_questions:
                    questions.append(self._generate_from_intent_question(intent, q_text))

        if matches:
            questions.extend(self._generate_from_matches(matches))

        questions.sort(key=lambda q: q.priority, reverse=True)

        self._logger.info("Generated clarification questions", count=len(questions))
        return questions

    def _generate_missing_trigger_question(self) -> ClarificationQuestion:
        """Generate question for missing trigger."""
        available_triggers = self._get_available_triggers()

        options = [
            ClarificationOption(
                id=cap.id,
                label=cap.name,
                description=cap.description,
                value=cap.id,
                is_recommended=cap.id == "trigger_email",
            )
            for cap in available_triggers
        ]

        return ClarificationQuestion(
            type=ClarificationType.MISSING_TRIGGER,
            question="What should trigger this agent?",
            context="I need to know when this agent should start running.",
            options=options,
            priority=10,
        )

    def _generate_missing_action_question(self) -> ClarificationQuestion:
        """Generate question for missing actions."""
        return ClarificationQuestion(
            type=ClarificationType.MISSING_ACTION,
            question="What should the agent do when triggered?",
            context="I understand when to run, but I need to know what actions to take.",
            options=[
                ClarificationOption(id="summarize", label="Summarize content", description="Create a summary of the content", value="action_summarize"),
                ClarificationOption(id="extract", label="Extract information", description="Extract specific data like action items or entities", value="action_extract"),
                ClarificationOption(id="notify", label="Send notification", description="Send a message to Slack, email, or other channel", value="action_send_message"),
                ClarificationOption(id="ticket", label="Create ticket", description="Create a Jira, Linear, or other issue tracker ticket", value="action_create_ticket"),
            ],
            priority=9,
        )

    def _generate_from_intent_question(self, intent: Any, question_text: str) -> ClarificationQuestion:
        """Generate question from intent's clarification need."""
        if "channel" in question_text.lower() or "where" in question_text.lower():
            q_type = ClarificationType.AMBIGUOUS_TARGET
        elif "which" in question_text.lower():
            q_type = ClarificationType.MULTIPLE_OPTIONS
        else:
            q_type = ClarificationType.MISSING_PARAMETER

        return ClarificationQuestion(
            type=q_type,
            question=question_text,
            context=f"For: {intent.description}",
            related_intent_id=str(intent.id),
            priority=5,
        )

    def _generate_from_matches(self, matches: CapabilityMatchResult) -> list[ClarificationQuestion]:
        """Generate questions from capability match issues."""
        questions = []
        all_matches = matches.trigger_matches + matches.action_matches + matches.condition_matches

        for match in all_matches:
            if match.missing_parameters:
                capability = CapabilityRegistry.get_capability(match.capability_id)
                for param in match.missing_parameters:
                    schema = capability.parameter_schema.get(param, {}) if capability else {}
                    questions.append(self._generate_parameter_question(match.capability_name, param, schema, match.intent_id))

            if not match.is_available:
                questions.append(ClarificationQuestion(
                    type=ClarificationType.MULTIPLE_OPTIONS,
                    question=f"'{match.capability_name}' requires {match.unavailability_reason}. Would you like to use an alternative?",
                    context="This capability isn't available with your current integrations.",
                    related_intent_id=match.intent_id,
                    options=self._get_alternative_options(match.capability_id),
                    priority=7,
                ))

        return questions

    def _generate_parameter_question(
        self,
        capability_name: str,
        param_name: str,
        schema: dict,
        intent_id: str,
    ) -> ClarificationQuestion:
        """Generate question for a missing parameter."""
        param_display = param_name.replace("_", " ").title()

        if schema.get("type") == "string" and "enum" in schema:
            options = [
                ClarificationOption(id=str(i), label=opt, value=opt)
                for i, opt in enumerate(schema["enum"])
            ]
            return ClarificationQuestion(
                type=ClarificationType.MULTIPLE_OPTIONS,
                question=f"Which {param_display} should be used for {capability_name}?",
                options=options,
                parameter_name=param_name,
                related_intent_id=intent_id,
                priority=6,
            )

        description = schema.get("description", f"the {param_display}")
        return ClarificationQuestion(
            type=ClarificationType.MISSING_PARAMETER,
            question=f"What {description}?",
            context=f"Needed for {capability_name}",
            parameter_name=param_name,
            related_intent_id=intent_id,
            priority=6,
        )

    def _get_available_triggers(self) -> list:
        """Get trigger capabilities available to tenant."""
        from aswa_agents.generation.capabilities import CapabilityCategory

        all_triggers = CapabilityRegistry.get_capabilities_by_category(CapabilityCategory.TRIGGER)
        return [
            cap for cap in all_triggers
            if not cap.required_connectors or all(c in self.tenant_connectors for c in cap.required_connectors)
        ]

    def _get_alternative_options(self, capability_id: str) -> list[ClarificationOption]:
        """Get alternative capabilities for unavailable one."""
        capability = CapabilityRegistry.get_capability(capability_id)
        if not capability:
            return []

        alternatives = []
        for intent_type in capability.intent_types:
            for alt_cap in CapabilityRegistry.get_capabilities_for_intent(intent_type):
                if alt_cap.id != capability_id:
                    available = all(c in self.tenant_connectors for c in alt_cap.required_connectors)
                    if available:
                        alternatives.append(ClarificationOption(
                            id=alt_cap.id,
                            label=alt_cap.name,
                            description=alt_cap.description,
                            value=alt_cap.id,
                        ))

        return alternatives


class ClarificationDialogManager:
    """Manages the clarification dialog flow."""

    def __init__(self):
        self._logger = logger.bind(component="ClarificationDialogManager")

    def apply_response(
        self,
        intents: IntentExtractionResult,
        question: ClarificationQuestion,
        response: ClarificationResponse,
    ) -> IntentExtractionResult:
        """Apply a clarification response to update intents."""
        value = response.custom_input or self._get_option_value(question, response.selected_option_id)

        if question.type == ClarificationType.MISSING_TRIGGER:
            intents = self._add_trigger_intent(intents, value)
        elif question.type == ClarificationType.MISSING_ACTION:
            intents = self._add_action_intent(intents, value)
        elif question.type == ClarificationType.MISSING_PARAMETER:
            intents = self._update_intent_parameter(intents, question.related_intent_id, question.parameter_name, value)
        elif question.type == ClarificationType.AMBIGUOUS_TARGET:
            intents = self._update_intent_parameter(intents, question.related_intent_id, question.parameter_name or "target", value)
        elif question.type == ClarificationType.MULTIPLE_OPTIONS:
            if question.related_intent_id:
                intents = self._replace_capability(intents, question.related_intent_id, value)

        intents.clarification_questions = [q for q in intents.clarification_questions if q != question.question]
        intents.needs_clarification = len(intents.clarification_questions) > 0

        return intents

    def _get_option_value(self, question: ClarificationQuestion, option_id: str | None) -> Any:
        """Get value from selected option."""
        if not option_id:
            return None
        for option in question.options:
            if option.id == option_id:
                return option.value
        return None

    def _add_trigger_intent(self, intents: IntentExtractionResult, trigger_type: str) -> IntentExtractionResult:
        """Add a trigger intent."""
        from aswa_agents.generation.models import ExtractedIntent

        capability = CapabilityRegistry.get_capability(trigger_type)
        intent_type_str = capability.intent_types[0] if capability else "trigger_on_manual"

        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.UNKNOWN

        new_intent = ExtractedIntent(
            type=intent_type,
            confidence=0.9,
            description=capability.description if capability else trigger_type,
            source_text="user clarification",
        )

        intents.trigger_intents.append(new_intent)
        return intents

    def _add_action_intent(self, intents: IntentExtractionResult, action_type: str) -> IntentExtractionResult:
        """Add an action intent."""
        from aswa_agents.generation.models import ExtractedIntent

        capability = CapabilityRegistry.get_capability(action_type)
        intent_type_str = capability.intent_types[0] if capability else "action_custom"

        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.UNKNOWN

        new_intent = ExtractedIntent(
            type=intent_type,
            confidence=0.9,
            description=capability.description if capability else action_type,
            source_text="user clarification",
        )

        intents.action_intents.append(new_intent)
        return intents

    def _update_intent_parameter(
        self,
        intents: IntentExtractionResult,
        intent_id: str | None,
        param_name: str | None,
        value: Any,
    ) -> IntentExtractionResult:
        """Update a parameter on an intent."""
        if not intent_id or not param_name:
            return intents

        for intent in intents.all_intents:
            if str(intent.id) == intent_id:
                intent.parameters[param_name] = value
                intent.requires_clarification = False
                intent.clarification_questions = []
                break

        return intents

    def _replace_capability(
        self,
        intents: IntentExtractionResult,
        intent_id: str,
        new_capability_id: str,
    ) -> IntentExtractionResult:
        """Replace the capability for an intent."""
        capability = CapabilityRegistry.get_capability(new_capability_id)
        if not capability:
            return intents

        intent_type_str = capability.intent_types[0] if capability.intent_types else "unknown"

        for intent in intents.all_intents:
            if str(intent.id) == intent_id:
                try:
                    intent.type = IntentType(intent_type_str)
                except ValueError:
                    intent.type = IntentType.UNKNOWN
                intent.description = capability.description
                intent.requires_clarification = False
                break

        return intents

    def generate_dialog_response(self, questions: list[ClarificationQuestion]) -> str:
        """Generate a natural language response with clarification questions."""
        if not questions:
            return "I have all the information I need. Would you like me to create the agent?"

        top_questions = questions[:3]
        parts = ["I need a bit more information:"]

        for q in top_questions:
            if q.options:
                options_text = ", ".join(o.label for o in q.options[:4])
                parts.append(f"\n- {q.question}")
                parts.append(f"  Options: {options_text}")
            else:
                parts.append(f"\n- {q.question}")

            if q.context:
                parts.append(f"  ({q.context})")

        return "\n".join(parts)
