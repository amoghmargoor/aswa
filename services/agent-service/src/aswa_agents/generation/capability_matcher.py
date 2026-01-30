"""Matches user intents to available capabilities."""

import structlog

from aswa_agents.generation.capabilities import (
    Capability,
    CapabilityMatch,
    CapabilityMatchResult,
)
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.models import (
    ExtractedIntent,
    IntentExtractionResult,
)

logger = structlog.get_logger()


class CapabilityMatcher:
    """Matches extracted intents to available capabilities."""

    def __init__(self, tenant_connectors: list[str] | None = None):
        self.tenant_connectors = tenant_connectors or []
        self._logger = logger.bind(component="CapabilityMatcher")
        CapabilityRegistry.initialize()

    async def match(self, intents: IntentExtractionResult) -> CapabilityMatchResult:
        """Match intents to capabilities."""
        result = CapabilityMatchResult()

        for intent in intents.trigger_intents:
            match = self._match_intent(intent)
            if match:
                result.trigger_matches.append(match)
            else:
                result.unmatched_intents.append(str(intent.id))

        for intent in intents.action_intents:
            match = self._match_intent(intent)
            if match:
                result.action_matches.append(match)
            else:
                result.unmatched_intents.append(str(intent.id))

        for intent in intents.condition_intents:
            match = self._match_intent(intent)
            if match:
                result.condition_matches.append(match)
            else:
                result.unmatched_intents.append(str(intent.id))

        result = self._assess_feasibility(result, intents)

        self._logger.info(
            "Capability matching completed",
            trigger_matches=len(result.trigger_matches),
            action_matches=len(result.action_matches),
            unmatched=len(result.unmatched_intents),
            feasibility=result.overall_feasibility,
        )

        return result

    def _match_intent(self, intent: ExtractedIntent) -> CapabilityMatch | None:
        """Match a single intent to a capability."""
        capabilities = CapabilityRegistry.get_capabilities_for_intent(intent.type.value)

        if not capabilities:
            self._logger.warning("No capability found for intent", intent_type=intent.type.value)
            return None

        best_match = None
        best_score = 0.0

        for capability in capabilities:
            score, param_mappings, missing = self._score_capability(intent, capability)
            is_available = self._check_availability(capability)

            if score > best_score:
                best_score = score
                best_match = CapabilityMatch(
                    intent_id=str(intent.id),
                    capability_id=capability.id,
                    capability_name=capability.name,
                    match_score=score,
                    parameter_mappings=param_mappings,
                    missing_parameters=missing,
                    is_available=is_available,
                    unavailability_reason="" if is_available else self._get_unavailability_reason(capability),
                )

        return best_match

    def _score_capability(
        self,
        intent: ExtractedIntent,
        capability: Capability,
    ) -> tuple[float, dict[str, str], list[str]]:
        """Score how well a capability matches an intent."""
        score = 0.7  # Base score for type match
        param_mappings: dict[str, str] = {}
        missing_params: list[str] = []

        cap_params = capability.parameter_schema
        intent_params = intent.parameters

        for cap_param, schema in cap_params.items():
            if cap_param in intent_params:
                param_mappings[cap_param] = intent_params[cap_param]
                score += 0.1
            elif schema.get("required", False):
                missing_params.append(cap_param)
                score -= 0.1

        for entity in intent.entities:
            for cap_param, schema in cap_params.items():
                if self._entity_matches_param(entity.type, cap_param):
                    param_mappings[cap_param] = entity.value
                    if cap_param in missing_params:
                        missing_params.remove(cap_param)
                        score += 0.1

        score *= intent.confidence
        return min(score, 1.0), param_mappings, missing_params

    def _entity_matches_param(self, entity_type: str, param_name: str) -> bool:
        """Check if an entity type can fill a parameter."""
        mappings = {
            "email_address": ["inbox", "to", "from", "from_filter"],
            "channel_name": ["channel"],
            "project_key": ["project"],
            "team_name": ["team"],
            "schedule": ["schedule"],
            "url": ["url", "webhook_url"],
        }
        return param_name in mappings.get(entity_type, [])

    def _check_availability(self, capability: Capability) -> bool:
        """Check if capability is available for tenant."""
        if not capability.required_connectors:
            return True
        return all(connector in self.tenant_connectors for connector in capability.required_connectors)

    def _get_unavailability_reason(self, capability: Capability) -> str:
        """Get reason why capability is unavailable."""
        missing = [c for c in capability.required_connectors if c not in self.tenant_connectors]
        return f"Missing connectors: {', '.join(missing)}"

    def _assess_feasibility(
        self,
        result: CapabilityMatchResult,
        intents: IntentExtractionResult,
    ) -> CapabilityMatchResult:
        """Assess overall feasibility of the agent."""
        issues = []

        if not result.trigger_matches:
            issues.append("No trigger could be matched to available capabilities")

        if not result.action_matches:
            issues.append("No actions could be matched to available capabilities")

        all_matches = result.trigger_matches + result.action_matches + result.condition_matches
        unavailable = [m for m in all_matches if not m.is_available]

        for match in unavailable:
            result.unavailable_capabilities.append(match.capability_id)
            issues.append(f"{match.capability_name}: {match.unavailability_reason}")

        for match in all_matches:
            if match.missing_parameters:
                issues.append(f"{match.capability_name} needs: {', '.join(match.missing_parameters)}")

        if not issues:
            avg_score = sum(m.match_score for m in all_matches) / len(all_matches) if all_matches else 0
            result.overall_feasibility = avg_score
            result.is_feasible = avg_score >= 0.6
        else:
            result.overall_feasibility = 0.0
            result.is_feasible = False

        result.feasibility_issues = issues
        return result

    def get_available_capabilities(self) -> list[Capability]:
        """Get all capabilities available to the tenant."""
        all_caps = CapabilityRegistry.get_all_capabilities()
        return [cap for cap in all_caps if self._check_availability(cap)]
