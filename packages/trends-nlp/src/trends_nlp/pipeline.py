"""
NLP Pipeline — The Intelligence Layer
=======================================
Orchestrates all NLP stages to transform raw ContentItems into
EnrichedContentItems ready for trend detection.

Input:  Raw ContentItem (text, timestamp, source)
Output: EnrichedContentItem (+ sentiment, keywords, entities, topic, embedding)

Pipeline stages:
  1. Clean text          → normalized text
  2. Analyze sentiment   → compound score + label
  3. Extract keywords    → top terms + bigrams
  4. Extract entities    → platforms, tools, brands mentioned
  5. Assign topic        → topic_id from taxonomy (keyword + embedding)
  6. Generate embedding  → 384-dim vector for RAG

The pipeline is designed to process items independently (stateless per item)
which is exactly how Flink would run it in production — each item flows
through map() stages without needing state from other items.

Usage:
    pipeline = NLPPipeline()
    enriched_items = pipeline.process_batch(raw_items)
    pipeline.print_stats()
"""

import logging
import time
from typing import Optional

from .cleaner import clean_text
from .sentiment import analyze_sentiment
from .keywords import extract_keywords, extract_bigrams, extract_entities
from .topic_assigner import TopicAssigner
from .embedder import Embedder

try:
    from trends_store import VectorStore
except ImportError:
    VectorStore = None  # Vector indexing available when trends-store is installed

log = logging.getLogger(__name__)


