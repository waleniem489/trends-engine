"""
Trend Detector — The Core Algorithm
=====================================
Computes trend metrics from windowed signals and classifies
each topic into a lifecycle state.

Algorithm: Velocity + Acceleration (Algorithm 4 from architecture doc)

Velocity  = (current_count - baseline_count) / baseline_count
  → "How far above normal?"
  → 2.0 means 3x baseline (200% above)

Acceleration = velocity_current - velocity_previous
  → "Is it speeding up or slowing down?"
  → Positive = growing faster. Negative = growth decelerating.

Lifecycle States:
  BASELINE   → Steady, normal activity
  EMERGING   → Just starting to rise above baseline
  GROWING    → Accelerating upward (velocity + acceleration both positive)
  PEAKING    → High velocity but acceleration turning negative
  DECLINING  → Velocity dropping, heading back toward baseline
  VIRAL      → Extreme spike (>10x baseline, rare)

                    velocity
                      ↑
            PEAKING   │   VIRAL
          ┌───────────┼──────────┐
          │           │          │
DECLINING │           │          │ GROWING
          │           │          │
          └───────────┼──────────┘
            BASELINE  │  EMERGING
                      └────────────→ acceleration

Design note:
  The lifecycle classifier uses a state machine with hysteresis.
  Topics don't flip between states on every measurement — they need
  sustained signal to transition. This prevents false positives
  from single-window spikes.
"""

from collections import defaultdict
from datetime import datetime
from typing import Optional

# ─── Lifecycle thresholds ────────────────────────────────
# Tuned for our demo data volume. In production, these would
# be adaptive per-topic based on historical variance.

THRESHOLDS = {
    "emerging_velocity": 0.5,       # 50% above baseline
    "growing_velocity": 1.0,        # 100% above baseline (2x)
    "peaking_velocity": 2.0,        # 200% above baseline (3x)
    "viral_velocity": 10.0,         # 1000% above baseline (11x)
    "declining_acceleration": -0.3,  # Negative acceleration threshold
    "min_baseline_count": 5,        # Minimum mentions to establish baseline
    "baseline_windows": 3,          # Number of early windows for baseline calc
}


