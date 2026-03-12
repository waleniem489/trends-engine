# Trends Engine

**AI-powered marketing intelligence: detect trends → generate campaigns → measure revenue impact.**

Trends Engine is a modular platform that ingests social media and news data in real time, detects emerging trends using velocity + acceleration algorithms, generates targeted email campaigns via LLMs with human-in-the-loop feedback, delivers through email platforms, and attributes revenue impact back to each campaign.

No other open-source tool combines trend discovery + NLP enrichment + LLM campaign generation + human feedback + revenue attribution in a single system.

---

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐    ┌──────────────┐
│  INGESTION  │───→│  INTELLIGENCE    │───→│  DELIVERY   │───→│ ATTRIBUTION  │
│             │    │                  │    │             │    │              │
│ Collectors  │    │ Trend Detector   │    │ Slack Agent │    │ Data Bridge  │
│ NLP Pipeline│    │ (V+A Algorithm)  │    │ Email Mgr   │    │ ROI Calc     │
│ Vector Store│    │ Campaign Gen     │    │             │    │              │
│ (Qdrant)    │    │ (LLM + RAG)     │    │             │    │              │
└─────────────┘    └──────────────────┘    └─────────────┘    └──────────────┘
```

## Packages

Each package is independently installable via pip:

| Package | Description | Install |
|---------|-------------|---------|
| **[trends-nlp](packages/trends-nlp/)** | 7-stage NLP pipeline: cleaning → sentiment → keywords → entities → topics → embeddings → indexing | `pip install trends-nlp` |
| **[trends-detector](packages/trends-detector/)** | Velocity + Acceleration trend detection with 6 lifecycle states | `pip install trends-detector` |
| **[trends-campaign](packages/trends-campaign/)** | LLM campaign generation with RAG (Ollama, Claude, OpenAI, Cohere) | `pip install trends-campaign` |
| **[trends-store](packages/trends-store/)** | Vector store abstraction (Qdrant) with two-pass RAG search | `pip install trends-store` |
| **[trends-collectors](collectors/)** | Data source connectors (Reddit, Hacker News, NewsAPI, RSS, demo) | `pip install trends-collectors` |

Install everything: `pip install trends-engine[all]`

## Quickstart

```bash
# Clone and install
git clone https://github.com/neelmanivispute/trends-engine.git
cd trends-engine
pip install -e ".[all]"

# Start infrastructure
docker compose up -d  # Qdrant + Redis + Listmonk

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run the quickstart example
python examples/quickstart.py
```

## Key Algorithms

### Trend Detection (Velocity + Acceleration)

```
velocity     = (current_count - baseline) / baseline
acceleration = velocity_current - velocity_previous
```

Topics flow through 6 lifecycle states: **BASELINE → EMERGING → GROWING → PEAKING → DECLINING → VIRAL**. The key insight: velocity alone says a topic at 155% above baseline is hot, but if it was 250% last window, acceleration is -0.95 — it's *peaking*, not *growing*. The marketing response is completely different.

### NLP Pipeline (7 Stages)

Each stage is stateless per item, mapping directly to stream processing operators (Flink, Kafka Streams) in production:

1. **Text Cleaning** — HTML, URLs, mentions, whitespace normalization
2. **Sentiment** — VADER (handles social media slang, emojis, caps)
3. **Keywords** — Frequency counting with 130+ domain-specific stop words
4. **Entities** — Pattern-based NER for platforms, tools, brands
5. **Topic Assignment** — Two-tier: keyword matching (80%, nanoseconds) + embedding similarity (20%, ~25ms)
6. **Embeddings** — BGE-small-en-v1.5 (384-dim) with TF-IDF fallback
7. **Vector Indexing** — Qdrant with two-pass RAG search

### Campaign Generation (RAG + LLM)

Campaigns are grounded in real trend data: top posts retrieved from the vector store via two-pass RAG (within-topic precision + cross-topic semantic neighbors), then composed by an LLM with structured JSON output. Human feedback via Slack creates an RLHF-like revision loop averaging 1.5 iterations per campaign.

## Graceful Degradation

The system adapts to available resources:

- **Embeddings**: BGE-large → BGE-small → TF-IDF (automatic based on load)
- **Vector store**: Qdrant server → in-memory fallback
- **LLM**: Cloud API → local Ollama → template fallback
- **Self-healing**: when load normalizes, TF-IDF items backfilled with real embeddings

## Configuration

Copy `.env.example` to `.env` and configure:

- **LLM_PROVIDER**: `ollama` (free, local), `claude`, `openai`, or `cohere`
- **Data sources**: NewsAPI key, Reddit credentials (all optional)
- **Email delivery**: Listmonk (self-hosted, default) or any SMTP-compatible provider
- **Business profile**: `BUSINESS_TYPE` and `BUSINESS_KEYWORDS` filter relevant trends

## Infrastructure

```bash
docker compose up -d
```

This starts Qdrant (vector store), Redis (caching), and Listmonk (email delivery). Ollama can be uncommented in `docker-compose.yml` for local LLM inference.

## Project Structure

```
trends-engine/
├── packages/
│   ├── trends-nlp/          # 7-stage NLP pipeline
│   ├── trends-detector/     # Velocity + Acceleration algorithm
│   ├── trends-campaign/     # LLM campaign generation with RAG
│   └── trends-store/        # Qdrant vector store abstraction
├── collectors/              # Data source connectors
├── examples/                # Quickstart and usage examples
├── docker/                  # Dockerfiles for each service
├── docs/                    # Architecture documentation
├── docker-compose.yml       # Full stack infrastructure
├── .env.example             # Configuration template
└── pyproject.toml           # Umbrella package
```

## Use Each Package Independently

```python
# Just the NLP pipeline
from trends_nlp import NLPPipeline, analyze_sentiment
pipeline = NLPPipeline(enable_embeddings=False)
enriched = pipeline.process(raw_items)

# Just trend detection
from trends_detector import TrendDetector, aggregate_by_windows
signals = aggregate_by_windows(enriched_items)
reports = TrendDetector().detect(signals)

# Just campaign generation
from trends_campaign import create_provider, CampaignGenerator
provider = create_provider("claude")
campaign = CampaignGenerator(provider).generate(context, posts)

# Just vector search
from trends_store import VectorStore
store = VectorStore(collection="trends")
results = store.search_rag(embedding, topic_id="ai_tools")
```

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Author

[Neelmani Vispute](https://neelmanivispute.vercel.app) — Principal Software Engineer specializing in distributed systems, AI engineering, and autonomous agents.
