#!/usr/bin/env python3
"""
Trends Engine — Quickstart Example
====================================
Demonstrates the full pipeline: collect → enrich → detect → generate.

Run:
    pip install -e packages/trends-nlp -e packages/trends-detector \
                -e packages/trends-campaign -e packages/trends-store \
                -e collectors
    python examples/quickstart.py
"""

import json
from datetime import datetime, timedelta

# ── 1. Collect: Generate synthetic social posts ──
from trends_collectors import DemoDataCollector

print("=" * 60)
print("STEP 1: Collecting social media data")
print("=" * 60)

collector = DemoDataCollector()
raw_items = collector.collect()
print(f"  Collected {len(raw_items)} items from demo data source")

# ── 2. Enrich: Run through NLP pipeline ──
from trends_nlp import NLPPipeline

print("\nSTEP 2: Enriching via 7-stage NLP pipeline")
print("=" * 60)

pipeline = NLPPipeline(enable_embeddings=False)  # Skip embeddings for speed
enriched = pipeline.process(raw_items)
print(f"  Enriched {len(enriched)} items")
print(f"  Topics found: {set(e.get('topic_id', 'unknown') for e in enriched)}")

# ── 3. Detect: Find trending topics ──
from trends_detector import aggregate_by_windows, TrendDetector

print("\nSTEP 3: Detecting trends (Velocity + Acceleration)")
print("=" * 60)

signals = aggregate_by_windows(enriched)
detector = TrendDetector()
reports = detector.detect(signals)

for report in reports:
    state = report.get("current_state", "BASELINE")
    topic = report.get("topic_id", "unknown")
    velocity = report.get("metrics", {}).get("velocity", 0)
    if state != "BASELINE":
        print(f"  🔥 {topic}: {state} (velocity={velocity:.2f})")

# ── 4. Generate: Create a campaign for the hottest trend ──
print("\nSTEP 4: Generating campaign (requires LLM)")
print("=" * 60)

hot_trends = [r for r in reports if r.get("current_state") not in ("BASELINE", "DECLINING")]
if hot_trends:
    top = hot_trends[0]
    print(f"  Top trend: {top['topic_id']} ({top['current_state']})")
    print(f"  To generate a campaign, configure LLM_PROVIDER in .env")
    print(f"  Example:")
    print(f"    from trends_campaign import CampaignGenerator, create_provider")
    print(f"    provider = create_provider('ollama', model='llama3.1')")
    print(f"    generator = CampaignGenerator(provider)")
else:
    print("  No hot trends detected in demo data — try with live sources")

print("\n✅ Pipeline complete!")
