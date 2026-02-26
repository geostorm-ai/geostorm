"""Service for detecting meaningful changes in AI perception and generating alerts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import logfire
from pydantic import BaseModel

from src.models import AlertMetadata, AlertSeverity, AlertType

if TYPE_CHECKING:
    from src.repos.alert_repo import AlertRepo
    from src.repos.change_detection_repo import ChangeDetectionRepo

logger = logging.getLogger(__name__)

DISAPPEARANCE_HIGH_THRESHOLD = 0.8
DISAPPEARANCE_LOW_THRESHOLD = 0.2
SHARE_DROP_THRESHOLD = 0.15
POSITION_DEGRADATION_THRESHOLD = 2.0
MODEL_DIVERGENCE_THRESHOLD = 0.20


class Baseline(BaseModel):
    """Historical baseline metrics for a project."""

    avg_recommendation_share: float
    avg_position: float | None
    known_competitors: set[str]
    provider_shares: dict[str, float]


class DetectedChange(BaseModel):
    """A single detected change that may become an alert."""

    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    metadata: AlertMetadata


class ChangeDetectionService:
    def __init__(self, change_detection_repo: ChangeDetectionRepo, alert_repo: AlertRepo) -> None:
        self._change_detection_repo = change_detection_repo
        self._alert_repo = alert_repo

    async def get_baseline(self, project_id: str, lookback_days: int = 7) -> Baseline:
        """Build a historical baseline from recent perception scores and mentions."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=lookback_days)).isoformat()

        row = await self._change_detection_repo.get_baseline_averages(project_id, cutoff)
        avg_share = float(row["avg_share"]) if row and row["avg_share"] is not None else 0.0
        avg_pos = float(row["avg_pos"]) if row and row["avg_pos"] is not None else None

        provider_rows = await self._change_detection_repo.get_baseline_provider_shares(project_id, cutoff)
        provider_shares: dict[str, float] = {}
        for pr in provider_rows:
            provider_shares[pr["provider_name"]] = float(pr["avg_share"])

        known_competitors = await self._change_detection_repo.get_baseline_competitors(project_id, cutoff)

        return Baseline(
            avg_recommendation_share=avg_share,
            avg_position=avg_pos,
            known_competitors=known_competitors,
            provider_shares=provider_shares,
        )

    async def detect_competitor_emergence(
        self,
        project_id: str,
        run_id: str,
        baseline: Baseline,
    ) -> list[DetectedChange]:
        """Detect competitors that appear for the first time relative to the baseline."""
        names = await self._change_detection_repo.get_run_competitor_names(run_id, project_id)

        changes: list[DetectedChange] = []
        for name in names:
            if name not in baseline.known_competitors:
                changes.append(
                    DetectedChange(
                        alert_type=AlertType.COMPETITOR_EMERGENCE,
                        severity=AlertSeverity.CRITICAL,
                        title=f"New competitor detected: {name}",
                        message=f"{name} now appears in AI recommendations for your monitored terms",
                        metadata=AlertMetadata(
                            competitor_name=name,
                            run_id=run_id,
                        ),
                    ),
                )
        return changes

    async def detect_disappearance(
        self,
        project_id: str,
        run_id: str,
        baseline: Baseline,
    ) -> list[DetectedChange]:
        """Detect if brand visibility has critically dropped from a strong baseline."""
        total = await self._change_detection_repo.count_run_responses(run_id, project_id)
        if total == 0:
            return []

        brand_count = await self._change_detection_repo.count_brand_mentions_in_run(run_id, project_id)
        current_share = brand_count / total
        baseline_high = baseline.avg_recommendation_share >= DISAPPEARANCE_HIGH_THRESHOLD
        if baseline_high and current_share < DISAPPEARANCE_LOW_THRESHOLD:
            baseline_pct = round(baseline.avg_recommendation_share * 100)
            current_pct = round(current_share * 100)
            return [
                DetectedChange(
                    alert_type=AlertType.DISAPPEARANCE,
                    severity=AlertSeverity.CRITICAL,
                    title="Brand visibility critically low",
                    message=f"Brand mention share dropped from {baseline_pct}% to {current_pct}%",
                    metadata=AlertMetadata(
                        previous_value=baseline.avg_recommendation_share,
                        current_value=current_share,
                        run_id=run_id,
                    ),
                ),
            ]
        return []

    async def detect_share_drop(
        self,
        project_id: str,  # noqa: ARG002
        run_id: str,
        baseline: Baseline,
        current_share: float,
    ) -> list[DetectedChange]:
        """Detect a significant drop in recommendation share (>15pp)."""
        drop = baseline.avg_recommendation_share - current_share
        if drop > SHARE_DROP_THRESHOLD:
            baseline_pct = round(baseline.avg_recommendation_share * 100)
            current_pct = round(current_share * 100)
            return [
                DetectedChange(
                    alert_type=AlertType.RECOMMENDATION_SHARE_DROP,
                    severity=AlertSeverity.WARNING,
                    title="Recommendation share declining",
                    message=f"Brand recommendation share dropped from {baseline_pct}% to {current_pct}%",
                    metadata=AlertMetadata(
                        threshold=SHARE_DROP_THRESHOLD,
                        previous_value=baseline.avg_recommendation_share,
                        current_value=current_share,
                        run_id=run_id,
                    ),
                ),
            ]
        return []

    async def detect_position_degradation(
        self,
        project_id: str,  # noqa: ARG002
        run_id: str,
        baseline: Baseline,
        current_position: float | None,
    ) -> list[DetectedChange]:
        """Detect when list position worsens by 2+ places compared to baseline."""
        if current_position is None or baseline.avg_position is None:
            return []
        degradation = current_position - baseline.avg_position
        if degradation >= POSITION_DEGRADATION_THRESHOLD:
            return [
                DetectedChange(
                    alert_type=AlertType.POSITION_DEGRADATION,
                    severity=AlertSeverity.WARNING,
                    title="Position degradation detected",
                    message=(
                        f"Average list position worsened from {baseline.avg_position:.1f}"
                        f" to {current_position:.1f}"
                    ),
                    metadata=AlertMetadata(
                        threshold=POSITION_DEGRADATION_THRESHOLD,
                        previous_value=baseline.avg_position,
                        current_value=current_position,
                        run_id=run_id,
                    ),
                ),
            ]
        return []

    async def detect_model_divergence(
        self,
        project_id: str,
        run_id: str,
    ) -> list[DetectedChange]:
        """Detect when different LLM providers give significantly different brand shares."""
        rows = await self._change_detection_repo.get_per_provider_brand_shares(run_id, project_id)

        if len(rows) < 2:  # noqa: PLR2004
            return []

        provider_shares: dict[str, float] = {}
        for row in rows:
            total = row["total"]
            brand_count = row["brand_count"]
            share = brand_count / total if total > 0 else 0.0
            provider_shares[row["provider_name"]] = share

        max_share = max(provider_shares.values())
        min_share = min(provider_shares.values())

        if max_share - min_share > MODEL_DIVERGENCE_THRESHOLD:
            max_provider = next(p for p, s in provider_shares.items() if s == max_share)
            min_provider = next(p for p, s in provider_shares.items() if s == min_share)
            return [
                DetectedChange(
                    alert_type=AlertType.MODEL_DIVERGENCE,
                    severity=AlertSeverity.WARNING,
                    title="Model divergence detected",
                    message=(
                        f"{max_provider} mentions brand {round(max_share * 100)}% of the time"
                        f" while {min_provider} only {round(min_share * 100)}%"
                    ),
                    metadata=AlertMetadata(
                        threshold=MODEL_DIVERGENCE_THRESHOLD,
                        current_value=max_share - min_share,
                        run_id=run_id,
                    ),
                ),
            ]
        return []

    async def run_change_detection(self, project_id: str, run_id: str) -> list[DetectedChange]:
        """Run all change detectors for a completed monitoring run."""
        baseline = await self.get_baseline(project_id)

        total = await self._change_detection_repo.count_run_responses(run_id, project_id)
        current_share = 0.0
        current_position: float | None = None

        if total > 0:
            brand_count = await self._change_detection_repo.count_brand_mentions_in_run(run_id, project_id)
            current_share = brand_count / total
            current_position = await self._change_detection_repo.get_avg_brand_position(run_id, project_id)

        changes: list[DetectedChange] = []
        changes.extend(await self.detect_competitor_emergence(project_id, run_id, baseline))
        changes.extend(await self.detect_disappearance(project_id, run_id, baseline))
        changes.extend(await self.detect_share_drop(project_id, run_id, baseline, current_share))
        changes.extend(await self.detect_position_degradation(project_id, run_id, baseline, current_position))
        changes.extend(await self.detect_model_divergence(project_id, run_id))

        logger.info("Change detection found %d changes for project %s run %s", len(changes), project_id, run_id)
        return changes

    async def store_alerts(self, project_id: str, changes: list[DetectedChange]) -> list[str]:
        """Persist detected changes as alert records."""
        if not changes:
            return []

        alerts_data: list[tuple[str, str, str, str, str, str]] = [
            (
                project_id,
                change.alert_type.value,
                change.severity.value,
                change.title,
                change.message,
                change.metadata.model_dump_json(),
            )
            for change in changes
        ]

        ids = await self._alert_repo.store_alerts(alerts_data)
        logger.info("Stored %d alerts for project %s", len(ids), project_id)
        return ids

    async def detect_and_store_alerts(self, project_id: str, run_id: str) -> list[str]:
        """Pipeline: run change detection then persist resulting alerts."""
        with logfire.span("change detection", project_id=project_id, run_id=run_id):
            changes = await self.run_change_detection(project_id, run_id)
            return await self.store_alerts(project_id, changes)
