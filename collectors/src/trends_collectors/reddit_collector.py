"""
Reddit Collector — Live API Data Source
========================================
Collects marketing-related posts from Reddit using PRAW.
Free tier, 100 req/min, rich engagement data.

Reddit is our primary live data source because:
1. Free (OAuth, no paid tier needed)
2. Rich engagement metrics (upvotes, comments, awards)
3. Marketing-specific subreddits exist
4. Real conversations (not just promotional content)
5. 100 req/min is generous enough for demo

Authentication:
- Requires Reddit app credentials (free, 2 min setup)
- Create at: https://www.reddit.com/prefs/apps/
- Select "script" type application
"""

import logging
from datetime import datetime, timezone
from typing import Generator

from .base import BaseCollector
from .schema import create_content_item

log = logging.getLogger(__name__)

# Subreddits relevant to marketing and small business
MARKETING_SUBREDDITS = [
    "marketing",
    "socialmedia",
    "emailmarketing",
    "digital_marketing",
    "ecommerce",
    "smallbusiness",
    "entrepreneur",
    "startups",
    "content_marketing",
    "SEO",
    "copywriting",
    "shopify",
    "SaaS",
    "coffee",
    "barista",
]


class RedditCollector(BaseCollector):
    """
    Collects posts from marketing-related subreddits via Reddit API.

    Fetches both 'hot' (popular right now) and 'new' (fresh content)
    to capture both trending discussions and emerging topics.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str = "TrendsEngine/1.0",
        subreddits: list[str] | None = None,
        posts_per_subreddit: int = 50,
    ):
        """
        Parameters
        ----------
        client_id, client_secret : str
            Reddit API credentials from https://www.reddit.com/prefs/apps/

        user_agent : str
            Required by Reddit API. Identifies our application.

        subreddits : list[str], optional
            Override default marketing subreddits.

        posts_per_subreddit : int
            Max posts to fetch per subreddit per sort type (hot/new).
        """
        super().__init__(name="reddit", platform="reddit")
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.subreddits = subreddits or MARKETING_SUBREDDITS
        self.posts_per_subreddit = posts_per_subreddit
        self._reddit = None

    def _get_reddit(self):
        """Lazy-initialize PRAW client (avoids import failure if praw not installed)."""
        if self._reddit is None:
            import praw

            self._reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
        return self._reddit

    def collect(self) -> Generator[dict, None, None]:
        """
        Collect recent posts from all configured subreddits.

        Fetches 'hot' posts (what's popular now) and 'new' posts
        (freshly submitted). Deduplicates by post ID.

        Yields ContentItem dicts conforming to universal schema.
        """
        reddit = self._get_reddit()
        seen_ids = set()  # Dedup across hot/new within this run

        for subreddit_name in self.subreddits:
            try:
                subreddit = reddit.subreddit(subreddit_name)

                # Fetch hot posts (currently popular)
                yield from self._fetch_posts(
                    subreddit.hot(limit=self.posts_per_subreddit),
                    subreddit_name,
                    seen_ids,
                    sort_type="hot",
                )

                # Fetch new posts (freshly submitted — for early trend detection)
                yield from self._fetch_posts(
                    subreddit.new(limit=self.posts_per_subreddit),
                    subreddit_name,
                    seen_ids,
                    sort_type="new",
                )

            except Exception as e:
                # Don't let one failing subreddit kill the whole run
                log.warning(f"Failed to collect from r/{subreddit_name}: {e}")
                continue

    def health_check(self) -> bool:
        """Verify Reddit API is reachable by fetching one post."""
        try:
            reddit = self._get_reddit()
            # Just check if we can reach the API
            next(reddit.subreddit("marketing").hot(limit=1))
            return True
        except Exception as e:
            log.error(f"Reddit health check failed: {e}")
            return False

    def get_config(self) -> dict:
        return {
            **super().get_config(),
            "subreddits": self.subreddits,
            "subreddit_count": len(self.subreddits),
            "posts_per_subreddit": self.posts_per_subreddit,
        }

    # ── Internal methods ─────────────────────────────────────

    def _fetch_posts(
        self, posts, subreddit_name: str, seen_ids: set, sort_type: str
    ) -> Generator[dict, None, None]:
        """
        Process a batch of Reddit posts into ContentItems.
        Handles errors per-post — one bad post doesn't stop collection.
        """
        for post in posts:
            try:
                # Dedup: skip if already seen in this collection run
                if post.id in seen_ids:
                    continue
                seen_ids.add(post.id)

                # Skip NSFW content (brand safety)
                if post.over_18:
                    continue

                # Build content text: title + body for self posts
                text = post.title
                if post.is_self and post.selftext:
                    text = f"{post.title}. {post.selftext}"

                # Skip very short posts (not useful for NLP)
                if len(text.strip()) < 20:
                    continue

                yield create_content_item(
                    content_id=f"reddit_{post.id}",
                    source_platform="reddit",
                    source_url=f"https://reddit.com{post.permalink}",
                    content_text=text,
                    published_at=datetime.fromtimestamp(
                        post.created_utc, tz=timezone.utc
                    ).isoformat(),
                    author=post.author.name if post.author else "[deleted]",
                    engagement={
                        "likes": post.score,
                        "comments": post.num_comments,
                        "shares": 0,  # Reddit doesn't expose crosspost count easily
                        "views": 0,   # Not available via API
                    },
                    metadata={
                        "subreddit": subreddit_name,
                        "sort_type": sort_type,
                        "flair": post.link_flair_text,
                        "is_self": post.is_self,
                        "upvote_ratio": post.upvote_ratio,
                        "awards": post.total_awards_received,
                    },
                    content_type="post",
                    language="en",  # Assuming English; NLP pipeline will verify
                )

            except Exception as e:
                log.debug(f"Skipping post {getattr(post, 'id', '?')}: {e}")
                continue
