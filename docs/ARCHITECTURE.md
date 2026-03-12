# Architecture

## System Overview

Trends Engine is a 4-service pipeline:

1. **Ingestion** — Collects social media posts from multiple platforms, enriches them through a 7-stage NLP pipeline, and indexes vectors in Qdrant.

2. **Intelligence** — Detects emerging trends using Velocity + Acceleration algorithms, then generates targeted email campaigns via LLM with RAG-grounded content.

3. **Delivery** — Human-in-the-loop review via Slack agent (state machine with RLHF-like feedback), then sends approved campaigns through email platforms.

4. **Attribution** — Joins marketing data (email recipients) with revenue data (sales records) on email address to compute per-campaign ROI.

## Trend Detection Algorithm

The core algorithm computes velocity (how far above baseline) and acceleration (speeding up or slowing down) per topic per time window:

```
velocity     = (current_count - baseline_count) / baseline_count
acceleration = velocity_current - velocity_previous
```

Topics transition through 6 lifecycle states with hysteresis to prevent false positives from single-window spikes.

## NLP Pipeline

7 stateless stages, each mapping to a stream processing operator:

| Stage | Operation | Latency |
|-------|-----------|---------|
| 1 | Text cleaning | ~μs |
| 2 | VADER sentiment | ~μs |
| 3 | Keyword extraction | ~μs |
| 4 | Entity extraction | ~μs |
| 5 | Topic assignment (keyword 80% + embedding 20%) | ~ns / ~25ms |
| 6 | Embedding (BGE-small or TF-IDF) | ~25ms |
| 7 | Vector indexing (Qdrant) | ~ms |

## Graceful Degradation

Under load: BGE-large → BGE-small → TF-IDF fallback. Self-healing backfills TF-IDF items with real embeddings when load normalizes.

## Campaign Generation

RAG pipeline: two-pass vector search (within-topic + cross-topic) → prompt assembly with trend context + retrieved posts → structured JSON output from LLM → human review via Slack → delivery.

Token budget: ~9,200 tokens per campaign including revisions.

## Revenue Attribution

The data bridge joins on email address across marketing platform (recipients) and revenue platform (customers). ROI computed as revenue lift between 7-day pre-campaign baseline and 7-day post-campaign window for the same customer cohort.
