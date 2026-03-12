"""
trends-nlp: 7-stage NLP enrichment pipeline for social content.

Stages:
  1. Text cleaning (HTML, URLs, mentions)
  2. Sentiment analysis (VADER)
  3. Keyword extraction (frequency + stop words)
  4. Entity extraction (pattern-based NER)
  5. Topic assignment (keyword matching + embedding similarity)
  6. Embedding generation (BGE-small or TF-IDF fallback)
  7. Vector indexing (Qdrant)

Each stage is stateless per item, mapping cleanly to stream
processing operators (Flink, Kafka Streams) in production.

Quick start:
    from trends_nlp import NLPPipeline
    pipeline = NLPPipeline()
    enriched = pipeline.process(raw_items)
"""

__version__ = "0.1.0"

from trends_nlp.cleaner import clean_text
from trends_nlp.sentiment import analyze_sentiment
from trends_nlp.keywords import extract_keywords, extract_bigrams, extract_entities
from trends_nlp.taxonomy import TAXONOMY, get_topic_keywords
from trends_nlp.topic_assigner import TopicAssigner
from trends_nlp.embedder import Embedder
from trends_nlp.pipeline import NLPPipeline

__all__ = [
    "NLPPipeline",
    "clean_text",
    "analyze_sentiment",
    "extract_keywords",
    "extract_bigrams",
    "extract_entities",
    "TopicAssigner",
    "Embedder",
    "TAXONOMY",
    "get_topic_keywords",
]