class NLPPipeline:
    """
    Orchestrates all NLP stages into a single process() call.

    Each stage is independent and stateless (per item).
    In production, each stage would be a Flink map() operator.
    """

    def __init__(
        self,
        enable_embeddings: bool = True,
        embedding_backend: Optional[str] = None,
        similarity_threshold: float = 0.3,
        vector_store: Optional[VectorStore] = None,
    ):
        """
        Parameters
        ----------
        enable_embeddings : bool
            Whether to generate embeddings (Stage 6).
            Disable for faster processing when embeddings not needed.

        embedding_backend : str, optional
            Force embedding backend: "sentence-transformers" or "tfidf".
            None = auto-select best available.

        similarity_threshold : float
            Min cosine similarity for embedding-based topic matching.

        vector_store : VectorStore, optional
            Qdrant vector store for indexing enriched items.
            If provided, items are indexed after enrichment.
        """
        # Initialize embedder (if enabled)
        self.embedder = None
        if enable_embeddings:
            self.embedder = Embedder(backend=embedding_backend)
            log.info(f"Embedder: {self.embedder.backend} ({self.embedder.dim}-dim)")

        # Initialize topic assigner (with embedder for Tier 2 matching)
        self.topic_assigner = TopicAssigner(
            embedder=self.embedder,
            similarity_threshold=similarity_threshold,
        )

        # Vector store (Qdrant)
        self.vector_store = vector_store

        # Stats
        self._processed = 0
        self._errors = 0
        self._total_time = 0.0

    def process(self, item: dict) -> dict:
        """
        Process a single ContentItem through all NLP stages.

        Parameters
        ----------
        item : dict
            Raw ContentItem from Layer 1.

        Returns
        -------
        dict
            EnrichedContentItem — original fields + NLP enrichments.
        """
        start = time.time()

        try:
            # ── Stage 1: Clean text ──
            raw_text = item.get("content_text", "")
            cleaned_text = clean_text(raw_text)

            # ── Stage 2: Sentiment ──
            sentiment = analyze_sentiment(cleaned_text)

            # ── Stage 3: Keywords ──
            keywords = extract_keywords(cleaned_text, top_n=8)
            bigrams = extract_bigrams(cleaned_text, top_n=3)

            # ── Stage 4: Entities ──
            entities = extract_entities(cleaned_text)

            # ── Stage 5: Topic assignment ──
            topic = self.topic_assigner.assign(cleaned_text, keywords)

            # ── Stage 6: Embedding ──
            embedding = None
            if self.embedder:
                embedding = self.embedder.embed(cleaned_text)
                embedding = embedding.tolist()  # Convert numpy → list for JSON

            # ── Build enriched item ──
            enriched = {
                **item,  # Keep ALL original fields
                "cleaned_text": cleaned_text,
                "nlp": {
                    "sentiment": sentiment,
                    "keywords": keywords,
                    "bigrams": bigrams,
                    "entities": entities,
                    "topic": topic,
                },
                "embedding": embedding,
            }

            self._processed += 1
            self._total_time += time.time() - start
            return enriched

        except Exception as e:
            self._errors += 1
            log.warning(f"NLP processing failed for {item.get('content_id', '?')}: {e}")
            # Return original item with empty NLP fields (don't drop items)
            return {
                **item,
                "cleaned_text": item.get("content_text", ""),
                "nlp": {
                    "sentiment": {"compound": 0.0, "label": "neutral",
                                  "positive": 0.0, "negative": 0.0, "neutral": 1.0},
                    "keywords": [],
                    "bigrams": [],
                    "entities": {"platforms": [], "tools": [], "brands": []},
                    "topic": {"topic_id": None, "topic_name": None,
                              "category": None, "confidence": 0.0,
                              "match_method": "error"},
                },
                "embedding": None,
            }

    def process_batch(self, items: list[dict], show_progress: bool = True) -> list[dict]:
        """
        Process a batch of ContentItems.

        Optionally pre-fits the TF-IDF embedder on the full corpus
        for better vocabulary coverage.

        Parameters
        ----------
        items : list[dict]
            Raw ContentItems from Layer 1.
        show_progress : bool
            Print progress bar during processing.

        Returns
        -------
        list[dict]
            EnrichedContentItems.
        """
        if not items:
            return []

        total = len(items)
        print(f"\n{'='*60}")
        print(f"  NLP PIPELINE — Processing {total} items")
        print(f"  Embedder: {self.embedder.backend if self.embedder else 'disabled'}")
        print(f"{'='*60}")

        # Pre-fit TF-IDF on full corpus for better embeddings
        if self.embedder and self.embedder.backend == "tfidf":
            print(f"  📐 Pre-fitting TF-IDF on full corpus...")
            all_texts = [clean_text(item.get("content_text", "")) for item in items]
            self.embedder.embed_batch(all_texts)
            print(f"     Vocabulary fitted on {len(all_texts)} documents")

        # Process each item
        enriched_items = []
        start_time = time.time()

        for i, item in enumerate(items):
            enriched = self.process(item)
            enriched_items.append(enriched)

            if show_progress and (i + 1) % 200 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                eta = (total - i - 1) / rate
                print(f"  ⚙️  {i+1}/{total} ({rate:.0f} items/sec, ETA: {eta:.0f}s)")

        elapsed = time.time() - start_time
        print(f"\n  ✅ Processed {total} items in {elapsed:.1f}s "
              f"({total/elapsed:.0f} items/sec)")

        # ── Stage 7: Index into Qdrant vector store ──
        if self.vector_store:
            print(f"\n  📦 Indexing {len(enriched_items)} items into Qdrant...")
            indexed = self.vector_store.index_items(enriched_items)
            print(f"  ✅ Qdrant: {indexed} vectors indexed — {self.vector_store.info()}")

        return enriched_items

    def get_stats(self) -> dict:
        """Return pipeline processing statistics."""
        topic_stats = self.topic_assigner.get_stats()
        return {
            "processed": self._processed,
            "errors": self._errors,
            "avg_time_ms": round(self._total_time / max(self._processed, 1) * 1000, 2),
            "topic_assignment": topic_stats,
            "embedder": self.embedder.get_info() if self.embedder else None,
        }

    def print_stats(self):
        """Print human-readable pipeline statistics."""
        stats = self.get_stats()
        topic = stats["topic_assignment"]

        print(f"\n{'─'*60}")
        print(f"  NLP PIPELINE STATS")
        print(f"{'─'*60}")
        print(f"  Processed:    {stats['processed']} items")
        print(f"  Errors:       {stats['errors']}")
        print(f"  Avg time:     {stats['avg_time_ms']}ms per item")
        print(f"")
        print(f"  Topic Assignment:")
        print(f"    Keyword match:  {topic['keyword_match']:5d} ({topic['keyword_pct']}%)")
        print(f"    Embedding match:{topic['embedding_match']:5d} ({topic['embedding_pct']}%)")
        print(f"    Unmatched:      {topic['unmatched']:5d} ({topic['unmatched_pct']}%)")
        if stats["embedder"]:
            print(f"")
            print(f"  Embedder: {stats['embedder']['backend']} ({stats['embedder']['dimensions']}-dim)")
        print(f"{'─'*60}\n")
