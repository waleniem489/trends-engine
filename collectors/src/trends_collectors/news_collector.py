"""
News/RSS Collector — Web Scraping Data Source
=============================================
Collects marketing-related articles from public RSS feeds.
Zero API keys required. Proves web scraping collection pattern.

Why RSS for the prototype:
1. Free — no API key, no rate limits (be polite though)
2. Structured — feedparser handles XML/Atom/RSS2.0 automatically
3. Real content — actual articles with titles and summaries
4. Diverse — multiple publishers, different perspectives
5. Reliable — RSS feeds rarely go down

This collector demonstrates a different pattern than Reddit:
- Reddit: Authenticated API with rate limiting
- RSS: Unauthenticated web fetch with parsing
- Demo: In-memory generation
Three patterns = proves the pluggable architecture works.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Generator

import feedparser
from bs4 import BeautifulSoup

from .base import BaseCollector
from .schema import create_content_item

log = logging.getLogger(__name__)

# Marketing and business RSS feeds (all free, public)
DEFAULT_FEEDS = [
    {
        "url": "https://feeds.feedburner.com/CoppybloGger",
        "name": "Copyblogger",
        "category": "content_marketing",
    },
    {
        "url": "https://blog.hubspot.com/marketing/rss.xml",
        "name": "HubSpot Marketing",
        "category": "marketing",
    },
    {
        "url": "https://www.socialmediaexaminer.com/feed/",
        "name": "Social Media Examiner",
        "category": "social_media",
    },
    {
        "url": "https://contentmarketinginstitute.com/feed/",
        "name": "Content Marketing Institute",
        "category": "content_marketing",
    },
    {
        "url": "https://moz.com/devblog/feed",
        "name": "Moz",
        "category": "seo",
    },
    {
        "url": "https://feeds.feedburner.com/naborly",
        "name": "Neil Patel",
        "category": "marketing",
    },
    {
        "url": "https://www.searchenginejournal.com/feed/",
        "name": "Search Engine Journal",
        "category": "seo",
    },
    {
        "url": "https://techcrunch.com/feed/",
        "name": "TechCrunch",
        "category": "tech",
    },
    {
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "name": "BBC Business",
        "category": "business",
    },
]


class NewsCollector(BaseCollector):
    """
    Collects articles from public RSS feeds.
    Parses XML feeds, cleans HTML from summaries, yields ContentItems.
    """

    def __init__(
        self,
        feeds: list[dict] | None = None,
        max_articles_per_feed: int = 30,
    ):
        """
        Parameters
        ----------
        feeds : list[dict], optional
            Override default feeds. Each dict: {url, name, category}

        max_articles_per_feed : int
            Cap per feed to keep collection fast for demo.
        """
        super().__init__(name="news_rss", platform="news")
        self.feeds = feeds or DEFAULT_FEEDS
        self.max_articles_per_feed = max_articles_per_feed

    def collect(self) -> Generator[dict, None, None]:
        """
        Fetch and parse all configured RSS feeds.
        Yields ContentItems for each article found.
        """
        seen_urls = set()  # Dedup across feeds (syndicated articles)

        for feed_config in self.feeds:
            try:
                yield from self._fetch_feed(feed_config, seen_urls)
            except Exception as e:
                log.warning(f"Failed to fetch feed '{feed_config['name']}': {e}")
                continue

    def health_check(self) -> bool:
        """Check if at least one RSS feed is reachable."""
        for feed_config in self.feeds[:3]:  # Try first 3 only (speed)
            try:
                result = feedparser.parse(feed_config["url"])
                if result.entries:
                    return True
            except Exception:
                continue
        return False

    def get_config(self) -> dict:
        return {
            **super().get_config(),
            "feed_count": len(self.feeds),
            "feed_names": [f["name"] for f in self.feeds],
            "max_articles_per_feed": self.max_articles_per_feed,
        }

    # ── Internal methods ─────────────────────────────────────

    def _fetch_feed(
        self, feed_config: dict, seen_urls: set
    ) -> Generator[dict, None, None]:
        """Parse a single RSS feed and yield ContentItems."""
        feed = feedparser.parse(feed_config["url"])

        if feed.bozo and not feed.entries:
            log.warning(f"Malformed feed with no entries: {feed_config['name']}")
            return

        count = 0
        for entry in feed.entries:
            if count >= self.max_articles_per_feed:
                break

            try:
                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                # Extract and clean text
                title = entry.get("title", "").strip()
                summary = self._clean_html(
                    entry.get("summary", entry.get("description", ""))
                )
                text = f"{title}. {summary}" if summary else title

                if len(text.strip()) < 20:
                    continue

                # Parse published date
                published_at = self._parse_date(entry)

                # Generate stable content ID from URL
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                source_slug = feed_config["name"].lower().replace(" ", "_")[:10]

                yield create_content_item(
                    content_id=f"news_{source_slug}_{url_hash}",
                    source_platform="news",
                    source_url=url,
                    content_text=text[:3000],  # Cap at 3K chars for very long articles
                    published_at=published_at,
                    author=entry.get("author", feed_config["name"]),
                    engagement={
                        "likes": 0,
                        "comments": 0,
                        "shares": 0,
                        "views": 0,  # RSS doesn't provide engagement
                    },
                    metadata={
                        "source_name": feed_config["name"],
                        "category": feed_config["category"],
                        "tags": [
                            tag["term"]
                            for tag in entry.get("tags", [])
                            if "term" in tag
                        ][:10],  # Cap tags
                    },
                    content_type="article",
                    language="en",
                )
                count += 1

            except Exception as e:
                log.debug(f"Skipping entry in {feed_config['name']}: {e}")
                continue

    def _clean_html(self, raw_html: str) -> str:
        """Strip HTML tags from RSS content, return plain text."""
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        # Collapse multiple whitespace
        return " ".join(text.split())

    def _parse_date(self, entry) -> str:
        """
        Extract publication date from RSS entry.
        Handles multiple date formats across different feeds.
        Falls back to current time if unparseable.
        """
        # feedparser normalizes dates into published_parsed (time.struct_time)
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")

        if time_struct:
            try:
                dt = datetime(*time_struct[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass

        # Fallback: use current time
        return datetime.now(timezone.utc).isoformat()
