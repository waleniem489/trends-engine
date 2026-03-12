"""
Topic Assigner — Stage 5 of NLP Pipeline
==========================================
Maps each content item to a topic from the taxonomy.
This is THE critical bridge between raw text and trend detection.

Two-tier matching strategy:
  Tier 1: Keyword match (nanoseconds, deterministic)
    "Just tried cortado at home" → scans for "cortado" → match ✅
    Handles ~80% of items. Fast, explainable, perfect for demo.

  Tier 2: Embedding similarity (25ms, catches paraphrases)
    "This tiny Spanish coffee drink is everywhere" → no keyword →
    embed → compare to topic centroids → closest: "cortado" ✅
    Handles the remaining ~20% that use indirect language.

Items matching NO topic → marked "unmatched" → BERTopic candidate
in production (nightly batch discovers new topics).

Design note:
  Topic assignment has a real-time path (keywords + embeddings)
  and a discovery path (BERTopic nightly). Hybrid gives both
  speed and coverage.
"""

import logging
import numpy as np
from typing import Optional

from .taxonomy import get_all_keywords, get_taxonomy, get_taxonomy_map

log = logging.getLogger(__name__)


class TopicAssigner:
    """
    Assigns content items to predefined topics.

    Tier 1: Keyword matching (always available)
    Tier 2: Embedding similarity (when embedder is provided)
    """

    def __init__(self, embedder=None, similarity_threshold: float = 0.3):
        """
        Parameters
        ----------
        embedder : optional
            An Embedder instance (from embedder.py) for Tier 2 matching.
            If None, only keyword matching is used.

        similarity_threshold : float
            Minimum cosine similarity for embedding match.
            Below this → "unmatched". Default 0.3 for TF-IDF
            (use 0.5+ for sentence-transformer embeddings).
        """
        # Build keyword lookup: {"cortado": "cortado", "oat milk": "oat_milk", ...}
        self.keyword_map = get_all_keywords()
        self.taxonomy_map = get_taxonomy_map()
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold

        # Pre-compute topic centroids for Tier 2
        self._topic_centroids = {}
        if embedder:
            self._build_topic_centroids()

        # Stats tracking
        self.stats = {"keyword_match": 0, "embedding_match": 0, "unmatched": 0}

    def assign(self, text: str, keywords: list[str] = None) -> dict:
        """
        Assign a topic to the given text.

        Parameters
        ----------
        text : str
            Cleaned content text.
        keywords : list[str], optional
            Pre-extracted keywords (from Stage 3). Used to boost
            keyword matching accuracy.

        Returns
        -------
        dict
            {
                "topic_id": str or None,
                "topic_name": str or None,
                "category": str or None,
                "confidence": float,      # 0.0-1.0
                "match_method": str       # "keyword" | "embedding" | "unmatched"
            }
        """
        # ── Tier 1: Keyword matching ──
        result = self._keyword_match(text, keywords)
        if result:
            self.stats["keyword_match"] += 1
            return result

        # ── Tier 2: Embedding similarity ──
        if self.embedder:
            result = self._embedding_match(text)
            if result:
                self.stats["embedding_match"] += 1
                return result

        # ── No match ──
        self.stats["unmatched"] += 1
        return {
            "topic_id": None,
            "topic_name": None,
            "category": None,
            "confidence": 0.0,
            "match_method": "unmatched",
        }

    def _keyword_match(self, text: str, keywords: list[str] = None) -> Optional[dict]:
        """
        Tier 1: Scan text for taxonomy keywords.

        Strategy:
        1. Check bigrams first (longer matches are more specific)
           "oat milk" should match before "milk"
        2. Then check unigrams
        3. If multiple topics match, return highest confidence
        """
        text_lower = text.lower()
        matches = {}  # topic_id → max confidence

        # Check all taxonomy keywords against text
        # Sort by length descending — longer phrases are more specific
        for keyword in sorted(self.keyword_map.keys(), key=len, reverse=True):
            if keyword in text_lower:
                topic_id = self.keyword_map[keyword]
                # Confidence based on keyword specificity (longer = more specific)
                confidence = min(0.95, 0.6 + len(keyword) * 0.03)
                if topic_id not in matches or confidence > matches[topic_id]:
                    matches[topic_id] = confidence

        # Also check pre-extracted keywords if provided
        if keywords:
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in self.keyword_map:
                    topic_id = self.keyword_map[kw_lower]
                    confidence = 0.7
                    if topic_id not in matches or confidence > matches[topic_id]:
                        matches[topic_id] = confidence

        if not matches:
            return None

        # Return best match
        best_topic_id = max(matches, key=matches.get)
        topic = self.taxonomy_map[best_topic_id]

        return {
            "topic_id": best_topic_id,
            "topic_name": topic["name"],
            "category": topic["category"],
            "confidence": round(matches[best_topic_id], 3),
            "match_method": "keyword",
        }

    def _embedding_match(self, text: str) -> Optional[dict]:
        """
        Tier 2: Compare text embedding to topic centroids.
        Used when keyword matching fails (indirect language).
        """
        if not self._topic_centroids:
            return None

        try:
            text_embedding = self.embedder.embed(text)

            best_topic_id = None
            best_similarity = -1.0

            for topic_id, centroid in self._topic_centroids.items():
                similarity = self._cosine_similarity(text_embedding, centroid)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_topic_id = topic_id

            if best_similarity >= self.similarity_threshold and best_topic_id:
                topic = self.taxonomy_map[best_topic_id]
                return {
                    "topic_id": best_topic_id,
                    "topic_name": topic["name"],
                    "category": topic["category"],
                    "confidence": round(float(best_similarity), 3),
                    "match_method": "embedding",
                }
        except Exception as e:
            log.debug(f"Embedding match failed: {e}")

        return None

    def _build_topic_centroids(self):
        """
        Pre-compute embedding centroids for each topic.
        Centroid = average embedding of all topic keywords + name.
        """
        for topic in get_taxonomy():
            topic_id = topic["topic_id"]
            # Combine name + all keywords as the topic representation
            topic_texts = [topic["name"]] + topic["keywords"]
            topic_text = " ".join(topic_texts)

            try:
                centroid = self.embedder.embed(topic_text)
                self._topic_centroids[topic_id] = centroid
            except Exception as e:
                log.warning(f"Failed to build centroid for {topic_id}: {e}")

    @staticmethod
    def _cosine_similarity(a, b) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(a).flatten()
        b = np.array(b).flatten()
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    def get_stats(self) -> dict:
        """Return matching statistics."""
        total = sum(self.stats.values())
        return {
            **self.stats,
            "total": total,
            "keyword_pct": round(self.stats["keyword_match"] / max(total, 1) * 100, 1),
            "embedding_pct": round(self.stats["embedding_match"] / max(total, 1) * 100, 1),
            "unmatched_pct": round(self.stats["unmatched"] / max(total, 1) * 100, 1),
        }
