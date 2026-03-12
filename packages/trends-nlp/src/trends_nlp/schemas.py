"""
Shared Data Models — Service Contracts
=========================================
Pydantic models defining data contracts between services.

  Ingestion → Intelligence → Delivery → Attribution

Each service speaks through these models, enabling:
  - Type safety at service boundaries
  - Automatic JSON serialization
  - Self-documenting API contracts
  - Independent service evolution
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class Platform(str, Enum):
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"
    NEWSAPI = "newsapi"
    RSS = "rss"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"

class TrendState(str, Enum):
    BASELINE = "BASELINE"
    EMERGING = "EMERGING"
    GROWING = "GROWING"
    PEAKING = "PEAKING"
    VIRAL = "VIRAL"
    DECLINING = "DECLINING"

class CampaignStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"

class ConversationState(str, Enum):
    IDLE = "IDLE"
    TREND_ALERTED = "TREND_ALERTED"
    DRAFTING = "DRAFTING"
    DRAFT_READY = "DRAFT_READY"
    AWAITING_FEEDBACK = "AWAITING_FEEDBACK"
    APPROVED = "APPROVED"
    SENT = "SENT"
    DISCARDED = "DISCARDED"


# ═══════════════════════════════════════════════════════════
# Ingestion Service Models
# ═══════════════════════════════════════════════════════════

class RawItem(BaseModel):
    """Raw content item from any data source."""
    id: str
    title: str
    body: Optional[str] = None
    source: str
    platform: str
    author: Optional[str] = None
    url: Optional[str] = None
    score: int = 0
    num_comments: int = 0
    published_at: Optional[datetime] = None
    collected_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)

class SentimentResult(BaseModel):
    score: float = Field(ge=-1.0, le=1.0)
    label: str

class EnrichedItem(BaseModel):
    """Item after NLP pipeline."""
    id: str
    sentiment: SentimentResult
    keywords: list[str] = Field(default_factory=list)
    topic_id: Optional[str] = None
    taxonomy_category: Optional[str] = None
    embedding: Optional[list[float]] = None
    enriched_at: datetime = Field(default_factory=datetime.now)


# ═══════════════════════════════════════════════════════════
# Intelligence Service Models
# ═══════════════════════════════════════════════════════════

class TrendMetrics(BaseModel):
    velocity: float = 0.0
    avg_sentiment: float = 0.0
    current_count: int = 0
    baseline: int = 0
    peak_count: int = 0
    platforms: list[str] = Field(default_factory=list)

class TrendReport(BaseModel):
    topic_id: str
    current_state: TrendState
    metrics: TrendMetrics
    history: list[dict] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.now)

class EmailBody(BaseModel):
    headline: str
    opening: str
    body: str
    cta_text: str
    cta_url_placeholder: str = ""
    closing: str

class CampaignSettings(BaseModel):
    recommended_send_day: str = "Tuesday"
    recommended_send_time: str = "9:00 AM"
    audience_segment: str = "all"
    estimated_open_rate: str = "25-30%"
    why_now: str = ""

class GeneratedCampaign(BaseModel):
    topic_id: str
    subject_lines: list[str]
    preview_text: str = ""
    email_body: EmailBody
    campaign_settings: CampaignSettings
    llm_provider: str = ""
    llm_model: str = ""
    revision_count: int = 0

class TrendAlert(BaseModel):
    topic_id: str
    topic_name: str
    current_state: TrendState
    previous_state: TrendState = TrendState.BASELINE
    velocity: float
    sentiment: float = 0.0
    mention_count: int = 0
    baseline: int = 0
    platforms: list[str] = Field(default_factory=list)
    demographics: Optional[dict] = None
    reason: str = ""


# ═══════════════════════════════════════════════════════════
# Delivery Service Models
# ═══════════════════════════════════════════════════════════

class EmailDraft(BaseModel):
    campaign_id: str
    topic_id: str
    subject: str
    preview_url: Optional[str] = None
    segment_tag: Optional[str] = None
    status: CampaignStatus = CampaignStatus.DRAFT

class CampaignPerformance(BaseModel):
    campaign_id: str
    emails_sent: int = 0
    unique_opens: int = 0
    open_rate: float = 0.0
    unique_clicks: int = 0
    click_rate: float = 0.0
    unsubscribes: int = 0


# ═══════════════════════════════════════════════════════════
# Attribution Service Models
# ═══════════════════════════════════════════════════════════

class Customer(BaseModel):
    id: str
    display_name: str
    email: str
    city: Optional[str] = None
    state: Optional[str] = None
    segment: Optional[str] = None
    lifetime_value: float = 0.0

class SalesReceipt(BaseModel):
    id: str
    customer_id: str
    date: str
    total: float
    items: list[dict] = Field(default_factory=list)

class RevenueMetrics(BaseModel):
    post_campaign: float = 0.0
    pre_campaign_baseline: float = 0.0
    lift: float = 0.0
    lift_percent: float = 0.0
    avg_order_value: float = 0.0

class RecipientMetrics(BaseModel):
    total: int = 0
    matched_in_revenue: int = 0
    purchased: int = 0
    conversion_rate: float = 0.0

class ProductBreakdown(BaseModel):
    product_name: str
    units_sold: int = 0
    revenue: float = 0.0

class BridgeMeta(BaseModel):
    join_key: str = "email_address"
    source_marketing: str = "Email Campaign Platform"
    source_revenue: str = "Revenue Platform"
    data_source_mode: str = "SIMULATED"

class ROIReport(BaseModel):
    campaign_id: Optional[str] = None
    topic_id: Optional[str] = None
    segment_tag: Optional[str] = None
    send_date: str = ""
    attribution_window_days: int = 7
    recipients: RecipientMetrics = Field(default_factory=RecipientMetrics)
    revenue: RevenueMetrics = Field(default_factory=RevenueMetrics)
    topic_attribution: dict = Field(default_factory=dict)
    product_breakdown: list[ProductBreakdown] = Field(default_factory=list)
    roi_summary: dict = Field(default_factory=dict)
    bridge_meta: BridgeMeta = Field(default_factory=BridgeMeta)

class Customer360(BaseModel):
    email: str
    customer: Customer
    revenue_data: dict = Field(default_factory=dict)
    marketing_data: dict = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════
# API Request/Response Models
# ═══════════════════════════════════════════════════════════

class GenerateCampaignRequest(BaseModel):
    topic_id: str
    segment_tag: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    industry: str = "cafe"

class RefineCampaignRequest(BaseModel):
    feedback: str

class SendCampaignRequest(BaseModel):
    segment_tag: Optional[str] = None
    schedule_at: Optional[datetime] = None

class ComputeROIRequest(BaseModel):
    topic_id: str
    segment_tag: Optional[str] = None
    send_date: Optional[str] = None
    attribution_window_days: int = 7
    use_live_api: bool = False

class HealthResponse(BaseModel):
    service: str
    status: str
    dependencies: dict = Field(default_factory=dict)
