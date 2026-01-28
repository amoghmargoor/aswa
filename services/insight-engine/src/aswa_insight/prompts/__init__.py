"""Prompt templates for extraction tasks."""

from .base import PromptTemplate, PromptManager, prompt_manager
from .entity_prompts import EntityExtractionPrompt
from .risk_prompts import RiskExtractionPrompt
from .opportunity_prompts import OpportunityExtractionPrompt
from .pattern_prompts import PatternExtractionPrompt
from .combined_prompts import CombinedExtractionPrompt, CombinedExtractionResult

__all__ = [
    "PromptTemplate",
    "PromptManager",
    "prompt_manager",
    "EntityExtractionPrompt",
    "RiskExtractionPrompt",
    "OpportunityExtractionPrompt",
    "PatternExtractionPrompt",
    "CombinedExtractionPrompt",
    "CombinedExtractionResult",
]
