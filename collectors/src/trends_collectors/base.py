"""
BaseCollector — The Plugin Contract
====================================
Every data source collector (Reddit, RSS, Demo, future Twitter/TikTok)
must extend this class and implement collect().

This is the Strategy Pattern — the Orchestrator calls collect() on
every registered collector without knowing HOW each one works.
Adding a new source = writing one class. Zero downstream changes.

Design decisions:
- Abstract base class (not Protocol) for clear inheritance + docstrings
- collect() is a generator (yield) for memory efficiency with large datasets
- health_check() lets orchestrator skip unhealthy sources gracefully
- get_config() returns operational metadata for monitoring/logging
"""

from abc import ABC, abstractmethod
from typing import Generator


class BaseCollector(ABC):
    """
    Abstract base class for all data source collectors.

    Every collector MUST:
    1. Implement collect() → yields ContentItem dicts
    2. Implement health_check() → returns True if source is reachable
    3. Set self.name and self.platform in __init__

    Every collector SHOULD:
    4. Handle its own rate limiting internally
    5. Handle its own authentication internally
    6. Log errors but never crash — yield what you can, skip what fails

    The Orchestrator only calls:
    - collector.health_check() → skip if unhealthy
    - collector.collect() → iterate results
    - collector.name → for logging/metrics
    """

    def __init__(self, name: str, platform: str):
        """
        Parameters
        ----------
        name : str
            Human-readable name for logging. E.g., "reddit", "news_rss"

        platform : str
            Platform identifier that goes into ContentItem.source_platform.
            Must match one of: "reddit", "news", "twitter", "instagram",
            "tiktok", "linkedin", "demo"
        """
        self.name = name
        self.platform = platform
        self.enabled = True

    @abstractmethod
    def collect(self) -> Generator[dict, None, None]:
        """
        Collect content from this source.

        Yields
        ------
        dict
            ContentItem dicts (created via create_content_item).
            Each must conform to the universal schema.

        Notes
        -----
        - This is a GENERATOR. Yield items one at a time.
          Don't accumulate everything in memory then return.
        - Handle errors PER ITEM. If one post fails to parse,
          log and skip — don't crash the entire collection run.
        - Respect rate limits internally. The Orchestrator doesn't
          manage rate limiting for you.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if this data source is reachable.

        Returns
        -------
        bool
            True if the source is available and we can collect from it.
            False if API is down, credentials expired, etc.

        Notes
        -----
        Should be FAST (< 5 seconds). Don't do a full collection.
        Just verify connectivity — ping the API, fetch one item, etc.
        """
        pass

    def get_config(self) -> dict:
        """
        Return operational metadata for monitoring and logging.

        Override this in subclasses to add source-specific config.
        """
        return {
            "name": self.name,
            "platform": self.platform,
            "enabled": self.enabled,
        }

    def __repr__(self) -> str:
        status = "✅" if self.enabled else "❌"
        return f"{status} {self.name} ({self.platform})"
