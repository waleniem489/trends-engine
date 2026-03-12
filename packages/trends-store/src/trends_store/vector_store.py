"""
Vector Store — Qdrant-Backed Semantic Search
=============================================
Stores enriched items with their BGE embeddings in Qdrant.
Replaces the manual filter/sort/diversify logic for RAG context selection
with proper semantic vector search + metadata filtering.

Why Qdrant (not ChromaDB):
  - Client-server architecture (Docker) → production-ready
  - Rich payload filtering (range, match, nested)
  - HNSW with quantization → fast at scale
  - Falls back to local/in-memory mode when Docker isn't running

Usage:
    store = VectorStore()                    # auto-connects
    store.index_items(enriched_items)        # after NLP pipeline
    posts = store.search_for_campaign(       # during campaign generation
        topic_id="cortado",
        query_text="cortado coffee trending in Austin cafes",
        top_k=8,
    )

Docker setup (your demo machine):
    docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
"""

import logging
import hashlib
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

log = logging.getLogger(__name__)

COLLECTION_NAME = "enriched_items"
VECTOR_DIM = 384  # BGE-small-en-v1.5


def _content_id_to_int(content_id: str) -> int:
    """Convert string content_id to a stable integer for Qdrant point ID."""
    return int(hashlib.md5(content_id.encode()).hexdigest()[:15], 16)


