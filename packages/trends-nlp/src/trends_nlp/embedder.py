"""
Embedder — Stage 6 of NLP Pipeline
=====================================
Generates vector embeddings for content items.
Used for: topic assignment (Tier 2) + RAG retrieval.

Auto-selects best available method:
1. sentence-transformers (all-MiniLM-L6-v2) — 384-dim, semantic
2. TF-IDF — sparse vectors, lexical (fallback)

On your machine: pip install sentence-transformers
   → Gets you semantic embeddings, much better for paraphrase matching
In this sandbox: TF-IDF fallback (works fine for demo)

Production: Use sentence-transformers or OpenAI embeddings.
Store in Qdrant for fast similarity search.
"""

import logging
import numpy as np
from typing import Optional

log = logging.getLogger(__name__)


class Embedder:
    """
    Generates text embeddings with automatic backend selection.

    Usage:
        embedder = Embedder()
        vector = embedder.embed("Just tried cortado at home")
        print(embedder.backend)  # "sentence-transformers" or "tfidf"
    """

    def __init__(self, backend: Optional[str] = None):
        """
        Parameters
        ----------
        backend : str, optional
            Force a specific backend: "sentence-transformers" or "tfidf".
            If None, auto-selects best available.
        """
        self.backend = None
        self._model = None
        self._tfidf_vectorizer = None
        self._tfidf_fitted = False

        if backend:
            self._init_backend(backend)
        else:
            self._auto_select()

    def _auto_select(self):
        """Try sentence-transformers first, fall back to TF-IDF."""
        try:
            self._init_backend("sentence-transformers")
        except Exception:
            log.info("sentence-transformers not available, falling back to TF-IDF")
            self._init_backend("tfidf")

    def _init_backend(self, backend: str):
        """Initialize the selected embedding backend."""
        if backend == "sentence-transformers":
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("BAAI/bge-small-en-v1.5")
            self.backend = "sentence-transformers"
            self.dim = 384
            log.info("Embedder: sentence-transformers (BGE-small-en-v1.5, 384-dim)")

        elif backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._tfidf_vectorizer = TfidfVectorizer(
                max_features=384,  # Match sentence-transformer dim for consistency
                stop_words="english",
                ngram_range=(1, 2),  # Unigrams + bigrams
                sublinear_tf=True,
            )
            self.backend = "tfidf"
            self.dim = 384
            log.info("Embedder: TF-IDF (384-dim, bigrams)")

        else:
            raise ValueError(f"Unknown backend: {backend}")

    def embed(self, text: str) -> np.ndarray:
        """
        Generate embedding vector for a single text.

        Parameters
        ----------
        text : str
            Cleaned text to embed.

        Returns
        -------
        np.ndarray
            Embedding vector (384-dim for both backends).
        """
        if not text or len(text.strip()) < 3:
            return np.zeros(self.dim)

        if self.backend == "sentence-transformers":
            return self._model.encode(text, show_progress_bar=False)

        elif self.backend == "tfidf":
            return self._tfidf_embed(text)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts efficiently.

        For sentence-transformers: batched GPU/CPU inference.
        For TF-IDF: fit on all texts then transform.

        Parameters
        ----------
        texts : list[str]
            List of cleaned texts.

        Returns
        -------
        np.ndarray
            Matrix of shape (len(texts), dim).
        """
        if not texts:
            return np.zeros((0, self.dim))

        if self.backend == "sentence-transformers":
            return self._model.encode(texts, show_progress_bar=False, batch_size=64)

        elif self.backend == "tfidf":
            return self._tfidf_embed_batch(texts)

    def _tfidf_embed(self, text: str) -> np.ndarray:
        """TF-IDF embedding for a single text."""
        if not self._tfidf_fitted:
            # First call: fit on this text (basic, but works for single items)
            # For better results, use embed_batch to fit on all items first
            self._tfidf_vectorizer.fit([text])
            self._tfidf_fitted = True

        vector = self._tfidf_vectorizer.transform([text]).toarray()[0]

        # Pad or truncate to target dim
        if len(vector) < self.dim:
            vector = np.pad(vector, (0, self.dim - len(vector)))
        return vector[: self.dim]

    def _tfidf_embed_batch(self, texts: list[str]) -> np.ndarray:
        """TF-IDF embeddings for a batch — fits on full corpus for better vectors."""
        # Always refit on the full batch for best vocabulary coverage
        self._tfidf_vectorizer.fit(texts)
        self._tfidf_fitted = True

        matrix = self._tfidf_vectorizer.transform(texts).toarray()

        # Pad columns if fewer features than target dim
        if matrix.shape[1] < self.dim:
            padding = np.zeros((matrix.shape[0], self.dim - matrix.shape[1]))
            matrix = np.hstack([matrix, padding])

        return matrix[:, : self.dim]

    def get_info(self) -> dict:
        """Return embedder configuration info."""
        return {
            "backend": self.backend,
            "dimensions": self.dim,
            "fitted": self._tfidf_fitted if self.backend == "tfidf" else True,
        }
