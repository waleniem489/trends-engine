"""
Collector Registry & Orchestrator
==================================
The Registry manages all active collectors.
The Orchestrator runs collection across all registered collectors.

This is the Strategy + Registry pattern in action:
- Registry: knows WHICH collectors exist and their status
- Orchestrator: knows HOW to run collection (order, error handling, stats)

Adding a new data source = write collector + register it. Zero other changes.

In production:
- Orchestrator would be an Airflow DAG or Flink source
- Registry would be backed by a config file or database
- Health checks would run on a schedule

In prototype:
- Orchestrator is a Python function call
- Registry is an in-memory dict
- Health checks run at collection time
"""

import logging
import time
from typing import Generator

from .base import BaseCollector

log = logging.getLogger(__name__)


class CollectorRegistry:
    """
    Manages all data source collectors.
    Add, remove, enable, disable collectors at runtime.

    In production, this would be backed by a config store.
    In prototype, it's an in-memory dict — same interface.
    """

    def __init__(self):
        self._collectors: dict[str, BaseCollector] = {}

    def register(self, collector: BaseCollector) -> None:
        """Register a collector. Overwrites if name already exists."""
        self._collectors[collector.name] = collector
        log.info(f"Registered collector: {collector}")

    def unregister(self, name: str) -> None:
        """Remove a collector entirely."""
        if name in self._collectors:
            removed = self._collectors.pop(name)
            log.info(f"Unregistered collector: {removed}")

    def enable(self, name: str) -> None:
        """Enable a previously disabled collector."""
        if name in self._collectors:
            self._collectors[name].enabled = True

    def disable(self, name: str) -> None:
        """Disable a collector without removing it."""
        if name in self._collectors:
            self._collectors[name].enabled = False

    def get_active(self) -> list[BaseCollector]:
        """Return all enabled collectors."""
        return [c for c in self._collectors.values() if c.enabled]

    def get_all(self) -> list[BaseCollector]:
        """Return all collectors regardless of status."""
        return list(self._collectors.values())

    def status(self) -> dict:
        """Return status summary of all collectors."""
        return {
            name: {
                "enabled": c.enabled,
                "platform": c.platform,
            }
            for name, c in self._collectors.items()
        }

    def __repr__(self) -> str:
        lines = [f"CollectorRegistry ({len(self._collectors)} collectors):"]
        for c in self._collectors.values():
            lines.append(f"  {c}")
        return "\n".join(lines)


class CollectionOrchestrator:
    """
    Runs data collection across all registered collectors.

    Responsibilities:
    1. Check health of each collector before running
    2. Run collection, yielding all ContentItems
    3. Track stats (items per source, errors, timing)
    4. Handle failures gracefully (skip broken sources, continue)

    Usage:
        registry = CollectorRegistry()
        registry.register(DemoDataCollector())
        registry.register(NewsCollector())

        orchestrator = CollectionOrchestrator(registry)
        items, stats = orchestrator.run()
    """

    def __init__(self, registry: CollectorRegistry, skip_health_check: bool = False):
        self.registry = registry
        self.skip_health_check = skip_health_check

    def run(self) -> tuple[list[dict], dict]:
        """
        Execute collection from all active, healthy collectors.

        Returns
        -------
        tuple[list[dict], dict]
            (list of ContentItems, stats dict with collection metadata)
        """
        all_items = []
        stats = {
            "collectors_attempted": 0,
            "collectors_succeeded": 0,
            "collectors_failed": [],
            "collectors_skipped_unhealthy": [],
            "items_per_source": {},
            "total_items": 0,
            "total_time_seconds": 0,
        }

        start_time = time.time()
        active_collectors = self.registry.get_active()
        stats["collectors_attempted"] = len(active_collectors)

        print(f"\n{'='*60}")
        print(f"  COLLECTION RUN — {len(active_collectors)} active collectors")
        print(f"{'='*60}")

        for collector in active_collectors:
            print(f"\n  📡 {collector.name} ({collector.platform})")

            # ── Health check ──
            if not self.skip_health_check:
                try:
                    healthy = collector.health_check()
                    if not healthy:
                        print(f"     ⚠️  Health check FAILED — skipping")
                        stats["collectors_skipped_unhealthy"].append(collector.name)
                        continue
                    print(f"     ✅ Health check passed")
                except Exception as e:
                    print(f"     ⚠️  Health check ERROR: {e} — skipping")
                    stats["collectors_skipped_unhealthy"].append(collector.name)
                    continue

            # ── Collect ──
            try:
                source_start = time.time()
                source_items = list(collector.collect())
                source_time = time.time() - source_start

                all_items.extend(source_items)
                stats["items_per_source"][collector.name] = len(source_items)
                stats["collectors_succeeded"] += 1

                print(f"     📦 {len(source_items)} items in {source_time:.1f}s")

            except Exception as e:
                print(f"     ❌ Collection FAILED: {e}")
                stats["collectors_failed"].append(
                    {"name": collector.name, "error": str(e)}
                )
                stats["items_per_source"][collector.name] = 0

        stats["total_items"] = len(all_items)
        stats["total_time_seconds"] = round(time.time() - start_time, 2)

        # ── Summary ──
        print(f"\n{'='*60}")
        print(f"  COLLECTION COMPLETE")
        print(f"  Total: {stats['total_items']} items in {stats['total_time_seconds']}s")
        print(f"  Sources: {stats['collectors_succeeded']}/{stats['collectors_attempted']} succeeded")
        if stats["collectors_failed"]:
            print(f"  Failed: {[f['name'] for f in stats['collectors_failed']]}")
        if stats["collectors_skipped_unhealthy"]:
            print(f"  Unhealthy: {stats['collectors_skipped_unhealthy']}")
        print(f"{'='*60}\n")

        return all_items, stats

    def run_stream(self) -> Generator[dict, None, None]:
        """
        Streaming version — yields items one at a time.
        Useful for piping directly into Kafka or NLP pipeline
        without holding everything in memory.
        """
        for collector in self.registry.get_active():
            try:
                if not self.skip_health_check and not collector.health_check():
                    continue
                yield from collector.collect()
            except Exception as e:
                log.warning(f"Collector {collector.name} failed: {e}")
                continue
