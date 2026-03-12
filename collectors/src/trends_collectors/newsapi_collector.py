"""
NewsAPI Collector — Authenticated API Source
=============================================
Collects news articles from NewsAPI.org.
Free tier: 100 requests/day, 1000+ sources.

Sign up (2 min): https://newsapi.org/register
Free tier limitations:
- 100 requests per day
- Articles up to 1 month old
- Developer use only (not commercial)

Perfect for prototype. Proves authenticated API pattern.

Collection strategy:
- Search for marketing-related queries
- Also fetch top headlines in business category
- Combine for breadth + relevance
"""

import logging
from datetime import datetime, timezone
import hashlib
from typing import Generator

import requests

from .base import BaseCollector
from .schema import create_content_item

log = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2"

# Search queries to find marketing/trend content
DEFAULT_QUERIES = [
    "marketing trends 2026",
    "email marketing",
    "social media trends",
    "small business marketing",
    "AI marketing tools",
    "ecommerce trends",
    "content marketing strategy",
    "coffee trend",
    "consumer trends",
]


class NewsAPICollector(BaseCollector):
    """
    Collects articles from NewsAPI.org.
    Requires free API key from https://newsapi.org/register

    Demonstrates authenticated API collection pattern
    (vs HN's no-auth and RSS's web scraping).
    """

    def __init__(
        self,
        api_key: str,
        queries: list[str] | None = None,
        articles_per_query: int = 20,
        include_headlines: bool = True,
    ):
        """
        Parameters
        ----------
        api_key : str
            NewsAPI key from https://newsapi.org/register

        queries : list[str], optional
            Search queries. Defaults to marketing/trend terms.

        articles_per_query : int
            Max articles per search query. NewsAPI max is 100.

        include_headlines : bool
            Also fetch top business headlines (broader coverage).
        """
        super().__init__(name="newsapi", platform="news")
        self.api_key = api_key
        self.queries = queries or DEFAULT_QUERIES
        self.articles_per_query = articles_per_query
        self.include_headlines = include_headlines
        self._session = requests.Session()
        self._session.headers["X-Api-Key"] = api_key

    def collect(self) -> Generator[dict, None, None]:
        """
        Run all search queries + optional headlines.
        Deduplicates across queries by URL.
        """
        seen_urls = set()

        # Search queries (targeted marketing content)
        for query in self.queries:
            try:
                articles = self._search(query)
                for article in articles:
                    url = article.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        item = self._article_to_content_item(article, query)
                        if item:
                            yield item
            except Exception as e:
                log.warning(f"NewsAPI search failed for '{query}': {e}")
                continue

        # Top headlines (broader coverage)
        if self.include_headlines:
            try:
                articles = self._top_headlines()
                for article in articles:
                    url = article.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        item = self._article_to_content_item(article, "headlines")
                        if item:
                            yield item
            except Exception as e:
                log.warning(f"NewsAPI headlines failed: {e}")

    def health_check(self) -> bool:
        """Verify API key is valid and API is reachable."""
        try:
            resp = self._session.get(
                f"{NEWSAPI_BASE}/top-headlines",
                params={"country": "us", "pageSize": 1},
                timeout=5,
            )
            data = resp.json()
            return data.get("status") == "ok"
        except Exception as e:
            log.error(f"NewsAPI health check failed: {e}")
            return False

    def get_config(self) -> dict:
        return {
            **super().get_config(),
            "query_count": len(self.queries),
            "queries": self.queries,
            "articles_per_query": self.articles_per_query,
            "include_headlines": self.include_headlines,
        }

    # ── Internal methods ─────────────────────────────────────

    def _search(self, query: str) -> list[dict]:
        """Search for articles matching a query."""
        resp = self._session.get(
            f"{NEWSAPI_BASE}/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": self.articles_per_query,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            log.warning(f"NewsAPI search error: {data.get('message', 'unknown')}")
            return []

        return data.get("articles", [])

    def _top_headlines(self) -> list[dict]:
        """Fetch top business headlines."""
        resp = self._session.get(
            f"{NEWSAPI_BASE}/top-headlines",
            params={
                "category": "business",
                "language": "en",
                "pageSize": 30,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])

    def _article_to_content_item(self, article: dict, source_query: str) -> dict | None:
        """Convert a NewsAPI article to a ContentItem."""
        try:
            title = (article.get("title") or "").strip()
            description = (article.get("description") or "").strip()
            content = (article.get("content") or "").strip()

            # Build best available text
            # NewsAPI truncates content at ~200 chars on free tier
            text_parts = [p for p in [title, description, content] if p]
            text = ". ".join(text_parts)

            # Remove "[+NNNN chars]" truncation markers
            if "[+" in text:
                text = text[:text.rfind("[+")]

            if len(text.strip()) < 20:
                return None

            # Parse date
            pub_date = article.get("publishedAt", "")
            if pub_date:
                published_at = pub_date  # Already ISO format from NewsAPI
            else:
                published_at = datetime.now(timezone.utc).isoformat()

            # Generate stable ID from URL
            url = article.get("url", "")
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]

            source_name = (article.get("source", {}).get("name") or "unknown")

            return create_content_item(
                content_id=f"newsapi_{url_hash}",
                source_platform="news",
                source_url=url,
                content_text=text[:3000],
                published_at=published_at,
                author=article.get("author") or source_name,
                engagement={
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "views": 0,
                },
                metadata={
                    "source_name": source_name,
                    "source_query": source_query,
                    "image_url": article.get("urlToImage"),
                    "category": "business" if source_query == "headlines" else "search",
                },
                content_type="article",
                language="en",
            )

        except Exception as e:
            log.debug(f"Skipping NewsAPI article: {e}")
            return None
