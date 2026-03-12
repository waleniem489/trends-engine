# trends-detector

Velocity + Acceleration trend detection with lifecycle classification.

Part of [Trends Engine](https://github.com/neelmanivispute/trends-engine) — can be used independently. Zero dependencies.

## Install

```bash
pip install trends-detector
```

## Usage

```python
from trends_detector import TrendDetector, aggregate_by_windows

# Aggregate enriched items into windowed signals
signals = aggregate_by_windows(enriched_items)

# Detect trends
detector = TrendDetector()
reports = detector.detect(signals)

for report in reports:
    print(f"{report['topic_id']}: {report['current_state']} (v={report['metrics']['velocity']:.2f})")
```

## Algorithm

```
velocity     = (current_count - baseline) / baseline
acceleration = velocity_current - velocity_previous
```

6 lifecycle states: **BASELINE → EMERGING → GROWING → PEAKING → DECLINING → VIRAL**

The key insight: velocity tells you *where* a topic is, acceleration tells you *where it's going*. A topic at 155% above baseline with negative acceleration is peaking, not growing — the marketing response is completely different.

Custom thresholds:
```python
detector = TrendDetector(thresholds={"emerging_velocity": 0.3, "viral_velocity": 15.0})
```
