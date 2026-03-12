"""
ContentItem Schema — The Universal Data Contract
=================================================
Every collector (Reddit, RSS, Demo, future Twitter/TikTok) MUST output
this exact schema. Downstream layers (NLP, Trend Detection, RAG) only
understand this format. This decoupling is what makes the plugin
architecture work.

Design decisions:
- Dict-based (not dataclass) for easy JSON serialization to Kafka/cache
- Engagement is a nested dict because each platform has different metrics
- metadata is a flexible dict for platform-specific fields
- content_id uses "{platform}_{native_id}" pattern for global uniqueness
"""

from datetime import datetime, timezone
from typing import Optional


def create_content_item(
    content_id: str,
    source_platform: str,
    source_url: str,
    content_text: str,
    published_at: str,
    author: str = "unknown",
    engagement: Optional[dict] = None,
    metadata: Optional[dict] = None,
    content_type: str = "post",
    language: str = "en",
) -> dict:
    """
    Factory function to create a validated ContentItem.

    Using a factory function instead of raw dict construction because:
    1. Enforces required fields at creation time
    2. Auto-generates crawled_at timestamp
    3. Sets sensible defaults
    4. Single place to add validation later

    Parameters
    ----------
    content_id : str
        Globally unique ID. Pattern: "{platform}_{native_id}"
        Examples: "reddit_abc123", "news_hubspot_8f3a", "demo_cortado_042"

    source_platform : str
        One of: "reddit", "news", "twitter", "instagram", "tiktok",
                "linkedin", "demo"

    source_url : str
        Original URL for attribution and deduplication.

    content_text : str
        The actual text content. Should be cleaned (no HTML).
        For social posts: title + body.
        For articles: title + article text.

    published_at : str
        ISO 8601 timestamp of when content was originally published.
        This is EVENT TIME — used by Flink for correct windowing.

    author : str
        Username/handle. For authority scoring, NOT PII storage.

    engagement : dict
        Platform-specific engagement metrics, normalized keys:
        {likes: int, shares: int, comments: int, views: int}

    metadata : dict
        Platform-specific metadata. Flexible schema.
        Reddit: {subreddit, flair, is_self}
        News: {source_name, tags[]}
        Demo: {scenario, day_number}

    content_type : str
        One of: "post", "comment", "article", "video_caption"

    language : str
        ISO 639-1 language code. Default "en".

    Returns
    -------
    dict
        A validated ContentItem ready for Kafka/processing.
    """
    if not content_id or not content_text.strip():
        raise ValueError("content_id and content_text are required")

    if len(content_text.strip()) < 10:
        raise ValueError(
            f"Content too short ({len(content_text.strip())} chars). "
            "Minimum 10 characters to be useful for NLP."
        )

    return {
        "content_id": content_id,
        "source_platform": source_platform,
        "source_url": source_url,
        "content_text": content_text.strip(),
        "published_at": published_at,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "author": author,
        "engagement": engagement or {"likes": 0, "shares": 0, "comments": 0, "views": 0},
        "metadata": metadata or {},
        "content_type": content_type,
        "language": language,
    }