class TrendDetector:
    """
    Analyzes windowed signals to detect and classify trends.

    Input: TrendSignals from Aggregator (per topic, per window)
    Output: TrendReport per topic (current state, metrics, history)
    """

    def __init__(self, thresholds: Optional[dict] = None):
        self.thresholds = {**THRESHOLDS, **(thresholds or {})}

    def detect(self, signals: list[dict]) -> list[dict]:
        """
        Analyze all signals and produce a TrendReport for each topic.

        Parameters
        ----------
        signals : list[dict]
            TrendSignal dicts from aggregator, sorted by (topic_id, window_start).

        Returns
        -------
        list[dict]
            TrendReport per topic, sorted by current velocity (hottest first).
        """
        # Group signals by topic
        signals_by_topic = defaultdict(list)
        for signal in signals:
            signals_by_topic[signal["topic_id"]].append(signal)

        # Analyze each topic
        reports = []
        for topic_id, topic_signals in signals_by_topic.items():
            # Sort by window start time
            topic_signals.sort(key=lambda s: s["window_start"])
            report = self._analyze_topic(topic_id, topic_signals)
            reports.append(report)

        # Sort by velocity descending (hottest trends first)
        reports.sort(key=lambda r: r["metrics"]["velocity"], reverse=True)

        return reports

    def _analyze_topic(self, topic_id: str, signals: list[dict]) -> dict:
        """
        Analyze a single topic's signal history.

        Steps:
        1. Compute baseline from early windows
        2. Compute velocity per window
        3. Compute acceleration (velocity delta)
        4. Classify current lifecycle state
        5. Package into TrendReport
        """
        counts = [s["mention_count"] for s in signals]
        n_baseline = self.thresholds["baseline_windows"]

        # ── Step 1: Compute baseline ──
        # Average of first N windows (before any potential trend)
        baseline_counts = counts[:n_baseline]
        baseline = sum(baseline_counts) / len(baseline_counts) if baseline_counts else 0
        baseline = max(baseline, self.thresholds["min_baseline_count"])

        # ── Step 2: Compute velocity per window ──
        velocities = []
        for count in counts:
            velocity = (count - baseline) / baseline
            velocities.append(round(velocity, 4))

        # ── Step 3: Compute acceleration ──
        accelerations = [0.0]  # First window has no previous velocity
        for i in range(1, len(velocities)):
            accel = velocities[i] - velocities[i - 1]
            accelerations.append(round(accel, 4))

        # ── Step 4: Compute per-window lifecycle states ──
        states = []
        for i in range(len(velocities)):
            state = self._classify_state(velocities[i], accelerations[i])
            states.append(state)

        # ── Step 5: Current state (latest window) ──
        current_velocity = velocities[-1] if velocities else 0.0
        current_acceleration = accelerations[-1] if accelerations else 0.0
        current_state = states[-1] if states else "BASELINE"
        current_count = counts[-1] if counts else 0
        peak_count = max(counts) if counts else 0
        peak_velocity = max(velocities) if velocities else 0.0

        # Find peak window
        peak_window_idx = velocities.index(peak_velocity) if velocities else 0
        peak_window = signals[peak_window_idx]["window_start"] if signals else None

        # Sentiment aggregation across all windows
        sentiments = [s["sentiment_avg"] for s in signals if s["sentiment_avg"] != 0]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

        # Platform spread (how many platforms mention this topic)
        all_platforms = set()
        for s in signals:
            all_platforms.update(s.get("platforms", {}).keys())

        # Aggregate engagement
        total_engagement = {
            "likes": sum(s.get("engagement", {}).get("total_likes", 0) for s in signals),
            "comments": sum(s.get("engagement", {}).get("total_comments", 0) for s in signals),
            "shares": sum(s.get("engagement", {}).get("total_shares", 0) for s in signals),
        }

        # Build window history (for visualization)
        history = []
        for i, signal in enumerate(signals):
            history.append({
                "window_start": signal["window_start"],
                "mention_count": counts[i],
                "velocity": velocities[i],
                "acceleration": accelerations[i],
                "state": states[i],
                "sentiment_avg": signal["sentiment_avg"],
            })

        return {
            "topic_id": topic_id,
            "current_state": current_state,
            "metrics": {
                "velocity": current_velocity,
                "acceleration": current_acceleration,
                "current_count": current_count,
                "peak_count": peak_count,
                "peak_velocity": peak_velocity,
                "peak_window": peak_window,
                "baseline": round(baseline, 1),
                "total_mentions": sum(counts),
                "avg_sentiment": round(avg_sentiment, 4),
                "platform_spread": len(all_platforms),
                "platforms": list(all_platforms),
                "total_engagement": total_engagement,
            },
            "history": history,
            "window_count": len(signals),
            "first_seen": signals[0]["window_start"] if signals else None,
            "last_seen": signals[-1]["window_start"] if signals else None,
        }

    def _classify_state(self, velocity: float, acceleration: float) -> str:
        """
        Classify a single window's lifecycle state.

        Uses velocity + acceleration quadrant approach:

        High velocity + positive accel  → GROWING (still accelerating)
        High velocity + negative accel  → PEAKING (slowing down at top)
        Extreme velocity                → VIRAL (off the charts)
        Medium velocity + positive accel → EMERGING (just starting)
        Negative velocity trend          → DECLINING (heading down)
        Low velocity                     → BASELINE (normal)
        """
        t = self.thresholds

        # VIRAL: extreme spike
        if velocity >= t["viral_velocity"]:
            return "VIRAL"

        # PEAKING: high velocity but decelerating
        if velocity >= t["peaking_velocity"] and acceleration < t["declining_acceleration"]:
            return "PEAKING"

        # GROWING: high velocity and still accelerating
        if velocity >= t["growing_velocity"] and acceleration >= 0:
            return "GROWING"

        # PEAKING: high velocity, mildly decelerating
        if velocity >= t["growing_velocity"] and acceleration < 0:
            return "PEAKING"

        # EMERGING: moderate velocity, positive trend
        if velocity >= t["emerging_velocity"]:
            return "EMERGING"

        # DECLINING: was above baseline, now dropping
        if velocity > 0 and acceleration < t["declining_acceleration"]:
            return "DECLINING"

        # BASELINE: normal activity
        return "BASELINE"

    def get_thresholds(self) -> dict:
        """Return current threshold configuration."""
        return self.thresholds.copy()
