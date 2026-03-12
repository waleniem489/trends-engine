# trends-nlp

7-stage NLP enrichment pipeline for social content analysis.

Part of [Trends Engine](https://github.com/neelmanivispute/trends-engine) — can be used independently.

## Install

```bash
pip install trends-nlp                    # Core (sentiment + keywords)
pip install trends-nlp[embeddings]        # + BGE embeddings
pip install trends-nlp[all]               # Everything
```

## Usage

```python
from trends_nlp import NLPPipeline

pipeline = NLPPipeline(enable_embeddings=True)
enriched = pipeline.process(raw_items)

# Or use individual stages
from trends_nlp import clean_text, analyze_sentiment, extract_keywords

text = clean_text("<p>Check out this amazing AI tool! 🚀 https://example.com</p>")
sentiment = analyze_sentiment(text)
keywords = extract_keywords(text)
```

## Pipeline Stages

| Stage | Module | Speed | Description |
|-------|--------|-------|-------------|
| 1 | `cleaner` | ~μs | HTML, URLs, mentions, whitespace |
| 2 | `sentiment` | ~μs | VADER (social-media-aware) |
| 3 | `keywords` | ~μs | Frequency + 130 stop words |
| 4 | `keywords` | ~μs | Pattern-based NER |
| 5 | `topic_assigner` | ~ns/~25ms | Two-tier: keyword (80%) + embedding (20%) |
| 6 | `embedder` | ~25ms | BGE-small-en-v1.5 or TF-IDF fallback |
| 7 | `vector_store` | ~ms | Qdrant indexing (requires `trends-store`) |

Each stage is stateless per item → maps to Flink/Kafka Streams operators in production.
