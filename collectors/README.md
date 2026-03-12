# trends-collectors

Data source connectors for social media and news APIs.

Part of [Trends Engine](https://github.com/neelmanivispute/trends-engine) — can be used independently.

## Install

```bash
pip install trends-collectors           # Core (HN, NewsAPI, Reddit)
pip install trends-collectors[rss]      # + RSS/Atom feed support
```

## Usage

```python
from trends_collectors import HackerNewsCollector, CollectorRegistry, CollectionOrchestrator

# Single collector
hn = HackerNewsCollector()
items = hn.collect()

# Or use the orchestrator for multiple sources
registry = CollectorRegistry()
registry.register(HackerNewsCollector())
orchestrator = CollectionOrchestrator(registry)
all_items = orchestrator.collect_all()
```

## Built-in Collectors

| Collector | Source | Auth Required | Rate Limit |
|-----------|--------|--------------|------------|
| `HackerNewsCollector` | Hacker News API | No | None |
| `NewsAPICollector` | newsapi.org | API key | 100/day (free) |
| `RedditCollector` | Reddit JSON API | OAuth | Generous |
| `NewsCollector` | RSS/Atom feeds | No | None |
| `DemoDataCollector` | Synthetic data | No | None |

## Custom Collectors

```python
from trends_collectors import BaseCollector

class MyCollector(BaseCollector):
    def collect(self) -> list[dict]:
        # Fetch from your data source
        return [{"id": "1", "title": "...", "body": "...", "source": "my_source"}]
```
