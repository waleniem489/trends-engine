"""
Keyword & Entity Extractor — Stages 3 & 4 of NLP Pipeline
===========================================================
Extracts meaningful keywords and named entities from text.

Two extractors in one module:
1. Keyword Extractor: Important terms for trend tracking
2. Entity Extractor: Named entities (brands, platforms, products)

Why not spaCy NER?
- spaCy needs a 50MB+ model download
- For our domain (marketing trends), pattern-based NER is more
  precise — we KNOW what entities matter (platforms, brands, tools)
- Faster, zero dependencies beyond regex

Production upgrade:
- Add spaCy for general NER
- Fine-tune on marketing corpus
- Add product/brand knowledge base
"""

import re
from collections import Counter


# ─── Keyword Extraction ──────────────────────────────────

# Common words to ignore (expanded for marketing domain)
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "don", "now", "and", "but", "or", "if", "this", "that",
    "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "it", "its", "they", "them", "their",
    "what", "which", "who", "whom", "up", "about", "also", "new", "one",
    "like", "get", "got", "make", "made", "really", "much", "still",
    "even", "back", "going", "well", "way", "look", "first", "see",
    "think", "know", "take", "come", "say", "said", "try", "tried",
    "using", "use", "right", "time", "year", "just", "good", "great",
}


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """
    Extract meaningful keywords from text.

    Uses word frequency with stop word removal and length filtering.
    Simple but effective for trend detection — we don't need TF-IDF
    per-document because topic assignment handles the intelligence.

    Parameters
    ----------
    text : str
        Cleaned text.
    top_n : int
        Max number of keywords to return.

    Returns
    -------
    list[str]
        Top keywords, ordered by frequency.
    """
    if not text:
        return []

    # Tokenize: split on non-alphanumeric, lowercase
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

    # Filter stop words and very short/long words
    meaningful = [
        w for w in words
        if w not in STOP_WORDS and 3 <= len(w) <= 30
    ]

    # Count and return top N
    counts = Counter(meaningful)
    return [word for word, _ in counts.most_common(top_n)]


# Also extract bigrams (two-word phrases) — important for compound terms
# like "oat milk", "email marketing", "cold plunge"
def extract_bigrams(text: str, top_n: int = 5) -> list[str]:
    """Extract top bigrams (two-word phrases)."""
    if not text:
        return []

    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    meaningful = [w for w in words if w not in STOP_WORDS]

    bigrams = [
        f"{meaningful[i]} {meaningful[i+1]}"
        for i in range(len(meaningful) - 1)
    ]

    counts = Counter(bigrams)
    return [bg for bg, _ in counts.most_common(top_n)]


# ─── Entity Extraction ───────────────────────────────────

# Pattern-based NER for marketing domain
# More precise than general NER for our use case

PLATFORM_PATTERNS = {
    "tiktok": r"\btik\s*tok\b",
    "instagram": r"\b(?:instagram|insta|ig)\b",
    "twitter": r"\b(?:twitter|x\.com|tweet)\b",
    "youtube": r"\b(?:youtube|yt|youtube shorts)\b",
    "reddit": r"\breddit\b",
    "linkedin": r"\blinkedin\b",
    "facebook": r"\b(?:facebook|meta|fb)\b",
    "pinterest": r"\bpinterest\b",
    "snapchat": r"\bsnapchat\b",
    "threads": r"\bthreads\b",
}

TOOL_PATTERNS = {
    "mailchimp": r"\bmailchimp\b",
    "hubspot": r"\bhubspot\b",
    "klaviyo": r"\bklaviyo\b",
    "shopify": r"\bshopify\b",
    "canva": r"\bcanva\b",
    "chatgpt": r"\b(?:chatgpt|chat\s*gpt|openai)\b",
    "claude": r"\bclaude\b",
    "midjourney": r"\bmidjourney\b",
    "notion": r"\bnotion\b",
    "wordpress": r"\bwordpress\b",
    "wix": r"\bwix\b",
    "squarespace": r"\bsquarespace\b",
}

BRAND_PATTERNS = {
    "starbucks": r"\bstarbucks\b",
    "nike": r"\bnike\b",
    "apple": r"\bapple\b",
    "google": r"\bgoogle\b",
    "amazon": r"\bamazon\b",
    "netflix": r"\bnetflix\b",
}


def extract_entities(text: str) -> dict:
    """
    Extract named entities using pattern matching.

    Returns entities grouped by type:
    - platforms: Social media platforms mentioned
    - tools: Marketing/business tools mentioned
    - brands: Major brands mentioned

    Parameters
    ----------
    text : str
        Cleaned text.

    Returns
    -------
    dict
        {"platforms": [...], "tools": [...], "brands": [...]}
    """
    if not text:
        return {"platforms": [], "tools": [], "brands": []}

    text_lower = text.lower()

    platforms = [
        name for name, pattern in PLATFORM_PATTERNS.items()
        if re.search(pattern, text_lower)
    ]

    tools = [
        name for name, pattern in TOOL_PATTERNS.items()
        if re.search(pattern, text_lower)
    ]

    brands = [
        name for name, pattern in BRAND_PATTERNS.items()
        if re.search(pattern, text_lower)
    ]

    return {
        "platforms": platforms,
        "tools": tools,
        "brands": brands,
    }
