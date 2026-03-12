"""
Campaign Generator — AI Workflow (Layer 5)
============================================
Orchestrates: Trend Data + RAG Context + LLM → Campaign Content

Architecture:
  Simple AI workflow. One prompt, one LLM call, structured output.
  NOT agentic — the steps are deterministic, LLM does one thing well.

  "For campaign generation, the steps are well-defined, so agent autonomy
   would be unnecessary complexity. The evolution path: Phase 2 adds a
   multi-step agentic workflow — trend analyst, audience strategist,
   content creator, quality reviewer in a DAG."

Data flow:
  1. Load trend report for topic (from Layer 3 detector output)
  2. Pull top N enriched posts for RAG context (from Layer 2 NLP output)
  3. Build RAG-grounded prompt with trend metrics + real posts
  4. Call LLM (Ollama/Cohere/Claude — provider-agnostic)
  5. Parse structured JSON response
  6. Cache result for demo reliability
"""

import json
import os
import time
import hashlib
from typing import Optional

from .provider import LLMProvider, create_provider
from .prompts import SYSTEM_PROMPT, build_campaign_prompt


class CampaignGenerator:
    """
    Generate trend-aware email campaigns using LLM + RAG context.

    Usage:
        gen = CampaignGenerator(provider="ollama", model="llama3.1")
        campaign = gen.generate(
            topic_id="cortado",
            trend_reports=trend_data,
            enriched_items=enriched_data,
            industry="cafe"
        )
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str = None,
        cache_dir: str = "data/campaign_cache",
        use_cache: bool = True,
        vector_store=None,
        embedder=None,
        **provider_kwargs,
    ):
        # Set model defaults per provider
        model_defaults = {
            "ollama": "llama3.1",
            "cohere": "command-r-plus",
            "claude": "claude-sonnet-4-20250514",
            "openai": "gpt-4o-mini",
        }
        if model:
            provider_kwargs["model"] = model
        elif provider in model_defaults:
            provider_kwargs["model"] = model_defaults[provider]

        self.llm = create_provider(provider, **provider_kwargs)
        self.cache_dir = cache_dir
        self.use_cache = use_cache
        self.vector_store = vector_store  # Qdrant store for semantic RAG
        self.embedder = embedder          # BGE embedder for query embedding

        if use_cache:
            os.makedirs(cache_dir, exist_ok=True)

    def generate(
        self,
        topic_id: str,
        trend_reports: dict,
        enriched_items: list,
        industry: str = "cafe",
        audience_segment: str = "all subscribers",
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> Optional[dict]:
        """
        Generate a campaign for a given topic.

        Args:
            topic_id: Topic to generate campaign for (e.g., "cortado")
            trend_reports: Full trend reports dict from Layer 3
            enriched_items: List of enriched items from Layer 2
            industry: Business type for tone/content
            audience_segment: Target audience description

        Returns:
            Campaign dict with subject_lines, email_body, campaign_settings
            Or None if generation fails.
        """

        # ── Step 1: Extract trend report for this topic ──
        report = self._find_trend_report(topic_id, trend_reports)
        if not report:
            print(f"  ⚠️  No trend report found for '{topic_id}'")
            return None

        metrics = report.get("metrics", {})

        # ── Step 2: Pull RAG context — real posts about this topic ──
        if self.vector_store and self.embedder:
            # Qdrant semantic search — proper RAG retrieval
            query_text = f"{topic_id.replace('_', ' ')} trending marketing campaign"
            query_embedding = self.embedder.embed(query_text).tolist()
            sample_posts = self.vector_store.search_for_campaign(
                topic_id=topic_id,
                query_embedding=query_embedding,
                top_k=8,
                min_sentiment=0.0,  # filter out negative posts
            )
            retrieval_method = "qdrant"
            print(f"  🔍 Qdrant: retrieved {len(sample_posts)} posts (semantic search)")
        else:
            # Fallback: in-memory filter (original method)
            sample_posts = self._get_sample_posts(topic_id, enriched_items, n=8)
            retrieval_method = "in-memory"
        if not sample_posts:
            print(f"  ⚠️  No enriched posts found for '{topic_id}'")
            return None

        # ── Step 3: Check cache ──
        cache_key = self._cache_key(topic_id, industry, audience_segment)
        if self.use_cache:
            cached = self._load_cache(cache_key)
            if cached:
                print(f"  💾 Cache hit for {topic_id}/{industry}")
                return cached

        # ── Step 4: Build RAG-grounded prompt ──
        # Collect top keywords from trend signals
        top_keywords = []
        for signal in report.get("history", [])[-3:]:
            top_keywords.extend(signal.get("top_keywords", []))
        top_keywords = list(dict.fromkeys(top_keywords))[:10]  # dedupe, top 10

        prompt = build_campaign_prompt(
            topic_name=report.get("topic_id", topic_id).replace("_", " ").title(),
            trend_state=report.get("current_state", "BASELINE"),
            velocity=metrics.get("velocity", 0) * 100,
            sentiment=metrics.get("avg_sentiment", 0),
            mention_count=metrics.get("current_count", 0),
            peak_count=metrics.get("peak_count", 0),
            baseline=metrics.get("baseline", 0),
            platforms=metrics.get("platforms", []),
            top_keywords=top_keywords,
            sample_posts=sample_posts,
            industry=industry,
            audience_segment=audience_segment,
        )

        # ── Step 5: Call LLM ──
        campaign = None
        for attempt in range(max_retries + 1):
            try:
                print(f"  🤖 Calling {self.llm.name()}... ", end="", flush=True)
                start = time.time()

                response = self.llm.generate(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=temperature,
                    max_tokens=2000,
                )

                elapsed = time.time() - start
                print(f"({elapsed:.1f}s)")

                # ── Step 6: Parse JSON response ──
                campaign = self._parse_response(response)
                if campaign:
                    break
                else:
                    print(f"  ⚠️  Failed to parse response (attempt {attempt + 1})")

            except Exception as e:
                print(f"\n  ❌ LLM error (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    print(f"  🔄 Retrying...")
                    time.sleep(1)

        if not campaign:
            print(f"  ❌ Failed to generate campaign for {topic_id} after {max_retries + 1} attempts")
            return None

        # ── Step 7: Enrich with metadata ──
        campaign["_meta"] = {
            "topic_id": topic_id,
            "trend_state": report.get("current_state"),
            "velocity": metrics.get("velocity", 0),
            "industry": industry,
            "audience_segment": audience_segment,
            "provider": self.llm.name(),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rag_context_count": len(sample_posts),
        }

        # ── Step 8: Cache result ──
        if self.use_cache:
            self._save_cache(cache_key, campaign)

        return campaign

    def generate_all(
        self,
        trend_reports: dict,
        enriched_items: list,
        industry: str = "cafe",
        audience_segment: str = "all subscribers",
        min_velocity: float = -1.0,
    ) -> dict:
        """
        Generate campaigns for all topics with velocity above threshold.

        Returns dict of {topic_id: campaign_dict}
        """
        reports = trend_reports.get("trend_reports", [])
        campaigns = {}

        # Sort by velocity descending — generate most interesting first
        reports_sorted = sorted(
            reports,
            key=lambda r: r.get("metrics", {}).get("velocity", 0),
            reverse=True,
        )

        for report in reports_sorted:
            topic_id = report.get("topic_id", "unknown")
            velocity = report.get("metrics", {}).get("velocity", 0)

            if velocity < min_velocity:
                print(f"  ⏭️  Skipping {topic_id} (velocity {velocity:.1%} below threshold)")
                continue

            print(f"\n  📝 Generating campaign: {topic_id} ({report.get('current_state', '?')}, {velocity:.0%})")

            campaign = self.generate(
                topic_id=topic_id,
                trend_reports=trend_reports,
                enriched_items=enriched_items,
                industry=industry,
                audience_segment=audience_segment,
            )

            if campaign:
                campaigns[topic_id] = campaign
                print(f"  ✅ {topic_id}: \"{campaign.get('subject_lines', ['?'])[0]}\"")
            else:
                print(f"  ⚠️  {topic_id}: generation failed")

        return campaigns

    # ═══════════════════════════════════════════════════════════
    # Private helpers
    # ═══════════════════════════════════════════════════════════

    def _find_trend_report(self, topic_id: str, trend_reports: dict) -> Optional[dict]:
        """Find the trend report for a specific topic."""
        for report in trend_reports.get("trend_reports", []):
            if report.get("topic_id") == topic_id:
                return report
        return None

    def _get_sample_posts(self, topic_id: str, enriched_items: list, n: int = 8) -> list:
        """
        Pull sample posts for RAG context.
        Selects diverse posts: mix of platforms and sentiments.
        """
        matching = [
            item for item in enriched_items
            if item.get("nlp", {}).get("topic", {}).get("topic_id") == topic_id
        ]

        if not matching:
            return []

        # Sort by engagement (if available) to get most interesting posts
        matching.sort(
            key=lambda x: sum(x.get("engagement", {}).values()),
            reverse=True,
        )

        # Take top N but try to mix platforms
        selected = []
        seen_platforms = set()
        # First pass: one per platform
        for item in matching:
            platform = item.get("platform", "unknown")
            if platform not in seen_platforms and len(selected) < n:
                selected.append(item)
                seen_platforms.add(platform)
        # Second pass: fill remaining slots
        for item in matching:
            if item not in selected and len(selected) < n:
                selected.append(item)

        return selected

    def _parse_response(self, response: str) -> Optional[dict]:
        """Parse LLM response as JSON. Handles common formatting issues."""
        if not response:
            return None

        text = response.strip()

        # Strip markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Try to find JSON object in the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        try:
            parsed = json.loads(text)
            # Validate required fields
            if "subject_lines" in parsed and "email_body" in parsed:
                return parsed
            else:
                print(f"    (missing required fields: {list(parsed.keys())})")
                return None
        except json.JSONDecodeError as e:
            # Print first 200 chars for debugging
            print(f"    (JSON parse error: {e})")
            print(f"    Response preview: {text[:200]}...")
            return None

    def _cache_key(self, topic_id: str, industry: str, audience: str) -> str:
        """Generate a deterministic cache key."""
        raw = f"{topic_id}:{industry}:{audience}:{self.llm.name()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _save_cache(self, key: str, data: dict):
        """Save campaign to cache file."""
        path = os.path.join(self.cache_dir, f"{key}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_cache(self, key: str) -> Optional[dict]:
        """Load campaign from cache file."""
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None

    def clear_cache(self):
        """Clear all cached campaigns."""
        if os.path.exists(self.cache_dir):
            import shutil
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            print(f"  🗑️  Cache cleared: {self.cache_dir}")
