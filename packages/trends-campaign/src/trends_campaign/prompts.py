"""
Campaign Prompts — RAG-Grounded Prompt Engineering
=====================================================
Prompts that turn trend data + real posts into campaign content.

Key design principle:
  We don't just say "write an email about cortado."
  We feed the LLM actual posts from our enriched data as context.
  This grounds the output in real trend data — no hallucination.

Why structured JSON output:
  - Deterministic parsing (no regex scraping)
  - Works across all LLM providers
  - Easy to cache and validate
"""


SYSTEM_PROMPT = """You are an expert email marketing strategist.
Your job is to help small business owners create effective, trend-aware email campaigns.

You write in a warm, confident, actionable tone — never salesy or generic.
You understand what makes people open emails and click through.
You always ground your recommendations in the specific trend data provided.

IMPORTANT: Always respond with valid JSON only. No markdown, no backticks, no explanation outside the JSON."""


def build_campaign_prompt(
    topic_name: str,
    trend_state: str,
    velocity: float,
    sentiment: float,
    mention_count: int,
    peak_count: int,
    baseline: int,
    platforms: list,
    top_keywords: list,
    sample_posts: list,
    industry: str = "cafe",
    audience_segment: str = "all subscribers",
) -> str:
    """
    Build a RAG-grounded prompt for campaign generation.

    The sample_posts are REAL posts from our enriched data — this is the RAG context
    that grounds the LLM's output in actual trend data rather than generic content.
    """

    # Format sample posts as context
    posts_context = ""
    for i, post in enumerate(sample_posts[:8], 1):
        text = post.get("cleaned_text", post.get("text", ""))[:200]
        platform = post.get("platform", "unknown")
        sentiment_label = post.get("nlp", {}).get("sentiment", {}).get("label", "neutral")
        posts_context += f"  {i}. [{platform}] ({sentiment_label}) {text}\n"

    # Format platforms
    platforms_str = ", ".join(platforms) if platforms else "various"

    # Format keywords
    keywords_str = ", ".join(top_keywords[:10]) if top_keywords else topic_name

    # Sentiment description
    if sentiment > 0.2:
        sentiment_desc = "very positive"
    elif sentiment > 0.05:
        sentiment_desc = "positive"
    elif sentiment > -0.05:
        sentiment_desc = "neutral"
    elif sentiment > -0.2:
        sentiment_desc = "slightly negative"
    else:
        sentiment_desc = "negative"

    # State-specific strategy guidance
    state_guidance = {
        "VIRAL": "This trend is EXPLODING right now. Create urgency — 'everyone is talking about this.' Capitalize on FOMO. Send ASAP.",
        "PEAKING": "This trend is at its peak. Time-sensitive content works best. Reference how popular it is. This is the last best window to ride it.",
        "GROWING": "This trend is gaining momentum fast. Position the business as an early adopter. 'Get ahead of the curve' messaging works well.",
        "EMERGING": "This trend is just starting to surface. Educational content works best — introduce the concept. 'Have you heard about...' angle.",
        "DECLINING": "This trend is past its peak. Shift to evergreen content. 'Lessons learned' or 'what's next' angle. Don't oversell a fading trend.",
        "BASELINE": "This is a steady, established topic. Focus on fresh angles or seasonal hooks rather than trend urgency.",
    }
    strategy = state_guidance.get(trend_state, state_guidance["BASELINE"])

    prompt = f"""Generate an email marketing campaign for a {industry} business based on the following trend data.

═══ TREND DATA (from our Marketing Trends Engine) ═══
Topic: {topic_name}
Current State: {trend_state}
Velocity: {velocity:+.0f}% above baseline
Current Mentions: {mention_count}/day (baseline: {baseline}/day, peak: {peak_count}/day)
Sentiment: {sentiment_desc} ({sentiment:+.2f})
Active Platforms: {platforms_str}
Top Keywords: {keywords_str}

═══ STRATEGY GUIDANCE ═══
{strategy}

═══ REAL POSTS FROM THE WEB (RAG context — use these for tone and angle) ═══
{posts_context}
═══ CAMPAIGN PARAMETERS ═══
Industry: {industry}
Target Audience: {audience_segment}

═══ GENERATE CAMPAIGN ═══
Respond with ONLY this JSON structure (no other text):

{{
  "subject_lines": [
    "Subject line option 1 (under 50 chars, compelling)",
    "Subject line option 2 (curiosity-driven)",
    "Subject line option 3 (benefit-focused)"
  ],
  "preview_text": "Preview text that appears after subject in inbox (under 100 chars)",
  "email_body": {{
    "headline": "Main headline for the email (attention-grabbing, 8-12 words)",
    "opening": "Opening paragraph (2-3 sentences, hook the reader, reference the trend)",
    "body": "Main content (3-4 sentences, value proposition, what the business offers related to this trend)",
    "cta_text": "Call to action button text (2-5 words)",
    "cta_url_placeholder": "Description of what the CTA links to (e.g., 'menu page', 'shop page')",
    "closing": "Brief closing line (1 sentence, warm and personal)"
  }},
  "campaign_settings": {{
    "recommended_send_day": "Best day of week to send",
    "recommended_send_time": "Best time to send (e.g., '10:00 AM')",
    "audience_segment": "{audience_segment}",
    "estimated_open_rate": "Predicted open rate as percentage string",
    "why_now": "One sentence explaining why this campaign should go out now based on the trend data"
  }}
}}"""

    return prompt


def build_subject_line_prompt(topic_name: str, industry: str, count: int = 5) -> str:
    """Generate just subject lines — useful for A/B testing."""
    return f"""Generate {count} email subject lines for a {industry} business about the trending topic "{topic_name}".

Rules:
- Under 50 characters each
- Mix of styles: curiosity, benefit, urgency, social proof
- No ALL CAPS or excessive punctuation

Respond with ONLY a JSON array:
["Subject line 1", "Subject line 2", ...]"""
