"""LLM client module for insight extraction.

Provides abstraction layer for different LLM providers:
- AWS Bedrock (Claude)
- Azure OpenAI (GPT-4)
- OpenAI (GPT-4)
"""

from aswa_insight.llm.client import LLMClient, get_llm_client
from aswa_insight.llm.bedrock import BedrockClient
from aswa_insight.llm.azure import AzureOpenAIClient
from aswa_insight.llm.openai_client import OpenAIClient

__all__ = [
    "LLMClient",
    "get_llm_client",
    "BedrockClient",
    "AzureOpenAIClient",
    "OpenAIClient",
]
