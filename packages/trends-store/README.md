# trends-store

Vector store abstraction for trend data with two-pass RAG search.

Part of [Trends Engine](https://github.com/neelmanivispute/trends-engine) — can be used independently.

## Install

```bash
pip install trends-store
```

## Usage

```python
from trends_store import VectorStore

# Auto-detects Qdrant Docker server or falls back to in-memory
store = VectorStore(collection="trends")

# Index items
store.index(enriched_items)

# Two-pass RAG search
results = store.search_rag(
    query_embedding=embedding_vector,  # 384-dim
    topic_id="ai_tools",              # Pass 1: within-topic precision
    limit=10,                         # Pass 2: cross-topic neighbors
)
```

## Infrastructure

```bash
docker run -p 6333:6333 qdrant/qdrant:v1.8.1
```

Without Qdrant running, the store automatically falls back to in-memory mode (suitable for development and small datasets).

## Capacity Planning

| Scale | Vectors | Storage | RAM |
|-------|---------|---------|-----|
| Dev | 10K | ~20MB | 256MB |
| Small | 1M | ~2GB | 4GB |
| Production (90 days) | 45M | ~22GB (quantized) | 32-64GB |
