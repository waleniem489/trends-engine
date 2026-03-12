"""
trends-campaign: LLM-powered marketing campaign generation with RAG.

Supports multiple LLM providers (Ollama, Claude, OpenAI, Cohere) and
generates targeted email campaigns grounded in real trend data via
retrieval-augmented generation.

Quick start:
    from trends_campaign import CampaignGenerator, create_provider
    provider = create_provider("ollama", model="llama3.1")
    generator = CampaignGenerator(provider)
    campaign = generator.generate(trend_context, rag_posts)
"""

__version__ = "0.1.0"

from trends_campaign.provider import (
    LLMProvider,
    OllamaProvider,
    ClaudeProvider,
    OpenAIProvider,
    CohereProvider,
    create_provider,
)
from trends_campaign.campaign_generator import CampaignGenerator
from trends_campaign.prompts import build_campaign_prompt

__all__ = [
    "CampaignGenerator",
    "LLMProvider",
    "OllamaProvider",
    "ClaudeProvider",
    "OpenAIProvider",
    "CohereProvider",
    "create_provider",
    "build_campaign_prompt",
]
