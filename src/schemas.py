"""API request/response schemas for GeoStorm REST endpoints."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from src.models import (
    AlertSeverity,
    AlertType,
    MentionType,
    RunStatus,
    TrendDirection,
    TriggerType,
)

T = TypeVar("T")


# ============================================================================
# Shared
# ============================================================================


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


# ============================================================================
# Project
# ============================================================================


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    brand_name: str | None = Field(default=None, max_length=255)
    brand_aliases: list[str] = Field(default_factory=list)
    brand_description: str | None = None
    brand_website: str | None = None


class UpdateProjectRequest(BaseModel):
    """Request to update a project."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ProjectResponse(BaseModel):
    """Project summary."""

    id: str
    name: str
    description: str | None = None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime
    latest_score: float | None = None
    run_count: int = 0
    active_alert_count: int = 0


class BrandResponse(BaseModel):
    """Brand detail."""

    id: str
    project_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    website: str | None = None
    created_at: datetime
    updated_at: datetime


class CompetitorResponse(BaseModel):
    """Competitor detail."""

    id: str
    project_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    website: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class TermResponse(BaseModel):
    """Term detail."""

    id: str
    project_id: str
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ScheduleResponse(BaseModel):
    """Schedule detail."""

    id: str
    project_id: str
    hour_of_day: int
    days_of_week: list[int]
    is_active: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(BaseModel):
    """Full project detail with related entities."""

    id: str
    name: str
    description: str | None = None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime
    run_count: int = 0
    brand: BrandResponse | None = None
    competitors: list[CompetitorResponse] = Field(default_factory=list)
    terms: list[TermResponse] = Field(default_factory=list)
    schedule: ScheduleResponse | None = None


class ProjectCreatedResponse(BaseModel):
    """Response after creating a project."""

    id: str
    name: str
    brand_id: str
    schedule_id: str
    providers_count: int = 0
    created_at: datetime


# ============================================================================
# Brand
# ============================================================================