class VectorStore:
    """
    Qdrant-backed vector store for enriched content items.

    Connects to Qdrant server (Docker) if available,
    falls back to local/in-memory mode for environments without Docker.
    """

    def __init__(self, host: str = "localhost", port: int = 6333, prefer_grpc: bool = False):
        """
        Initialize connection to Qdrant.

        Parameters
        ----------
        host : str
            Qdrant server host. Default localhost (Docker).
        port : int
            Qdrant REST port. Default 6333.
        """
        self.mode = "unknown"

        # Try Docker container first
        try:
            self.client = QdrantClient(host=host, port=port, timeout=3)
            self.client.get_collections()  # test connection
            self.mode = "server"
            log.info(f"Qdrant: connected to server at {host}:{port}")
        except Exception:
            # Fall back to local in-memory
            self.client = QdrantClient(":memory:")
            self.mode = "memory"
            log.info("Qdrant: running in-memory (no Docker server found)")

        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_DIM,
                    distance=Distance.COSINE,
                ),
            )
            # Create payload indexes for filtered search
            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="topic_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="platform",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            log.info(f"Qdrant: created collection '{COLLECTION_NAME}' ({VECTOR_DIM}-dim, cosine)")

    def reset(self):
        """Drop and recreate the collection. Used by `clean` command."""
        try:
            self.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._ensure_collection()
        log.info("Qdrant: collection reset")

    def count(self) -> int:
        """Return number of points in the collection."""
        info = self.client.get_collection(COLLECTION_NAME)
        return info.points_count

    def index_items(self, enriched_items: list, batch_size: int = 100) -> int:
        """
        Index enriched items into Qdrant.

        Parameters
        ----------
        enriched_items : list
            Enriched items from NLP pipeline (must have 'embedding' field).
        batch_size : int
            Upsert batch size.

        Returns
        -------
        int
            Number of items indexed.
        """
        points = []
        skipped = 0

        for item in enriched_items:
            embedding = item.get("embedding")
            if not embedding or len(embedding) != VECTOR_DIM:
                skipped += 1
                continue

            content_id = item.get("content_id", "")
            engagement = item.get("engagement", {})
            total_engagement = sum(engagement.values()) if isinstance(engagement, dict) else 0
            nlp = item.get("nlp", {})
            topic = nlp.get("topic", {})
            sentiment = nlp.get("sentiment", {})

            point = PointStruct(
                id=_content_id_to_int(content_id),
                vector=embedding,
                payload={
                    "content_id": content_id,
                    "topic_id": topic.get("topic_id") or "unknown",
                    "topic_name": topic.get("topic_name") or "Unknown",
                    "platform": item.get("source_platform") or "unknown",
                    "sentiment_compound": sentiment.get("compound", 0.0),
                    "sentiment_label": sentiment.get("label", "neutral"),
                    "total_engagement": total_engagement,
                    "cleaned_text": item.get("cleaned_text", "")[:500],  # cap for storage
                    "content_text": item.get("content_text", "")[:500],
                    "published_at": item.get("published_at", ""),
                    "source_url": item.get("source_url", ""),
                    "keywords": nlp.get("keywords", [])[:10],
                    "match_method": topic.get("match_method", "unknown"),
                    "confidence": topic.get("confidence", 0.0),
                },
            )
            points.append(point)

        # Batch upsert
        indexed = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(collection_name=COLLECTION_NAME, points=batch)
            indexed += len(batch)

        log.info(f"Qdrant: indexed {indexed} items (skipped {skipped} without embeddings)")
        return indexed

    def search_for_campaign(
        self,
        topic_id: str,
        query_embedding: list,
        top_k: int = 8,
        min_sentiment: float = -1.0,
        platform_diversity: bool = True,
    ) -> list:
        """
        Semantic search for RAG context — replaces _get_sample_posts().

        This is the KEY improvement: instead of exact topic_id match + manual sorting,
        we do vector similarity search with metadata filtering. This catches:
          - Posts about the topic that were assigned to a neighboring topic
          - Semantically related posts the keyword matcher missed
          - Cross-topic context (oat milk posts relevant to cortado campaign)

        Parameters
        ----------
        topic_id : str
            Target topic for filtering (used as a soft filter).
        query_embedding : list
            384-d embedding of the query (e.g., "cortado coffee trend").
        top_k : int
            Number of posts to return.
        min_sentiment : float
            Minimum sentiment score (filter out very negative posts).
        platform_diversity : bool
            If True, ensure at least one post per platform.

        Returns
        -------
        list
            Top-K enriched items formatted for RAG context.
        """
        # Strategy: Search 3x top_k, then apply diversity + re-ranking
        search_limit = top_k * 3

        # First: search within the topic (high-precision)
        topic_results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            query_filter=Filter(
                must=[
                    FieldCondition(key="topic_id", match=MatchValue(value=topic_id)),
                ],
            ),
            limit=search_limit,
        ).points

        # Second: search across ALL topics (semantic neighbors — cross-topic RAG)
        global_results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=search_limit,
        ).points

        # Merge and deduplicate (topic results get priority)
        seen_ids = set()
        all_candidates = []

        for point in topic_results:
            if point.id not in seen_ids:
                seen_ids.add(point.id)
                all_candidates.append({"point": point, "source": "topic_match"})

        for point in global_results:
            if point.id not in seen_ids:
                seen_ids.add(point.id)
                all_candidates.append({"point": point, "source": "semantic_neighbor"})

        # Filter by sentiment
        if min_sentiment > -1.0:
            all_candidates = [
                c for c in all_candidates
                if c["point"].payload.get("sentiment_compound", 0) >= min_sentiment
            ]

        # Apply platform diversity if requested
        if platform_diversity and len(all_candidates) > top_k:
            selected = self._diversify_by_platform(all_candidates, top_k)
        else:
            selected = all_candidates[:top_k]

        # Format for campaign generator (match the old _get_sample_posts output)
        results = []
        for candidate in selected:
            p = candidate["point"].payload
            results.append({
                "content_id": p.get("content_id", ""),
                "cleaned_text": p.get("cleaned_text", ""),
                "content_text": p.get("content_text", ""),
                "platform": p.get("platform", "unknown"),
                "source_platform": p.get("platform", "unknown"),
                "nlp": {
                    "sentiment": {
                        "compound": p.get("sentiment_compound", 0.0),
                        "label": p.get("sentiment_label", "neutral"),
                    },
                    "topic": {
                        "topic_id": p.get("topic_id", ""),
                        "topic_name": p.get("topic_name", ""),
                    },
                    "keywords": p.get("keywords", []),
                },
                "engagement": {"total": p.get("total_engagement", 0)},
                "published_at": p.get("published_at", ""),
                "source_url": p.get("source_url", ""),
                "_retrieval": {
                    "score": candidate["point"].score,
                    "source": candidate["source"],
                },
            })

        return results

    def _diversify_by_platform(self, candidates: list, top_k: int) -> list:
        """
        Select top_k candidates with platform diversity.
        Round-robin across platforms, then fill remaining with best scores.
        """
        by_platform = {}
        for c in candidates:
            platform = c["point"].payload.get("platform", "unknown")
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append(c)

        selected = []
        seen_ids = set()

        # Round 1: one per platform (highest score from each)
        for platform in sorted(by_platform.keys()):
            if by_platform[platform] and len(selected) < top_k:
                pick = by_platform[platform][0]
                selected.append(pick)
                seen_ids.add(pick["point"].id)

        # Round 2: fill remaining with best overall scores
        remaining = [c for c in candidates if c["point"].id not in seen_ids]
        for c in remaining:
            if len(selected) >= top_k:
                break
            selected.append(c)

        return selected

    def get_topic_stats(self) -> dict:
        """Return item count per topic for diagnostics."""
        # Scroll through all points and count by topic
        stats = {}
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=COLLECTION_NAME,
                limit=500,
                offset=offset,
                with_payload=["topic_id"],
            )
            if not results:
                break
            for point in results:
                tid = point.payload.get("topic_id", "unknown")
                stats[tid] = stats.get(tid, 0) + 1
            if offset is None:
                break

        return dict(sorted(stats.items(), key=lambda x: x[1], reverse=True))

    def info(self) -> str:
        """Return human-readable store info."""
        count = self.count()
        return f"Qdrant [{self.mode}] — {count} vectors in '{COLLECTION_NAME}' ({VECTOR_DIM}-dim, cosine)"
