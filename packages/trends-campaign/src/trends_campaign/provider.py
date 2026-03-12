"""
LLM Provider — Abstraction Layer
==================================
Provider-agnostic LLM interface. Swap models with a config change.

Supported providers:
  - ollama:   Local Llama 3.1 via Ollama (default, zero cost)
  - cohere:   Cohere Command R via API (free tier available)
  - claude:   Anthropic Claude via API (production recommendation)
  - openai:   OpenAI GPT-4 via API

Architecture note:
  Each provider implements generate(prompt, system_prompt) → str.
  No LangChain needed — single-model call, 15 lines per provider.
  LangChain makes sense when you need chaining, agents, or multi-model
  orchestration — not for a single-model call with structured prompt.

Production note:
  Provider-agnostic design means swapping models is a config change.
  Claude via AWS Bedrock is recommended for enterprise deployments.
"""

import json
import os
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Generate text from a prompt. Returns the generated string."""
        pass

    @abstractmethod
    def name(self) -> str:
        pass


class OllamaProvider(LLMProvider):
    """
    Local LLM via Ollama.
    Requires: ollama installed + model pulled (ollama pull llama3.1)
    API runs at http://localhost:11434
    """

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
        import urllib.request
        import urllib.error

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", "")
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Is Ollama running? Try: ollama serve\n"
                f"Error: {e}"
            )

    def name(self) -> str:
        return f"ollama/{self.model}"


class CohereProvider(LLMProvider):
    """
    Cohere Command R via API.
    Requires: pip install cohere + COHERE_API_KEY env var
    Free trial tier available at https://cohere.com
    """

    def __init__(self, model: str = "command-r-plus"):
        self.model = model
        self.api_key = os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError("COHERE_API_KEY environment variable not set")

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
        import cohere

        client = cohere.ClientV2(api_key=self.api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.message.content[0].text

    def name(self) -> str:
        return f"cohere/{self.model}"


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude via API.
    Requires: pip install anthropic + ANTHROPIC_API_KEY env var.
    Also available on AWS Bedrock for enterprise deployments.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt if system_prompt else "",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.content[0].text

    def name(self) -> str:
        return f"claude/{self.model}"


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT via API.
    Requires: pip install openai + OPENAI_API_KEY env var
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def name(self) -> str:
        return f"openai/{self.model}"


# ═══════════════════════════════════════════════════════════════
# Factory — Create provider from config string
# ═══════════════════════════════════════════════════════════════

PROVIDERS = {
    "ollama": OllamaProvider,
    "cohere": CohereProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def create_provider(provider_name: str = "ollama", **kwargs) -> LLMProvider:
    """
    Create an LLM provider by name.

    Usage:
        provider = create_provider("ollama", model="llama3.1")
        provider = create_provider("cohere")  # needs COHERE_API_KEY
        provider = create_provider("claude")  # needs ANTHROPIC_API_KEY
    """
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")

    return PROVIDERS[provider_name](**kwargs)
