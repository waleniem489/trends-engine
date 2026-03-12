"""
Hacker News Collector — Zero Auth API Source
=============================================
Collects stories from Hacker News Firebase API.
No API key. No rate limits. No auth. Just fetch.

HN is valuable for the Trends Engine because:
1. Tech-savvy early adopters spot trends before mainstream
2. Rich engagement data (points, comments)
3. Completely free and reliable API
4. Stories span tech, business, marketing, startups
5. Firebase API is fast and well-documented

API docs: https://github.com/HackerNews/API

Collection strategy:
- Fetch top/new/best story IDs (returns ~500 IDs each)
- Fetch individual story details
- Filter for marketing/business relevance via keyword scan
- Also fetch "Ask HN" and "Show HN" posts (high signal content)
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Generator

import requests

from .base import BaseCollector
from .schema import create_content_item

log = logging.getLogger(__name__)

HN_BASE = "https://hacker-news.firebaseio.com/v0"

# Keywords that signal marketing/business relevance
# Broad enough to catch trends, narrow enough to filter noise
RELEVANCE_KEYWORDS = {
    # Marketing
    "marketing", "email", "newsletter", "campaign", "brand", "content",
    "social media", "seo", "advertising", "ad tech", "growth",
    "engagement", "conversion", "audience", "subscriber",
    # Business / SMB
    "small business", "startup", "ecommerce", "e-commerce", "shopify",
    "saas", "b2b", "b2c", "customer", "retention", "churn",
    # Trends / Culture
    "trend", "viral", "tiktok", "instagram", "influencer",
    "ai", "gpt", "llm", "chatbot", "automation",
    # Food & Lifestyle (for cortado-style trends)
    "coffee", "food", "restaurant", "recipe", "wellness", "fitness",
}


class HackerNewsCollector(BaseCollector):
    """
    Collects stories from Hacker News.
    Zero auth required. Fetches top + new stories in parallel.
    """

    def __init__(
        self,
        max_stories: int = 200,
        filter_relevant: bool = True,
        workers: int = 10,
    ):
        """
        Parameters
        ----------
        max_stories : int
            Max story IDs to fetch from each endpoint (top/new).
            HN returns up to 500 per endpoint.

        filter_relevant : bool
            If True, only yield stories matching RELEVANCE_KEYWORDS.
            If False, yield everything (useful for broad trend detection).

        workers : int
            Thread pool size for parallel story fetching.
            Each story = 1 HTTP request, so parallelism helps a lot.
        """
        super().__init__(name="hackernews", platform="hackernews")
        self.max_stories = max_stories
        self.filter_relevant = filter_relevant
        self.workers = workers
        self._session = requests.Session()

    def collect(self) -> Generator[dict, None, None]:
        """
        Fetch top and new stories, process in parallel,
        yield ContentItems for relevant stories.
        """
        seen_ids = set()

        # Fetch story IDs from both endpoints
        for endpoint in ["topstories", "newstories"]:
            try:
                story_ids = self._fetch_story_ids(endpoint)
                log.info(f"HN {endpoint}: {len(story_ids)} IDs fetched")
            except Exception as e:
                log.warning(f"Failed to fetch HN {endpoint}: {e}")
                continue

            # Fetch story details in parallel
            stories = self._fetch_stories_parallel(story_ids)

            for story in stories:
                if story and story.get("id") not in seen_ids:
                    seen_ids.add(story["id"])
                    item = self._story_to_content_item(story, endpoint)
                    if item:
                        yield item

    def health_check(self) -> bool:
        """Check if HN API is reachable."""
        try:
            resp = self._session.get(f"{HN_BASE}/topstories.json", timeout=5)
            return resp.status_code == 200 and len(resp.json()) > 0
        except Exception as e:
            log.error(f"HN health check failed: {e}")
            return False

    def get_config(self) -> dict:
        return {
            **super().get_config(),
            "max_stories": self.max_stories,
            "filter_relevant": self.filter_relevant,
            "workers": self.workers,
        }

    # ── Internal methods ─────────────────────────────────────

    def _fetch_story_ids(self, endpoint: str) -> list[int]:
        """Fetch story IDs from an HN endpoint."""
        resp = self._session.get(f"{HN_BASE}/{endpoint}.json", timeout=10)
        resp.raise_for_status()
        ids = resp.json()
        return ids[: self.max_stories]

    def _fetch_story(self, story_id: int) -> dict | None:
        """Fetch a single story's details."""
        try:
            resp = self._session.get(
                f"{HN_BASE}/item/{story_id}.json", timeout=5
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _fetch_stories_parallel(self, story_ids: list[int]) -> list[dict]:
        """Fetch multiple stories in parallel using thread pool."""
        stories = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self._fetch_story, sid): sid
                for sid in story_ids
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    stories.append(result)
        return stories

    def _is_relevant(self, text: str) -> bool:
        """Check if story text contains marketing/business keywords."""
        if not self.filter_relevant:
            return True
        text_lower = text.lower()
        return any(kw in text_lower for kw in RELEVANCE_KEYWORDS)

    def _story_to_content_item(self, story: dict, source_endpoint: str) -> dict | None:
        """Convert an HN story dict to a ContentItem."""
        try:
            # Skip non-story items (comments, polls, jobs)
            if story.get("type") != "story":
                return None

            # Build text from title + optional text body (Ask HN posts)
            title = story.get("title", "").strip()
            body = story.get("text", "")  # Only present for Ask HN / text posts
            if body:
                # HN text posts contain HTML
                from bs4 import BeautifulSoup
                body = BeautifulSoup(body, "html.parser").get_text(separator=" ", strip=True)

            text = f"{title}. {body}" if body else title

            if len(text.strip()) < 15:
                return None

            # Relevance filter
            if not self._is_relevant(text):
                return None

            # Parse timestamp
            created_utc = story.get("time", 0)
            published_at = datetime.fromtimestamp(
                created_utc, tz=timezone.utc
            ).isoformat()

            return create_content_item(
                content_id=f"hn_{story['id']}",
                source_platform="hackernews",
                source_url=story.get("url", f"https://news.ycombinator.com/item?id={story['id']}"),
                content_text=text,
                published_at=published_at,
                author=story.get("by", "unknown"),
                engagement={
                    "likes": story.get("score", 0),
                    "comments": story.get("descendants", 0),
                    "shares": 0,
                    "views": 0,
                },
                metadata={
                    "hn_id": story["id"],
                    "source_endpoint": source_endpoint,
                    "story_type": "ask_hn" if title.startswith("Ask HN") else
                                  "show_hn" if title.startswith("Show HN") else
                                  "link",
                    "domain": story.get("url", "").split("/")[2] if "url" in story and "/" in story.get("url", "") else "self",
                },
                content_type="post",
                language="en",
            )

        except Exception as e:
            log.debug(f"Skipping HN story {story.get('id', '?')}: {e}")
            return None
