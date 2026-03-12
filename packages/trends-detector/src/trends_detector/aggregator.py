"""
Windowed Aggregator — The Flink Equivalent
============================================
Groups enriched content items by (topic_id, time_window) and
computes aggregate metrics per window.

In production (Flink):
  enriched_stream
    .keyBy(topic_id)
    .window(SlidingEventTimeWindows.of(1hr, 15min))
    .aggregate(count, avg_sentiment, platform_breakdown)

In prototype (this file):
  Same logic, batch mode with pandas-like grouping.
  Same output schema. Same metrics. Just not real-time.

Output: List of TrendSignal dicts — one per (topic, window).
This is what goes into the "trend-signals" Kafka topic in production.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional


def aggregate_by_windows(
    enriched_items: list[dict],
    window_hours: int = 24,
    slide_hours: Optional[int] = None,
) -> list[dict]:
    """
    Aggregate enriched items into time windows per topic.

    Parameters
    ----------
    enriched_items : list[dict]
        EnrichedContentItems from Layer 2 (must have nlp.topic.topic_id).

    window_hours : int
        Window size in hours. Default 24h (daily windows).
        Use 1 for hourly granularity (production).

    slide_hours : int, optional
        Slide interval. If None, uses tumbling windows (= window_hours).
        Set to window_hours/4 for sliding windows.

    Returns
    -------
    list[dict]
        TrendSignal dicts, one per (topic_id, window_start).
        Sorted by (topic_id, window_start).
    """
    if slide_hours is None:
        slide_hours = window_hours  # Tumbling windows

    # ── Step 1: Parse timestamps and filter to items with topics ──
    parsed_items = []
    for item in enriched_items:
        topic_id = item.get("nlp", {}).get("topic", {}).get("topic_id")
        if not topic_id:
            continue  # Skip unmatched items

        try:
            published = _parse_timestamp(item["published_at"])
            parsed_items.append((topic_id, published, item))
        except Exception:
            continue

    if not parsed_items:
        return []

    # ── Step 2: Determine time range ──
    all_times = [t for _, t, _ in parsed_items]
    min_time = min(all_times)
    max_time = max(all_times)

    # ── Step 3: Generate window boundaries ──
    window_size = timedelta(hours=window_hours)
    slide_size = timedelta(hours=slide_hours)
    windows = []

    window_start = min_time.replace(minute=0, second=0, microsecond=0)
    while window_start + window_size <= max_time + slide_size:
        window_end = window_start + window_size
        windows.append((window_start, window_end))
        window_start += slide_size

    # ── Step 4: Assign items to windows and aggregate ──
    # Group items by topic first for efficiency
    items_by_topic = defaultdict(list)
    for topic_id, published, item in parsed_items:
        items_by_topic[topic_id].append((published, item))

    signals = []
    for topic_id, topic_items in items_by_topic.items():
        for window_start, window_end in windows:
            # Find items in this window
            window_items = [
                item for ts, item in topic_items
                if window_start <= ts < window_end
            ]

            if not window_items:
                # Emit zero-count signal (important for detecting DECLINING)
                signals.append(_create_signal(
                    topic_id, window_start, window_end, []
                ))
                continue

            signals.append(_create_signal(
                topic_id, window_start, window_end, window_items
            ))

    # Sort by topic, then time
    signals.sort(key=lambda s: (s["topic_id"], s["window_start"]))

    return signals


def _create_signal(
    topic_id: str,
    window_start: datetime,
    window_end: datetime,
    items: list[dict],
) -> dict:
    """
    Create a TrendSignal from items in a window.

    This is the schema that goes to the "trend-signals" Kafka topic.
    """
    mention_count = len(items)

    # Sentiment aggregation
    sentiments = [
        item["nlp"]["sentiment"]["compound"]
        for item in items
        if item.get("nlp", {}).get("sentiment")
    ]
    sentiment_avg = sum(sentiments) / len(sentiments) if sentiments else 0.0
    sentiment_std = _std(sentiments) if len(sentiments) > 1 else 0.0

    # Platform breakdown
    platform_counts = defaultdict(int)
    for item in items:
        platform_counts[item.get("source_platform", "unknown")] += 1

    # Engagement aggregation
    total_likes = sum(item.get("engagement", {}).get("likes", 0) for item in items)
    total_comments = sum(item.get("engagement", {}).get("comments", 0) for item in items)
    total_shares = sum(item.get("engagement", {}).get("shares", 0) for item in items)

    # Top keywords across window (frequency count)
    keyword_freq = defaultdict(int)
    for item in items:
        for kw in item.get("nlp", {}).get("keywords", []):
            keyword_freq[kw] += 1
    top_keywords = sorted(keyword_freq.items(), key=lambda x: -x[1])[:10]

    return {
        "topic_id": topic_id,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "mention_count": mention_count,
        "sentiment_avg": round(sentiment_avg, 4),
        "sentiment_std": round(sentiment_std, 4),
        "platforms": dict(platform_counts),
        "engagement": {
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
        },
        "top_keywords": [{"keyword": kw, "count": c} for kw, c in top_keywords],
    }


def _parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO timestamp string to datetime."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _std(values: list[float]) -> float:
    """Standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5
