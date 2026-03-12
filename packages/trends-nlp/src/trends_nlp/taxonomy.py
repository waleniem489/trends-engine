"""
Topic Taxonomy — What We Track
================================
Predefined list of topics the Trends Engine monitors.
Each topic has keywords for matching, a category, and industry tags.

Why predefined (not auto-discovered)?
- Speed: Keyword match is nanoseconds vs 25ms for embedding
- Reliability: Deterministic for demo
- Explainability: Easy to debug why a post was assigned to "cortado"
- Control: Marketers care about THESE topics, not random clusters

Production evolution:
- Phase 1 (prototype): This static taxonomy
- Phase 2: BERTopic nightly on unmatched posts → discovers new topics
- Phase 3: Per-user custom taxonomies based on their industry

Adding a new topic = one dict entry. Zero code changes downstream.
"""

# Each topic:
#   name:         Display name (used in dashboard, alerts)
#   keywords:     Terms that trigger assignment (case-insensitive)
#   category:     Grouping for UI organization
#   industry:     Which business types care about this

TOPIC_TAXONOMY = [
    # ── Food & Beverage (cortado is our star) ──────────────
    {
        "topic_id": "cortado",
        "name": "Cortado Coffee",
        "keywords": ["cortado", "cortado coffee", "spanish coffee", "cortadito"],
        "category": "food_beverage",
        "industry": ["cafe", "restaurant", "food", "beverage"],
    },
    {
        "topic_id": "oat_milk",
        "name": "Oat Milk",
        "keywords": ["oat milk", "oatmilk", "oat milk latte", "oat creamer", "oat beverage"],
        "category": "food_beverage",
        "industry": ["cafe", "restaurant", "food", "beverage", "health"],
    },
    {
        "topic_id": "matcha",
        "name": "Matcha",
        "keywords": ["matcha", "matcha latte", "matcha tea", "matcha powder"],
        "category": "food_beverage",
        "industry": ["cafe", "restaurant", "food", "beverage", "health"],
    },
    {
        "topic_id": "sourdough",
        "name": "Sourdough",
        "keywords": ["sourdough", "sourdough bread", "sourdough starter", "artisan bread"],
        "category": "food_beverage",
        "industry": ["bakery", "restaurant", "food"],
    },

    # ── Marketing Strategies ──────────────────────────────
    {
        "topic_id": "ai_email_tools",
        "name": "AI Email Marketing Tools",
        "keywords": [
            "ai email", "ai marketing", "ai campaign", "ai subject line",
            "ai copywriting", "gpt email", "llm marketing", "ai newsletter",
            "ai-generated email", "ai content creation",
        ],
        "category": "marketing",
        "industry": ["all"],
    },
    {
        "topic_id": "short_form_video",
        "name": "Short-Form Video Marketing",
        "keywords": [
            "short form video", "short-form video", "reels", "tiktok marketing",
            "youtube shorts", "video marketing", "vertical video",
        ],
        "category": "marketing",
        "industry": ["all"],
    },
    {
        "topic_id": "ugc_marketing",
        "name": "User-Generated Content",
        "keywords": [
            "ugc", "user generated content", "user-generated content",
            "ugc creator", "ugc campaign", "customer content",
        ],
        "category": "marketing",
        "industry": ["ecommerce", "retail", "fashion"],
    },
    {
        "topic_id": "micro_influencer",
        "name": "Micro-Influencer Marketing",
        "keywords": [
            "micro influencer", "micro-influencer", "nano influencer",
            "nano-influencer", "small influencer", "influencer marketing",
        ],
        "category": "marketing",
        "industry": ["all"],
    },
    {
        "topic_id": "email_personalization",
        "name": "Email Personalization",
        "keywords": [
            "email personalization", "personalized email", "dynamic content",
            "segmentation", "hyper-personalization", "behavioral email",
        ],
        "category": "marketing",
        "industry": ["all"],
    },
    {
        "topic_id": "nft_marketing",
        "name": "NFT Marketing",
        "keywords": [
            "nft marketing", "nft campaign", "nft brand", "web3 marketing",
            "nft loyalty", "nft engagement",
        ],
        "category": "marketing",
        "industry": ["tech", "art", "gaming"],
    },

    # ── E-commerce & Retail ───────────────────────────────
    {
        "topic_id": "spring_collection",
        "name": "Spring Collection",
        "keywords": [
            "spring collection", "spring fashion", "spring arrivals",
            "spring launch", "spring campaign", "spring sale",
        ],
        "category": "ecommerce",
        "industry": ["fashion", "retail", "ecommerce"],
    },
    {
        "topic_id": "sustainable_fashion",
        "name": "Sustainable Fashion",
        "keywords": [
            "sustainable fashion", "eco fashion", "ethical fashion",
            "slow fashion", "circular fashion", "sustainable brand",
        ],
        "category": "ecommerce",
        "industry": ["fashion", "retail"],
    },

    # ── Wellness & Fitness ────────────────────────────────
    {
        "topic_id": "desk_yoga",
        "name": "Desk Yoga",
        "keywords": [
            "desk yoga", "office yoga", "chair yoga", "work stretches",
            "desk stretches", "workplace wellness",
        ],
        "category": "wellness",
        "industry": ["fitness", "health", "corporate"],
    },
    {
        "topic_id": "walking_pad",
        "name": "Walking Pad / Under-Desk Treadmill",
        "keywords": [
            "walking pad", "under desk treadmill", "desk treadmill",
            "walk and work", "treadmill desk",
        ],
        "category": "wellness",
        "industry": ["fitness", "health", "office"],
    },

    # ── Tech & Tools ──────────────────────────────────────
    {
        "topic_id": "no_code_tools",
        "name": "No-Code Tools",
        "keywords": [
            "no code", "no-code", "nocode", "low code", "low-code",
            "no code website", "no code app",
        ],
        "category": "tech",
        "industry": ["tech", "startup", "small_business"],
    },
    {
        "topic_id": "voice_search",
        "name": "Voice Search Optimization",
        "keywords": [
            "voice search", "voice seo", "voice assistant",
            "alexa marketing", "voice commerce", "voice optimization",
        ],
        "category": "tech",
        "industry": ["all"],
    },

    # ── Small Business ────────────────────────────────────
    {
        "topic_id": "local_seo",
        "name": "Local SEO",
        "keywords": [
            "local seo", "google business", "local search",
            "google maps marketing", "local listing", "local marketing",
        ],
        "category": "small_business",
        "industry": ["small_business", "restaurant", "retail"],
    },
    {
        "topic_id": "community_marketing",
        "name": "Community-Led Marketing",
        "keywords": [
            "community marketing", "community led", "community-led",
            "brand community", "community building", "community engagement",
        ],
        "category": "small_business",
        "industry": ["all"],
    },
]


def get_taxonomy() -> list[dict]:
    """Return the full topic taxonomy."""
    return TOPIC_TAXONOMY


def get_taxonomy_map() -> dict[str, dict]:
    """Return taxonomy indexed by topic_id for fast lookup."""
    return {t["topic_id"]: t for t in TOPIC_TAXONOMY}


def get_all_keywords() -> dict[str, str]:
    """
    Return flattened keyword → topic_id mapping.
    Used by the keyword matcher for O(1) lookup.

    Returns dict like: {"cortado": "cortado", "oat milk": "oat_milk", ...}
    """
    keyword_map = {}
    for topic in TOPIC_TAXONOMY:
        for keyword in topic["keywords"]:
            keyword_map[keyword.lower()] = topic["topic_id"]
    return keyword_map
