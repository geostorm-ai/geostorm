"""Service for detecting meaningful changes in AI perception and generating alerts."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

import logfire
from pydantic import BaseModel

from src.database import get_db_connection
from src.models import AlertMetadata, AlertSeverity, AlertType, MentionType

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


async def get_baseline(project_id: str, lookback_days: int = 7) -> Baseline:
    """Build a historical baseline from recent perception scores and mentions.

    Returns a Baseline with zeroed values if no historical data is available.
    """
    cutoff = (datetime.now(tz=UTC) - timedelta(days=lookback_days)).isoformat()

    async with get_db_connection() as db:
        # Average recommendation share and position from perception_scores
        cursor = await db.execute(
            "SELECT AVG(recommendation_share) AS avg_share, AVG(position_avg) AS avg_pos"
            " FROM perception_scores"
            " WHERE project_id = ? AND created_at > ?",
            (project_id, cutoff),
        )
        row = await cursor.fetchone()
        avg_share = float(row["avg_share"]) if row and row["avg_share"] is not None else 0.0
        avg_pos = float(row["avg_pos"]) if row and row["avg_pos"] is not None else None

        # Per-provider shares
        cursor = await db.execute(
            "SELECT provider_name, AVG(recommendation_share) AS avg_share"
            " FROM perception_scores"
            " WHERE project_id = ? AND provider_name IS NOT NULL AND created_at > ?"
            " GROUP BY provider_name",
            (project_id, cutoff),
        )
        provider_rows = await cursor.fetchall()
        provider_shares: dict[str, float] = {}
        for pr in provider_rows:
            provider_shares[pr["provider_name"]] = float(pr["avg_share"])

        # Known competitors from mentions in the lookback window
        cursor = await db.execute(
            "SELECT DISTINCT m.target_name"
            " FROM mentions m"
            " JOIN responses r ON m.response_id = r.id"
            " WHERE r.project_id = ? AND m.mention_type = ? AND m.detected_at > ?",
            (project_id, MentionType.COMPETITOR.value, cutoff),
        )
        competitor_rows = await cursor.fetchall()
        known_competitors = {cr["target_name"] for cr in competitor_rows}

    return Baseline(
        avg_recommendation_share=avg_share,
        avg_position=avg_pos,
        known_competitors=known_competitors,
        provider_shares=provider_shares,
    )


async def detect_competitor_emergence(
    project_id: str,
    run_id: str,
    baseline: Baseline,
) -> list[DetectedChange]:
    """Detect competitors that appear for the first time relative to the baseline."""
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT DISTINCT m.target_name"
            " FROM mentions m"
            " JOIN responses r ON m.response_id = r.id"
            " WHERE r.run_id = ? AND r.project_id = ? AND m.mention_type = ?",
            (run_id, project_id, MentionType.COMPETITOR.value),
        )
        rows = await cursor.fetchall()

    changes: list[DetectedChange] = []
    for row in rows:
        name = row["target_name"]
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
    project_id: str,
    run_id: str,
    baseline: Baseline,
) -> list[DetectedChange]:
    """Detect if brand visibility has critically dropped from a strong baseline."""
    async with get_db_connection() as db:
        # Count total non-error responses and brand mentions for this run
        cursor = await db.execute(
            "SELECT COUNT(*) AS total"
            " FROM responses WHERE run_id = ? AND project_id = ? AND error_message IS NULL",
            (run_id, project_id),
        )
        total_row = await cursor.fetchone()
        total = total_row["total"] if total_row else 0

        if total == 0:
            return []

        cursor = await db.execute(
            "SELECT COUNT(DISTINCT r.id) AS brand_count"
            " FROM responses r"
            " JOIN mentions m ON m.response_id = r.id"
            " WHERE r.run_id = ? AND r.project_id = ? AND r.error_message IS NULL"
            "   AND m.mention_type = ?",
            (run_id, project_id, MentionType.BRAND.value),
        )
        brand_row = await cursor.fetchone()
        brand_count = brand_row["brand_count"] if brand_row else 0

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
    project_id: str,  # noqa: ARG001
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
    project_id: str,  # noqa: ARG001
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
    project_id: str,
    run_id: str,
) -> list[DetectedChange]:
    """Detect when different LLM providers give significantly different brand shares."""
    async with get_db_connection() as db:
        # Per-provider brand mention share for this run
        cursor = await db.execute(
            "SELECT r.provider_name,"
            "   COUNT(DISTINCT r.id) AS total,"
            "   COUNT(DISTINCT CASE WHEN m.mention_type = ? THEN r.id END) AS brand_count"
            " FROM responses r"
            " LEFT JOIN mentions m ON m.response_id = r.id AND m.mention_type = ?"
            " WHERE r.run_id = ? AND r.project_id = ? AND r.error_message IS NULL"
            " GROUP BY r.provider_name",
            (MentionType.BRAND.value, MentionType.BRAND.value, run_id, project_id),
        )
        rows = list(await cursor.fetchall())

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


async def run_change_detection(project_id: str, run_id: str) -> list[DetectedChange]:
    """Run all change detectors for a completed monitoring run.

    Returns a combined list of all detected changes.
    """
    baseline = await get_baseline(project_id)

    # Calculate current run metrics for share and position
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS total"
            " FROM responses WHERE run_id = ? AND project_id = ? AND error_message IS NULL",
            (run_id, project_id),
        )
        total_row = await cursor.fetchone()
        total = total_row["total"] if total_row else 0

        current_share = 0.0
        current_position: float | None = None

        if total > 0:
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT r.id) AS brand_count"
                " FROM responses r"
                " JOIN mentions m ON m.response_id = r.id"
                " WHERE r.run_id = ? AND r.project_id = ? AND r.error_message IS NULL"
                "   AND m.mention_type = ?",
                (run_id, project_id, MentionType.BRAND.value),
            )
            brand_row = await cursor.fetchone()
            brand_count = brand_row["brand_count"] if brand_row else 0
            current_share = brand_count / total

            cursor = await db.execute(
                "SELECT AVG(m.list_position) AS avg_pos"
                " FROM mentions m"
                " JOIN responses r ON m.response_id = r.id"
                " WHERE r.run_id = ? AND r.project_id = ? AND r.error_message IS NULL"
                "   AND m.mention_type = ? AND m.list_position IS NOT NULL",
                (run_id, project_id, MentionType.BRAND.value),
            )
            pos_row = await cursor.fetchone()
            if pos_row and pos_row["avg_pos"] is not None:
                current_position = float(pos_row["avg_pos"])

    changes: list[DetectedChange] = []
    changes.extend(await detect_competitor_emergence(project_id, run_id, baseline))
    changes.extend(await detect_disappearance(project_id, run_id, baseline))
    changes.extend(await detect_share_drop(project_id, run_id, baseline, current_share))
    changes.extend(await detect_position_degradation(project_id, run_id, baseline, current_position))
    changes.extend(await detect_model_divergence(project_id, run_id))

    logger.info("Change detection found %d changes for project %s run %s", len(changes), project_id, run_id)
    return changes


async def store_alerts(project_id: str, changes: list[DetectedChange]) -> list[str]:
    """Persist detected changes as alert records.

    Returns the list of newly created alert IDs.
    """
    if not changes:
        return []

    now = datetime.now(tz=UTC).isoformat()
    ids: list[str] = []

    async with get_db_connection() as db:
        for change in changes:
            alert_id = uuid.uuid4().hex
            await db.execute(
                "INSERT INTO alerts"
                " (id, project_id, alert_type, severity, title, message,"
                "  metadata_json, is_acknowledged, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    alert_id,
                    project_id,
                    change.alert_type.value,
                    change.severity.value,
                    change.title,
                    change.message,
                    change.metadata.model_dump_json(),
                    0,
                    now,
                ),
            )
            ids.append(alert_id)
        await db.commit()

    logger.info("Stored %d alerts for project %s", len(ids), project_id)
    return ids


async def detect_and_store_alerts(project_id: str, run_id: str) -> list[str]:
    """Pipeline: run change detection then persist resulting alerts.

    Returns the list of stored alert IDs.
    """
    with logfire.span('change detection', project_id=project_id, run_id=run_id):
        changes = await run_change_detection(project_id, run_id)
        return await store_alerts(project_id, changes)
