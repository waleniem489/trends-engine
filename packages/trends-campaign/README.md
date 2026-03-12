# trends-campaign

LLM-powered marketing campaign generation with retrieval-augmented generation (RAG).

Part of [Trends Engine](https://github.com/neelmanivispute/trends-engine) — can be used independently.

## Install

```bash
pip install trends-campaign                # Core (Ollama support)
pip install trends-campaign[anthropic]     # + Claude
pip install trends-campaign[all]           # All providers
```

## Usage

```python
from trends_campaign import create_provider, CampaignGenerator

# Create an LLM provider
provider = create_provider("ollama", model="llama3.1")
# Or: create_provider("claude"), create_provider("openai"), create_provider("cohere")

# Generate a campaign
generator = CampaignGenerator(provider)
campaign = generator.generate(
    trend_context={"topic": "AI Tools", "velocity": 2.5, "state": "GROWING"},
    rag_posts=["Post about new AI writing tools...", "AI productivity trends..."],
    industry="saas",
)
```

## Supported Providers

| Provider | Model | Cost | Setup |
|----------|-------|------|-------|
| Ollama | Llama 3.1 | Free (local) | `ollama pull llama3.1` |
| Claude | claude-sonnet-4-20250514 | ~$0.003/campaign | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o | ~$0.005/campaign | `OPENAI_API_KEY` |
| Cohere | command-r-plus | Free tier | `COHERE_API_KEY` |

## Custom Providers

```python
from trends_campaign import LLMProvider

class MyProvider(LLMProvider):
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        # Your LLM call here
        return response_text
```