class UpdateBrandRequest(BaseModel):
    """Request to update a brand."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = None
    description: str | None = None
    website: str | None = None


# ============================================================================
# Competitor
# ============================================================================


class CreateCompetitorRequest(BaseModel):
    """Request to create a competitor."""

    name: str = Field(..., min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    website: str | None = None


# ============================================================================
# Term
# ============================================================================


class CreateTermRequest(BaseModel):
    """Request to create a term."""

    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None


# ============================================================================
# Schedule
# ============================================================================


class UpdateScheduleRequest(BaseModel):
    """Request to update a schedule."""

    hour_of_day: int | None = Field(default=None, ge=0, le=23)
    days_of_week: list[int] | None = None
    is_active: bool | None = None


# ============================================================================
# Run
# ============================================================================


class RunResponse(BaseModel):
    """Run summary."""

    id: str
    project_id: str
    status: RunStatus
    trigger_type: TriggerType
    triggered_by: str | None = None
    total_queries: int = 0
    completed_queries: int = 0
    failed_queries: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class RunDetailResponse(BaseModel):
    """Run detail with perception data."""

    id: str
    project_id: str
    status: RunStatus
    trigger_type: TriggerType
    triggered_by: str | None = None
    total_queries: int = 0
    completed_queries: int = 0
    failed_queries: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    perception_score: float | None = None
    recommendation_share: float | None = None
    competitors_detected: list[str] = Field(default_factory=list)


class MentionItem(BaseModel):
    """Mention within a response."""

    id: str
    mention_type: MentionType
    target_name: str
    position_chars: int | None = None
    position_words: int | None = None
    list_position: int | None = None
    context_before: str = ""
    context_after: str = ""


class ResponseItem(BaseModel):
    """Response with nested mentions."""

    id: str
    run_id: str
    term_id: str
    term_name: str
    provider_name: str
    model_name: str
    response_text: str
    latency_ms: int | None = None
    cost_usd: float | None = None
    error_message: str | None = None
    created_at: datetime
    mentions: list[MentionItem] = Field(default_factory=list)


# ============================================================================
# Alert
# ============================================================================


class AlertResponse(BaseModel):
    """Alert detail."""

    id: str
    project_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    explanation: str | None = None
    is_acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    created_at: datetime


class AlertConfigItem(BaseModel):
    """Alert configuration item for request/response."""

    channel: str
    endpoint: str
    alert_types: list[AlertType] = Field(default_factory=list)
    min_severity: AlertSeverity = AlertSeverity.INFO
    is_enabled: bool = True


class UpdateAlertConfigRequest(BaseModel):
    """Request to update alert configs."""

    configs: list[AlertConfigItem]


class AlertConfigResponse(BaseModel):
    """Alert configuration detail."""

    id: str
    project_id: str
    channel: str
    endpoint: str
    alert_types: list[AlertType] = Field(default_factory=list)
    min_severity: AlertSeverity = AlertSeverity.INFO
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime


# ============================================================================
# LLM Provider
# ============================================================================


class LLMProviderResponse(BaseModel):
    """LLM provider detail."""

    id: str
    project_id: str
    provider_name: str
    model_name: str
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class CreateProviderRequest(BaseModel):
    """Request to create an LLM provider."""

    provider_name: str = Field(..., min_length=1, max_length=255)
    model_name: str = Field(..., min_length=1, max_length=255)


class UpdateProviderRequest(BaseModel):
    """Request to update an LLM provider."""

    is_enabled: bool | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=255)


# ============================================================================
# Perception
# ============================================================================


class PerceptionDataPoint(BaseModel):
    """Single data point in perception time-series."""

    date: str
    overall_score: float | None = None
    recommendation_share: float | None = None
    position_avg: float | None = None
    competitor_delta: float | None = None
    trend_direction: TrendDirection = TrendDirection.STABLE


class PerceptionResponse(BaseModel):
    """Perception time-series data."""

    project_id: str
    data: list[PerceptionDataPoint] = Field(default_factory=list)


class PerceptionBreakdownByTerm(BaseModel):
    """Per-term breakdown in perception data."""

    term_id: str
    term_name: str
    recommendation_share: float
    position_avg: float | None = None


class PerceptionBreakdownByProvider(BaseModel):
    """Per-provider breakdown in perception data."""

    provider_name: str
    recommendation_share: float
    position_avg: float | None = None


class PerceptionBreakdownResponse(BaseModel):
    """Perception breakdown with per-term and per-provider aggregated scores."""

    project_id: str
    total_responses: int = 0
    brand_mentions: int = 0
    ranked_responses: int = 0
    by_term: list[PerceptionBreakdownByTerm] = Field(default_factory=list)
    by_provider: list[PerceptionBreakdownByProvider] = Field(default_factory=list)


class TrajectoryDataPoint(BaseModel):
    """Single data point in trajectory time-series."""

    date: str
    recommendation_share: float | None = None
    position_avg: float | None = None
    competitor_delta: float | None = None
    trend_direction: TrendDirection = TrendDirection.STABLE


class TrajectoryResponse(BaseModel):
    """Historical trajectory data for a project."""

    project_id: str
    data: list[TrajectoryDataPoint] = Field(default_factory=list)


# ============================================================================
# Setup
# ============================================================================


class SetupStatusResponse(BaseModel):
    """Setup status check."""

    has_api_key: bool = False
    has_projects: bool = False
    project_count: int = 0


class ApiKeyStatusResponse(BaseModel):
    """API key status."""

    configured: bool = False
    source: str | None = None


class AutofillLLMResponse(BaseModel):
    """Structured output expected from the autofill LLM call."""

    project_name: str = Field(description="Short, human-friendly project name (usually the brand name itself)")
    brand_name: str = Field(description="Official brand or product name")
    brand_aliases: list[str] = Field(description="Common alternative names, abbreviations, or misspellings")
    description: str = Field(description="One-sentence description of what this brand/product does")
    competitors: list[str] = Field(description="3-5 direct competitor names")
    monitoring_terms: list[str] = Field(
        description="5-8 short noun phrases that complete 'What are the best options for {term}?' naturally",
    )


class AutofillRequest(BaseModel):
    """Request to autofill project details via AI."""

    input: str = Field(..., min_length=1)


class AutofillResponse(BaseModel):
    """AI-generated project details."""

    project_name: str
    brand_name: str
    brand_aliases: list[str] = Field(default_factory=list)
    description: str
    competitors: list[str] = Field(default_factory=list)
    monitoring_terms: list[str] = Field(default_factory=list)


class StoreApiKeyRequest(BaseModel):
    """Request to store an API key."""

    key: str = Field(..., min_length=1)
