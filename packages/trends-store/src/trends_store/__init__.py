"""
trends-store: Vector store abstraction for trend data (Qdrant).

Provides vector indexing, two-pass RAG search (within-topic + cross-topic),
and automatic fallback from Qdrant server to in-memory mode.

Quick start:
    from trends_store import VectorStore
    store = VectorStore(collection="trends")
    store.index(items)
    results = store.search_rag(query_embedding, topic_id="ai_tools")
"""

__version__ = "0.1.0"

from trends_store.vector_store import VectorStore

__all__ = ["VectorStore"]
