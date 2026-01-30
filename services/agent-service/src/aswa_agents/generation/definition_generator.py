"""Generates agent definitions from matched capabilities."""

import re
from typing import Any
from uuid import uuid4

import structlog

from aswa_agents.generation.capabilities import CapabilityMatch, CapabilityMatchResult
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.definition import (
    ActionDefinition,
    ApprovalDefinition,
    ConditionDefinition,
    GeneratedAgentDefinition,
    TriggerDefinition,
    VariableDefinition,
)
from aswa_agents.generation.models import ExtractedIntent, IntentExtractionResult

logger = structlog.get_logger()


class DefinitionGenerationError(Exception):
    """Error during definition generation."""
    pass


class AgentDefinitionGenerator:
    """Generates complete agent definitions from matched capabilities."""

    def __init__(self):
        self._logger = logger.bind(component="DefinitionGenerator")

    async def generate(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult,
        name_hint: str | None = None,
    ) -> GeneratedAgentDefinition:
        """Generate agent definition from intents and capability matches."""
        if not matches.is_feasible:
            raise DefinitionGenerationError(f"Cannot generate: {', '.join(matches.feasibility_issues)}")

        name = self._generate_name(intents, name_hint)
        display_name = self._generate_display_name(intents)
        description = self._generate_description(intents)

        trigger = self._generate_trigger(matches.trigger_matches[0], intents.trigger_intents[0])
        conditions = self._generate_conditions(matches.condition_matches, intents.condition_intents)
        actions = self._generate_actions(matches.action_matches, intents.action_intents)
        variables = self._generate_variables(trigger, actions)
        approval = self._generate_approval_config(matches)
        tags = self._generate_tags(intents, matches)

        definition = GeneratedAgentDefinition(
            name=name,
            display_name=display_name,
            description=description,
            trigger=trigger,
            conditions=conditions,
            variables=variables,
            actions=actions,
            approval=approval,
            tags=tags,
            generation_confidence=matches.overall_feasibility,
            generation_notes=self._generate_notes(intents, matches),
        )

        self._logger.info(
            "Generated agent definition",
            name=name,
            action_count=len(actions),
            confidence=matches.overall_feasibility,
        )

        return definition

    def _generate_name(self, intents: IntentExtractionResult, hint: str | None) -> str:
        """Generate a valid agent name."""
        if hint:
            name = re.sub(r'[^a-z0-9-]', '-', hint.lower())
            name = re.sub(r'-+', '-', name).strip('-')
            return name[:50]

        parts = []
        if intents.trigger_intents:
            trigger_type = intents.trigger_intents[0].type.value
            parts.append(trigger_type.replace("trigger_on_", ""))

        if intents.action_intents:
            action_type = intents.action_intents[0].type.value
            parts.append(action_type.replace("action_", ""))

        base = "-".join(parts) if parts else "generated"
        suffix = uuid4().hex[:6]
        return f"{base}-{suffix}"

    def _generate_display_name(self, intents: IntentExtractionResult) -> str:
        """Generate human-readable display name."""
        parts = []

        if intents.trigger_intents:
            trigger = intents.trigger_intents[0]
            parts.append(trigger.description or "Trigger")

        if intents.action_intents:
            actions = [a.description or a.type.value for a in intents.action_intents]
            parts.append(" & ".join(actions[:2]))

        return " → ".join(parts) if parts else "Generated Agent"

    def _generate_description(self, intents: IntentExtractionResult) -> str:
        """Generate agent description."""
        return intents.normalized_input or intents.original_input

    def _generate_trigger(self, match: CapabilityMatch, intent: ExtractedIntent) -> TriggerDefinition:
        """Generate trigger configuration."""
        capability = CapabilityRegistry.get_capability(match.capability_id)
        config = dict(match.parameter_mappings)

        if capability:
            for param, schema in capability.parameter_schema.items():
                if param not in config and "default" in schema:
                    config[param] = schema["default"]

        return TriggerDefinition(
            type=match.capability_id.replace("trigger_", ""),
            config=config,
        )

    def _generate_conditions(
        self,
        matches: list[CapabilityMatch],
        intents: list[ExtractedIntent],
    ) -> list[ConditionDefinition]:
        """Generate condition configurations."""
        conditions = []
        for match, intent in zip(matches, intents):
            condition = ConditionDefinition(
                type="expression",
                expression=self._build_condition_expression(intent),
                description=intent.description,
            )
            conditions.append(condition)
        return conditions

    def _build_condition_expression(self, intent: ExtractedIntent) -> str:
        """Build condition expression from intent."""
        params = intent.parameters

        if "keyword" in params:
            return f'contains(trigger.content, "{params["keyword"]}")'
        elif "from_filter" in params:
            return f'trigger.from == "{params["from_filter"]}"'
        elif "priority" in params:
            return f'trigger.priority == "{params["priority"]}"'

        return "true"

    def _generate_actions(
        self,
        matches: list[CapabilityMatch],
        intents: list[ExtractedIntent],
    ) -> list[ActionDefinition]:
        """Generate action configurations."""
        actions = []
        previous_id = None

        for i, (match, intent) in enumerate(zip(matches, intents)):
            action_id = f"action_{i+1}"
            config = dict(match.parameter_mappings)
            config = self._add_template_variables(config, match, intent)
            depends_on = [previous_id] if previous_id else []

            action = ActionDefinition(
                id=action_id,
                type=match.capability_id.replace("action_", ""),
                config=config,
                depends_on=depends_on,
                description=intent.description,
            )
            actions.append(action)
            previous_id = action_id

        return actions

    def _add_template_variables(
        self,
        config: dict[str, Any],
        match: CapabilityMatch,
        intent: ExtractedIntent,
    ) -> dict[str, Any]:
        """Add template variables for dynamic content."""
        if "summarize" in match.capability_id:
            if "content" not in config:
                config["content"] = "{{ trigger.content }}"

        if "send" in match.capability_id or "message" in match.capability_id:
            if "message" not in config:
                config["message"] = "{{ actions.action_1.result }}"

        if "create" in match.capability_id and "ticket" in match.capability_id:
            if "title" not in config:
                config["title"] = "{{ trigger.subject | default: 'New Issue' }}"
            if "description" not in config:
                config["description"] = "{{ trigger.content }}"

        return config

    def _generate_variables(
        self,
        trigger: TriggerDefinition,
        actions: list[ActionDefinition],
    ) -> list[VariableDefinition]:
        """Generate variable definitions for data flow."""
        variables = [
            VariableDefinition(name="trigger_content", source="trigger", path="content")
        ]

        for action in actions:
            variables.append(VariableDefinition(
                name=f"{action.id}_result",
                source="action_result",
                path=f"{action.id}.result",
            ))

        return variables

    def _generate_approval_config(self, matches: CapabilityMatchResult) -> ApprovalDefinition:
        """Generate approval configuration based on confidence."""
        confidence = matches.overall_feasibility

        if confidence >= 0.95:
            mode = "auto"
        elif confidence >= 0.85:
            mode = "notify"
        elif confidence >= 0.7:
            mode = "review"
        else:
            mode = "manual"

        return ApprovalDefinition(mode=mode, confidence_threshold=confidence)

    def _generate_tags(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult,
    ) -> list[str]:
        """Generate tags for the agent."""
        tags = ["generated"]

        if matches.trigger_matches:
            trigger_type = matches.trigger_matches[0].capability_id.replace("trigger_", "")
            tags.append(trigger_type)

        for match in matches.action_matches:
            capability = CapabilityRegistry.get_capability(match.capability_id)
            if capability and capability.required_connectors:
                tags.extend(capability.required_connectors)

        return list(set(tags))

    def _generate_notes(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult,
    ) -> list[str]:
        """Generate notes about the generation."""
        notes = []

        for match in matches.trigger_matches + matches.action_matches:
            if match.missing_parameters:
                notes.append(f"{match.capability_name}: Missing {', '.join(match.missing_parameters)}")

        if matches.overall_feasibility < 0.8:
            notes.append("Review recommended due to lower confidence")

        return notes
