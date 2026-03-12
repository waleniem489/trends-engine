"""
Alert Generator — Lifecycle Transition Alerts
===============================================
Detects when a topic transitions between lifecycle states
and generates actionable alerts for downstream systems
(campaign builder, Slack bot, dashboard).

Not every window produces an alert. Alerts fire on TRANSITIONS:
  BASELINE → EMERGING  → "New trend detected — consider early content"
  EMERGING → GROWING   → "Trend accelerating — create campaign now"
  GROWING  → PEAKING   → "Trend at peak — maximize reach now"
  PEAKING  → DECLINING → "Trend cooling — shift to evergreen content"

Each alert includes:
  - What happened (transition)
  - Why it matters (metrics)
  - Recommended action (for campaign integration)
  - Urgency level (for Slack notification priority)

In production: These go to the "trend-alerts" Kafka topic.
In prototype: Returned as dicts for the dashboard/Slack bot.
"""

from datetime import datetime, timezone

# Priority levels for different transitions
TRANSITION_CONFIG = {
    ("BASELINE", "EMERGING"): {
        "priority": "medium",
        "action": "Monitor this trend. Consider drafting exploratory content.",
        "emoji": "✨",
        "label": "NEW TREND DETECTED",
    },
    ("EMERGING", "GROWING"): {
        "priority": "high",
        "action": "Trend is accelerating. Create a targeted email campaign NOW.",
        "emoji": "🚀",
        "label": "TREND ACCELERATING",
    },
    ("GROWING", "PEAKING"): {
        "priority": "urgent",
        "action": "Trend at peak visibility. Send campaign immediately for maximum reach.",
        "emoji": "⛰️",
        "label": "TREND PEAKING",
    },
    ("GROWING", "VIRAL"): {
        "priority": "urgent",
        "action": "VIRAL trend detected! Drop everything — send campaign immediately.",
        "emoji": "🔥",
        "label": "VIRAL TREND",
    },
    ("PEAKING", "DECLINING"): {
        "priority": "low",
        "action": "Trend is cooling. Shift to evergreen content angles.",
        "emoji": "📉",
        "label": "TREND DECLINING",
    },
    ("VIRAL", "PEAKING"): {
        "priority": "medium",
        "action": "Viral spike stabilizing. Good time for follow-up content.",
        "emoji": "📊",
        "label": "VIRAL SPIKE STABILIZING",
    },
}

# States ordered by "intensity" for detecting any upward/downward movement
STATE_INTENSITY = {
    "BASELINE": 0,
    "DECLINING": 1,
    "EMERGING": 2,
    "GROWING": 3,
    "PEAKING": 4,
    "VIRAL": 5,
}


def generate_alerts(trend_reports: list[dict]) -> list[dict]:
    """
    Analyze trend reports and generate alerts for significant transitions.

    Looks at each topic's history to find the most recent transition,
    then generates an alert if it's actionable.

    Parameters
    ----------
    trend_reports : list[dict]
        TrendReports from TrendDetector.detect().

    Returns
    -------
    list[dict]
        Alert dicts sorted by priority (urgent first).
    """
    alerts = []

    for report in trend_reports:
        alert = _check_for_transition(report)
        if alert:
            alerts.append(alert)

    # Sort by priority: urgent > high > medium > low
    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: priority_order.get(a["priority"], 99))

    return alerts


def _check_for_transition(report: dict) -> dict | None:
    """
    Check if a topic has a recent lifecycle transition worth alerting on.

    Looks at the last few windows in history to find state changes.
    Only alerts on the MOST RECENT transition.
    """
    history = report.get("history", [])
    if len(history) < 2:
        return None

    # Find the most recent state transition
    for i in range(len(history) - 1, 0, -1):
        current_state = history[i]["state"]
        previous_state = history[i - 1]["state"]

        if current_state != previous_state:
            transition = (previous_state, current_state)

            # Check if this is a configured transition
            config = TRANSITION_CONFIG.get(transition)
            if not config:
                # Check if it's a significant upward or downward move
                curr_intensity = STATE_INTENSITY.get(current_state, 0)
                prev_intensity = STATE_INTENSITY.get(previous_state, 0)

                if curr_intensity > prev_intensity:
                    config = {
                        "priority": "medium",
                        "action": f"Trend moved from {previous_state} to {current_state}.",
                        "emoji": "📈",
                        "label": "TREND MOVING UP",
                    }
                elif curr_intensity < prev_intensity:
                    config = {
                        "priority": "low",
                        "action": f"Trend moved from {previous_state} to {current_state}.",
                        "emoji": "📉",
                        "label": "TREND MOVING DOWN",
                    }
                else:
                    continue

            metrics = report["metrics"]

            return {
                "alert_id": f"alert_{report['topic_id']}_{history[i]['window_start'][:13]}",
                "topic_id": report["topic_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "transition": {
                    "from": previous_state,
                    "to": current_state,
                },
                "priority": config["priority"],
                "emoji": config["emoji"],
                "label": config["label"],
                "action": config["action"],
                "metrics": {
                    "velocity": metrics["velocity"],
                    "acceleration": metrics["acceleration"],
                    "current_count": metrics["current_count"],
                    "peak_count": metrics["peak_count"],
                    "baseline": metrics["baseline"],
                    "avg_sentiment": metrics["avg_sentiment"],
                    "platform_spread": metrics["platform_spread"],
                },
                "window": {
                    "start": history[i]["window_start"],
                    "mention_count": history[i]["mention_count"],
                },
            }

    return None


def format_alert_text(alert: dict) -> str:
    """
    Format an alert as human-readable text.
    Used for Slack messages, dashboard notifications, and CLI output.
    """
    m = alert["metrics"]
    velocity_pct = round(m["velocity"] * 100)

    lines = [
        f"{alert['emoji']} {alert['label']}: {alert['topic_id']}",
        f"   {alert['transition']['from']} → {alert['transition']['to']}",
        f"   Velocity: {velocity_pct:+d}% above baseline (baseline: {m['baseline']:.0f}/day)",
        f"   Current: {m['current_count']} mentions | Peak: {m['peak_count']}",
        f"   Sentiment: {'😊 positive' if m['avg_sentiment'] > 0.05 else '😐 neutral' if m['avg_sentiment'] > -0.05 else '😞 negative'} ({m['avg_sentiment']:+.2f})",
        f"   Platforms: {m['platform_spread']}",
        f"   ➡️  {alert['action']}",
    ]

    return "\n".join(lines)


def format_alerts_summary(alerts: list[dict]) -> str:
    """Format all alerts as a summary report."""
    if not alerts:
        return "No new trend alerts."

    lines = [
        f"{'='*60}",
        f"  TREND ALERTS — {len(alerts)} alerts",
        f"{'='*60}",
    ]

    for alert in alerts:
        lines.append("")
        lines.append(format_alert_text(alert))

    lines.append(f"\n{'='*60}")
    return "\n".join(lines)
