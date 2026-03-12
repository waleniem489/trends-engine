"""
trends-detector: Velocity + Acceleration trend detection algorithm.

Classifies topics into lifecycle states (BASELINE → EMERGING → GROWING →
PEAKING → DECLINING → VIRAL) using windowed signal analysis.

Quick start:
    from trends_detector import TrendDetector, TrendAggregator
    aggregator = TrendAggregator()
    signals = aggregator.aggregate(enriched_items)
    detector = TrendDetector()
    reports = detector.detect(signals)
"""

__version__ = "0.1.0"

from trends_detector.detector import TrendDetector, THRESHOLDS
from trends_detector.aggregator import aggregate_by_windows
from trends_detector.alerts import generate_alerts, format_alert_text

__all__ = [
    "TrendDetector",
    "aggregate_by_windows",
    "generate_alerts",
    "format_alert_text",
    "THRESHOLDS",
]
