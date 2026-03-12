"""
Text Cleaner — Stage 1 of NLP Pipeline
========================================
Normalizes raw content text for downstream NLP stages.
Removes noise while preserving meaning.

Why a dedicated cleaning step?
- Different sources have different noise (HTML, URLs, emojis, markdown)
- Cleaning ONCE, correctly, prevents bugs in every downstream stage
- Sentiment analysis on "Check out https://t.co/xyz!!!!" gives wrong signal
"""

import re
import html


def clean_text(raw_text: str) -> str:
    """
    Clean raw content text for NLP processing.

    Steps (order matters):
    1. Decode HTML entities (&amp; → &)
    2. Remove URLs (they confuse keyword extraction)
    3. Remove @mentions (not useful for trend detection)
    4. Remove excessive hashtag symbols (keep the word)
    5. Collapse whitespace
    6. Strip leading/trailing whitespace

    Parameters
    ----------
    raw_text : str
        Raw text from any collector (Reddit, HN, RSS, Demo).

    Returns
    -------
    str
        Cleaned text ready for sentiment, keyword, entity extraction.
    """
    if not raw_text:
        return ""

    text = raw_text

    # 1. Decode HTML entities
    text = html.unescape(text)

    # 2. Remove HTML tags (RSS summaries sometimes have leftover tags)
    text = re.sub(r"<[^>]+>", " ", text)

    # 3. Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)

    # 4. Remove @mentions
    text = re.sub(r"@\w+", "", text)

    # 5. Convert hashtags to words (#CortadoLove → CortadoLove)
    text = re.sub(r"#(\w+)", r"\1", text)

    # 6. Remove markdown formatting (* ** __ ~~ `)
    text = re.sub(r"[*_~`]{1,3}", "", text)

    # 7. Collapse multiple whitespace/newlines into single space
    text = re.sub(r"\s+", " ", text)

    # 8. Strip
    text = text.strip()

    return text
