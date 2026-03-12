"""
Demo Data Collector — Crafted Trend Story
==========================================
Generates pre-crafted content items that produce a compelling
cortado trend lifecycle when fed through the pipeline.

This is NOT cheating — it's test fixture design. Every good system
has test data that exercises important code paths. This data exercises
the trend lifecycle (EMERGING → GROWING → PEAKING → DECLINING).

The demo data tells a specific 10-day story:
  Day 1-2:  Baseline — cortado mentioned occasionally (~10-15/day)
  Day 3:    Spark — a TikTok video goes semi-viral (~25/day)
  Day 4-5:  Growth — Reddit/news pick it up (~40-80/day)
  Day 6-7:  Peak — everywhere, every platform (~150-200/day)
  Day 8-9:  Decline — mentions dropping (~80-50/day)
  Day 10:   Settling — becoming evergreen (~30/day)

Meanwhile, 4 other topics maintain steady baselines so cortado
stands out as the clear trend.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Generator

from .base import BaseCollector
from .schema import create_content_item


class DemoDataCollector(BaseCollector):
    """
    Generates synthetic content items for demo purposes.
    Uses the same ContentItem schema as live collectors.
    Downstream pipeline can't tell the difference.
    """

    def __init__(self, days: int = 10, seed: int = 42):
        """
        Parameters
        ----------
        days : int
            Number of days of historical data to generate.
        seed : int
            Random seed for reproducible demo data.
        """
        super().__init__(name="demo_data", platform="demo")
        self.days = days
        self.seed = seed

    def collect(self) -> Generator[dict, None, None]:
        """Generate all demo content items across the full time range."""
        random.seed(self.seed)
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=self.days)

        # ── Generate content for each topic ──
        for topic_name, topic_config in TOPIC_SCENARIOS.items():
            for item in self._generate_topic_items(topic_name, topic_config, start, now):
                yield item

    def health_check(self) -> bool:
        """Demo data is always available."""
        return True

    def get_config(self) -> dict:
        return {
            **super().get_config(),
            "days": self.days,
            "seed": self.seed,
            "topics": list(TOPIC_SCENARIOS.keys()),
        }

    # ── Internal generators ──────────────────────────────────

    def _generate_topic_items(
        self, topic_name: str, config: dict, start: datetime, end: datetime
    ) -> Generator[dict, None, None]:
        """
        Generate content items for a single topic across the time range.

        Uses the volume_curve to determine how many posts per day,
        then creates realistic-looking posts spread across each day.
        """
        templates = config["templates"]
        platforms = config["platforms"]
        volume_curve = config["volume_curve"]  # posts per day, by day index

        for day_offset in range(len(volume_curve)):
            day_start = start + timedelta(days=day_offset)
            if day_start > end:
                break

            posts_today = volume_curve[day_offset]

            for i in range(posts_today):
                # Spread posts across the day with some clustering
                hour = self._weighted_hour()
                minute = random.randint(0, 59)
                published = day_start.replace(
                    hour=hour, minute=minute, second=random.randint(0, 59)
                )

                platform = random.choice(platforms)
                template = random.choice(templates)
                text = self._fill_template(template, topic_name)

                # Engagement scales roughly with trend velocity
                engagement_multiplier = max(1, posts_today / 15)
                engagement = self._generate_engagement(platform, engagement_multiplier)

                try:
                    item = create_content_item(
                        content_id=f"demo_{topic_name}_{day_offset:02d}_{i:04d}",
                        source_platform=platform,
                        source_url=f"https://demo.example.com/{topic_name}/{day_offset}/{i}",
                        content_text=text,
                        published_at=published.isoformat(),
                        author=f"demo_user_{random.randint(1000, 9999)}",
                        engagement=engagement,
                        metadata={
                            "scenario": "demo",
                            "topic": topic_name,
                            "day_number": day_offset + 1,
                            "is_demo": True,
                        },
                        content_type="post",
                        language="en",
                    )
                    yield item
                except ValueError:
                    continue  # Skip if template produced too-short text

    def _weighted_hour(self) -> int:
        """
        Generate posting hour weighted toward business hours.
        Social media activity peaks 8-10 AM and 7-9 PM.
        """
        weights = [
            1, 1, 1, 1, 1, 2,  # 0-5 AM (low)
            3, 5, 8, 9, 8, 7,  # 6-11 AM (morning peak)
            6, 6, 5, 5, 5, 6,  # 12-5 PM (afternoon)
            7, 8, 9, 7, 4, 2,  # 6-11 PM (evening peak)
        ]
        return random.choices(range(24), weights=weights, k=1)[0]

    def _fill_template(self, template: str, topic_name: str) -> str:
        """Fill in template placeholders with contextual details."""
        display_name = topic_name.replace("_", " ")
        adjectives = ["amazing", "incredible", "trending", "popular", "viral",
                       "game-changing", "must-try", "everyone's favorite"]
        actions = ["tried", "discovered", "made", "ordered", "found"]
        sources = ["TikTok", "Instagram", "my feed", "a friend", "a blog post"]

        return template.format(
            topic=display_name,
            adj=random.choice(adjectives),
            action=random.choice(actions),
            source=random.choice(sources),
        )

    def _generate_engagement(self, platform: str, multiplier: float) -> dict:
        """Generate realistic engagement metrics scaled by trend intensity."""
        base = {
            "reddit":    {"likes": 25, "comments": 8, "shares": 3, "views": 0},
            "news":      {"likes": 0, "comments": 2, "shares": 15, "views": 500},
            "twitter":   {"likes": 40, "comments": 5, "shares": 12, "views": 800},
            "instagram": {"likes": 80, "comments": 12, "shares": 5, "views": 1200},
            "demo":      {"likes": 20, "comments": 5, "shares": 3, "views": 200},
        }

        metrics = base.get(platform, base["demo"])
        return {
            k: int(v * multiplier * random.uniform(0.5, 2.0))
            for k, v in metrics.items()
        }


# ═══════════════════════════════════════════════════════════════
# TOPIC SCENARIOS — The heart of the demo data
# ═══════════════════════════════════════════════════════════════
# Each topic has:
#   - volume_curve: posts per day for each day (drives the trend shape)
#   - templates: realistic post text templates
#   - platforms: which platforms these posts "come from"

TOPIC_SCENARIOS = {
    # ═══════════════════════════════════════════════════════════
    # Each volume_curve entry = posts per day.
    # Curves auto-truncate to `days` param (default 10).
    # Use --demo-days 30 to see full 30-day story.
    #
    # HOW TO ADD A NEW TOPIC:
    #   1. Pick a unique key (e.g., "cold_plunge")
    #   2. Write a volume_curve (list of ints, one per day)
    #   3. Pick platforms it would appear on
    #   4. Write 5-15 realistic templates using {topic}, {adj}, {action}, {source}
    #   5. Add matching entry in nlp/taxonomy.py so topic assignment works
    #
    # TREND SHAPES CHEAT SHEET:
    #   Spike:     [10, 10, 10, 80, 200, 150, 60, 20, 10, 10]
    #   Gradual:   [10, 12, 15, 18, 22, 27, 33, 40, 48, 55]
    #   Seasonal:  [5, 10, 25, 50, 70, 60, 40, 20, 10, 5]
    #   Decline:   [50, 45, 38, 30, 22, 18, 14, 10, 8, 6]
    #   Flat:      [30, 28, 32, 30, 29, 31, 28, 33, 30, 31]
    #   Double:    [10, 40, 20, 10, 60, 120, 80, 30, 15, 10]
    # ═══════════════════════════════════════════════════════════

    # ── THE STAR: Cortado (clear lifecycle, EMERGING→PEAKING→DECLINING) ──
    "cortado": {
        "volume_curve": [
            8, 10, 10, 12, 11, 10, 12, 15,       # D1-8:  baseline (~10/day)
            20, 28, 38, 50, 70, 95, 130,           # D9-15: spark → growth
            175, 210, 240, 220, 195,                # D16-20: PEAK zone
            160, 120, 85, 60, 45, 35, 28, 22, 18, 15,  # D21-30: decline → settle
        ],
        "platforms": ["reddit", "twitter", "instagram", "news"],
        "templates": [
            "Just {action} a cortado for the first time — {adj}!",
            "The cortado trend is real. Saw it on {source} and had to try it.",
            "My cafe just added cortados to the menu. Customers love them.",
            "Cortado recipe: equal parts espresso and steamed milk. Simple but {adj}.",
            "Is it just me or is everyone drinking cortados now? Saw it on {source}.",
            "Cortado vs flat white — what's the difference? The {topic} is smaller and stronger.",
            "Added cortados to our coffee shop menu last week. Already our #3 seller.",
            "The {adj} cortado trend — why this Spanish coffee drink is taking over.",
            "Tried making a cortado at home after seeing it on {source}. Not as easy as it looks!",
            "Our cortado sales are up 300% this month. Thank you {source}.",
            "The perfect afternoon pick-me-up: a cortado. Discovered thanks to {source}.",
            "Small but mighty — the cortado is the espresso drink of 2026.",
            "Why every coffee shop needs to add cortado to their menu right now.",
            "Just launched a cortado special at our cafe. The response has been {adj}.",
            "Marketing tip: if your audience loves coffee, the cortado trend is your content goldmine.",
        ],
    },

    # ── STEADY BASELINE: Oat milk (flat, evergreen — control topic) ──
    "oat_milk": {
        "volume_curve": [
            30, 28, 32, 30, 29, 31, 28, 33, 30, 31,
            29, 32, 30, 28, 31, 30, 33, 29, 31, 30,
            28, 32, 30, 31, 29, 30, 32, 28, 31, 30,
        ],
        "platforms": ["reddit", "news", "instagram"],
        "templates": [
            "Switched to oat milk in my coffee. Never going back.",
            "Oat milk market continues steady growth in the dairy alternative space.",
            "Best oat milk brands for coffee: our top picks for baristas.",
            "Oat milk is now standard at most cafes. The {topic} revolution is complete.",
            "New oat milk product launch — thicker barista edition for better foam.",
        ],
    },

    # ── SLOW GROWER: AI email tools (gradual uptrend over 30 days) ──
    "ai_email_tools": {
        "volume_curve": [
            12, 13, 14, 14, 15, 16, 16, 17, 18, 19,
            20, 21, 22, 23, 24, 26, 27, 29, 31, 33,
            35, 37, 40, 42, 45, 48, 50, 53, 56, 60,
        ],
        "platforms": ["reddit", "news", "twitter"],
        "templates": [
            "Using AI to write email campaigns now. Saves hours every week.",
            "AI email marketing tools comparison: which one actually works?",
            "Our open rates went up 15% after using AI-generated subject lines.",
            "The AI email tools landscape is getting crowded. Here's what stands out.",
            "Marketers are split on AI-written emails. Our test results were {adj}.",
            "AI tools for small business email marketing — a practical guide.",
            "Just tested 5 AI email writers. Here's the honest ranking.",
            "AI email personalization is getting scary good. Saw an example on {source}.",
        ],
    },

    # ── SEASONAL: Spring collection (predictable bell curve) ──
    "spring_collection": {
        "volume_curve": [
            3, 4, 5, 6, 8, 10, 13, 18, 25, 35,
            48, 62, 75, 85, 90, 88, 80, 68, 55, 42,
            30, 22, 15, 10, 8, 6, 5, 4, 3, 3,
        ],
        "platforms": ["instagram", "news", "twitter"],
        "templates": [
            "Spring collection 2026 is here! New arrivals just dropped.",
            "Email campaign ideas for your spring collection launch.",
            "Spring fashion trends: what your audience wants to see in their inbox.",
            "Planning our spring collection email series. Starting with a teaser campaign.",
            "Spring is the best time for re-engagement campaigns. Fresh content, fresh start.",
            "Our spring collection email had a 38% open rate. Here's what we did differently.",
        ],
    },

    # ── DECLINING: NFT marketing (fading away over 30 days) ──
    "nft_marketing": {
        "volume_curve": [
            45, 42, 40, 38, 35, 33, 30, 28, 26, 24,
            22, 20, 18, 16, 15, 14, 13, 12, 11, 10,
            9, 8, 8, 7, 7, 6, 6, 5, 5, 5,
        ],
        "platforms": ["reddit", "twitter"],
        "templates": [
            "NFT marketing strategies that still work in 2026.",
            "The NFT hype has cooled but some brands are still finding success.",
            "Should you still include NFTs in your marketing strategy?",
            "NFT marketing budgets are shrinking. Where should you reallocate?",
            "Lessons learned from the NFT marketing wave — a retrospective.",
        ],
    },

    # ═══════════════════════════════════════════════════════════
    # NEW TOPICS BELOW
    # ═══════════════════════════════════════════════════════════

    # ── VIRAL SPIKE: Short-form video (sudden explosion, fast decay) ──
    "short_form_video": {
        "volume_curve": [
            15, 14, 16, 15, 18, 20, 22, 25, 30, 42,
            65, 110, 190, 280, 250, 180, 120, 75, 50, 38,
            28, 22, 18, 16, 15, 14, 13, 14, 13, 14,
        ],
        "platforms": ["twitter", "instagram", "reddit", "news"],
        "templates": [
            "Short-form video is dominating every platform right now.",
            "Our Reels got 10x the reach of static posts. Short-form video is king.",
            "YouTube Shorts just overtook TikTok in our engagement metrics.",
            "Short-form video marketing guide: how to get started in 2026.",
            "Every brand needs a short-form video strategy. Here's why.",
            "We switched our content calendar to 80% short-form video. Results were {adj}.",
            "The short-form video trend is not slowing down. Saw this stat on {source}.",
            "Reels vs TikTok vs Shorts: which short-form video platform wins for marketing?",
            "Our client's short-form video campaign went viral — 2M views in 48 hours.",
        ],
    },

    # ── DOUBLE PEAK: Micro-influencer (two waves of interest) ──
    "micro_influencer": {
        "volume_curve": [
            12, 15, 22, 38, 55, 70, 60, 40, 25, 18,
            15, 14, 16, 20, 30, 48, 72, 95, 110, 100,
            78, 55, 38, 28, 20, 16, 14, 13, 12, 12,
        ],
        "platforms": ["instagram", "twitter", "news"],
        "templates": [
            "Micro-influencers outperform mega-influencers 3:1 on engagement.",
            "Our micro-influencer campaign had better ROI than paid ads.",
            "Finding the right micro-influencer for your brand: a complete guide.",
            "Micro-influencer marketing is the most underrated strategy of 2026.",
            "We spent $500 on micro-influencers vs $5000 on ads. Guess which won?",
            "Nano and micro-influencer partnerships are {adj} for small businesses.",
            "The micro-influencer trend just hit our industry. Saw it on {source}.",
        ],
    },

    # ── EMERGING (hasn't peaked yet): Walking pad / desk treadmill ──
    "walking_pad": {
        "volume_curve": [
            3, 3, 4, 4, 5, 5, 6, 7, 8, 9,
            10, 12, 14, 16, 19, 22, 26, 30, 35, 40,
            46, 52, 60, 68, 78, 88, 100, 112, 126, 140,
        ],
        "platforms": ["reddit", "instagram", "twitter", "news"],
        "templates": [
            "Just got a walking pad for my home office. Game changer.",
            "Walking pad sales are exploding. Everyone wants one now.",
            "Under-desk treadmill review: is the walking pad worth it?",
            "My walking pad helps me hit 10K steps while working. {adj}!",
            "The walking pad trend is real. Saw it recommended on {source}.",
            "Best walking pads for small home offices — 2026 buyer's guide.",
            "Walking pad + standing desk = the ultimate WFH setup.",
            "Our wellness brand just launched a walking pad campaign. Results are {adj}.",
        ],
    },

    # ── STEADY HIGH: Email personalization (consistently popular) ──
    "email_personalization": {
        "volume_curve": [
            55, 58, 52, 56, 60, 54, 57, 59, 53, 58,
            56, 60, 55, 57, 62, 58, 54, 59, 56, 61,
            57, 55, 60, 58, 56, 59, 57, 61, 55, 58,
        ],
        "platforms": ["news", "reddit", "twitter"],
        "templates": [
            "Email personalization is no longer optional — it's expected.",
            "Dynamic content blocks increased our click rate by 22%.",
            "Email personalization beyond first name: behavioral triggers that work.",
            "Hyper-personalized emails convert 3x better. Here are the numbers.",
            "Segmentation + personalization = email marketing gold.",
            "The best email personalization tools for marketers in 2026.",
        ],
    },

    # ── SUDDEN CRASH: UGC marketing (was growing, then controversy killed it) ──
    "ugc_marketing": {
        "volume_curve": [
            20, 22, 25, 30, 38, 48, 62, 80, 95, 110,
            125, 135, 140, 130, 100, 60, 30, 20, 15, 12,
            10, 10, 9, 9, 8, 8, 8, 7, 7, 7,
        ],
        "platforms": ["instagram", "twitter", "reddit"],
        "templates": [
            "UGC is the most authentic content you can put in your emails.",
            "User-generated content campaigns: how to get customers to create for you.",
            "Our UGC campaign generated 500+ customer photos in one week.",
            "UGC creators are the new influencers. Every brand needs them.",
            "How to run a successful UGC campaign on Instagram.",
            "UGC marketing best practices: legal, ethical, and {adj} results.",
            "Is UGC still worth it? The latest data says yes — saw it on {source}.",
        ],
    },

    # ── LOCAL SEO: Gradual growth with weekend spikes ──
    "local_seo": {
        "volume_curve": [
            10, 12, 8, 9, 10, 18, 20, 11, 13, 9,
            10, 11, 20, 22, 12, 14, 10, 11, 12, 24,
            26, 14, 16, 12, 13, 14, 28, 30, 16, 18,
        ],
        "platforms": ["reddit", "news", "twitter"],
        "templates": [
            "Local SEO is the single best investment for small businesses.",
            "Updated your Google Business Profile lately? Local SEO starts there.",
            "Local search is how 78% of customers find nearby businesses.",
            "Local SEO tips: how to rank #1 in Google Maps for your area.",
            "Small business local SEO checklist for 2026.",
            "Combining email marketing with local SEO for maximum local reach.",
        ],
    },

    # ── SUSTAINABLE FASHION: Slow steady rise ──
    "sustainable_fashion": {
        "volume_curve": [
            8, 9, 9, 10, 10, 11, 12, 12, 13, 14,
            15, 16, 17, 18, 19, 20, 22, 23, 25, 27,
            29, 31, 33, 36, 38, 41, 44, 47, 50, 54,
        ],
        "platforms": ["instagram", "news", "twitter", "reddit"],
        "templates": [
            "Sustainable fashion is no longer niche — it's mainstream.",
            "Consumers want eco-friendly brands. Sustainable fashion delivers.",
            "Our sustainable fashion email campaign had the highest engagement ever.",
            "Slow fashion is the future. Here's how to market it.",
            "Sustainable fashion brands are winning on Instagram. Seen on {source}.",
            "Eco-friendly fashion marketing: authenticity beats greenwashing every time.",
            "The sustainable fashion movement is {adj} and growing fast.",
        ],
    },
}

