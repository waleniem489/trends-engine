"""
trends-collectors: Data source connectors for the Trends Engine.

Built-in collectors for Reddit, Hacker News, NewsAPI, and RSS feeds,
plus a demo collector for synthetic data. Follows a registry pattern
for easy extension.

Quick start:
    from trends_collectors import HackerNewsCollector, CollectionOrchestrator
    hn = HackerNewsCollector()
    items = hn.collect()
"""

__version__ = "0.1.0"

from trends_collectors.base import BaseCollector
from trends_collectors.schema import create_content_item
from trends_collectors.orchestrator import CollectorRegistry, CollectionOrchestrator
from trends_collectors.hackernews_collector import HackerNewsCollector
from trends_collectors.newsapi_collector import NewsAPICollector
from trends_collectors.reddit_collector import RedditCollector
from trends_collectors.news_collector import NewsCollector
from trends_collectors.demo_collector import DemoDataCollector

__all__ = [
    "BaseCollector",
    "create_content_item",
    "CollectorRegistry",
    "CollectionOrchestrator",
    "HackerNewsCollector",
    "NewsAPICollector",
    "RedditCollector",
    "NewsCollector",
    "DemoDataCollector",
]
