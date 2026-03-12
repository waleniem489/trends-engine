"""
Sentiment Analyzer — Stage 2 of NLP Pipeline
==============================================
Uses VADER (Valence Aware Dictionary and sEntiment Reasoner).

Why VADER over TextBlob or transformer models?
- Built for social media text (understands slang, emojis, caps, punctuation)
- "This coffee is AMAZING!!!" → higher positive than "This coffee is amazing"
- No GPU needed, runs in microseconds
- Perfect for prototype speed

Returns compound score: -1.0 (most negative) to +1.0 (most positive)
Also returns categorical label: positive/negative/neutral.

Production upgrade path:
- Phase 1 (prototype): VADER — fast, no dependencies
- Phase 2: Fine-tuned DistilBERT for marketing domain
- Phase 3: Aspect-based sentiment ("coffee is great, price is awful")
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Singleton — VADER loads a lexicon on init, reuse across calls
_analyzer = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def analyze_sentiment(text: str) -> dict:
    """
    Analyze sentiment of text using VADER.

    Parameters
    ----------
    text : str
        Cleaned text (output of Stage 1).

    Returns
    -------
    dict
        {
            "compound": float,    # -1.0 to 1.0 (overall score)
            "positive": float,    # 0.0 to 1.0
            "negative": float,    # 0.0 to 1.0
            "neutral": float,     # 0.0 to 1.0
            "label": str          # "positive" | "negative" | "neutral"
        }

    Notes
    -----
    Thresholds for labels (VADER recommended):
    - compound >= 0.05 → positive
    - compound <= -0.05 → negative
    - else → neutral
    """
    if not text or len(text.strip()) < 3:
        return {
            "compound": 0.0,
            "positive": 0.0,
            "negative": 0.0,
            "neutral": 1.0,
            "label": "neutral",
        }

    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(text)

    compound = scores["compound"]
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return {
        "compound": round(compound, 4),
        "positive": round(scores["pos"], 4),
        "negative": round(scores["neg"], 4),
        "neutral": round(scores["neu"], 4),
        "label": label,
    }
