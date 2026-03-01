"""Pydantic models for GeoStorm data layer."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ============================================================================
# Enums (all StrEnum)
# ============================================================================


class RunStatus(StrEnum):
    """Status of a monitoring run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerType(StrEnum):
    """How a run was triggered."""

    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class AlertType(StrEnum):
    """Types of alerts the system can generate."""

    COMPETITOR_EMERGENCE = "competitor_emergence"
    CONFIGURATION_ERROR = "configuration_error"
    DISAPPEARANCE = "disappearance"
    RECOMMENDATION_SHARE_DROP = "recommendation_share_drop"
    POSITION_DEGRADATION = "position_degradation"
    MODEL_DIVERGENCE = "model_divergence"
    CITATION_DOMAIN_SHIFT = "citation_domain_shift"


class AlertSeverity(StrEnum):
    """Severity levels for alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(StrEnum):
    """Delivery channels for alerts."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class TrendDirection(StrEnum):
    """Trend direction indicators."""

    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class MentionType(StrEnum):
    """Type of mention detected in a response."""

    BRAND = "brand"
    COMPETITOR = "competitor"


class PeriodType(StrEnum):
    """Period type for perception scores."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ============================================================================
# Pydantic Models
# ============================================================================


class Project(BaseModel):
    """A monitored software project."""

    id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime


class Brand(BaseModel):
    """The software being tracked in a project (1:1 with Project)."""

    id: str
    project_id: str
    name: str = Field(..., min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    website: str | None = None
    created_at: datetime
    updated_at: datetime


class Competitor(BaseModel):
    """Competitor brand to track against."""

    id: str
    project_id: str
    name: str = Field(..., min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    website: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ProjectTerm(BaseModel):
    """A term/keyword to monitor."""

    id: str
    project_id: str
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ProjectSchedule(BaseModel):
    """Schedule for monitoring a project (one per project)."""

    id: str
    project_id: str
    hour_of_day: int = Field(..., ge=0, le=23)
    days_of_week: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    is_active: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LLMProviderConfig(BaseModel):
    """Configured LLM provider for a project."""

    id: str
    project_id: str
    provider_name: str
    model_name: str
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class Run(BaseModel):
    """A batch execution record for monitoring."""

    id: str
    project_id: str
    status: RunStatus = RunStatus.PENDING
    trigger_type: TriggerType
    triggered_by: str | None = None
    total_queries: int = 0
    completed_queries: int = 0
    failed_queries: int = 0
    scheduled_for: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class Response(BaseModel):
    """Individual LLM response for a term x provider combination."""

    id: str
    run_id: str
    project_id: str
    term_id: str
    provider_name: str
    model_name: str
    response_text: str
    latency_ms: int | None = None
    token_count_prompt: int | None = None
    token_count_completion: int | None = None
    cost_usd: float | None = None
    error_message: str | None = None
    created_at: datetime


class Mention(BaseModel):
    """Detected software mention in a response."""

    id: str
    response_id: str
    mention_type: MentionType
    target_name: str
    position_chars: int | None = None
    position_words: int | None = None
    list_position: int | None = None
    context_before: str = ""
    context_after: str = ""
    detected_at: datetime


class Citation(BaseModel):
    """URL citation detected in a response."""

    id: str
    response_id: str
    url: str
    domain: str
    is_brand_domain: bool = False
    is_competitor_domain: bool = False
    competitor_id: str | None = None
    detected_at: datetime


class PerceptionScore(BaseModel):
    """Aggregated perception metrics for a project."""

    id: str
    project_id: str
    term_id: str | None = None
    provider_name: str | None = None
    recommendation_share: float = Field(..., ge=0, le=1)
    position_avg: float | None = None
    competitor_delta: float | None = None
    overall_score: float | None = None
    trend_direction: TrendDirection = TrendDirection.STABLE
    period_type: PeriodType = PeriodType.DAILY
    period_start: datetime
    period_end: datetime
    created_at: datetime


class AlertMetadata(BaseModel):
    """Structured metadata for an alert."""

    threshold: float | None = None
    current_value: float | None = None
    previous_value: float | None = None
    competitor_name: str | None = None
    term_id: str | None = None
    run_id: str | None = None


class Alert(BaseModel):
    """Generated alert record."""

    id: str
    project_id: str
    alert_type: AlertType
    severity: AlertSeverity = AlertSeverity.INFO
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=2000)
    metadata: AlertMetadata | None = None
    explanation: str | None = None
    is_acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    created_at: datetime


class AlertConfig(BaseModel):
    """User alert notification preferences."""

    id: str
    project_id: str
    channel: AlertChannel
    endpoint: str
    alert_types: list[AlertType] = Field(default_factory=list)
    min_severity: AlertSeverity = AlertSeverity.INFO
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class Setting(BaseModel):
    """Key-value application setting."""

    key: str
    value: str
    updated_at: datetime
