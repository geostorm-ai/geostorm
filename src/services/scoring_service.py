"""Service for calculating perception scores from monitoring run data."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import logfire
from pydantic import BaseModel

from src.database import get_db_connection
from src.models import MentionType, PeriodType, TrendDirection

logger = logging.getLogger(__name__)

TREND_THRESHOLD = 0.05
SHARE_WEIGHT = 0.50
POSITION_WEIGHT = 0.30
DELTA_WEIGHT = 0.20
POSITION_MAX = 10.0
NEUTRAL_SCORE = 50.0


class ScoreResult(BaseModel):
    """Intermediate scoring result before database storage."""

    term_id: str | None
    provider_name: str | None
    recommendation_share: float
    position_avg: float | None
    competitor_delta: float | None
    overall_score: float
    trend_direction: TrendDirection


def calculate_trend(current_share: float, previous_share: float | None) -> TrendDirection:
    """Determine trend direction by comparing current and previous recommendation share.

    Returns UP if the share increased by more than 5 percentage points,
    DOWN if it decreased by more than 5pp, or STABLE otherwise.
    """
    if previous_share is None:
        return TrendDirection.STABLE
    diff = current_share - previous_share
    if diff > TREND_THRESHOLD:
        return TrendDirection.UP
    if diff < -TREND_THRESHOLD:
        return TrendDirection.DOWN
    return TrendDirection.STABLE


def calculate_overall_score(
    recommendation_share: float,
    position_avg: float | None,
    competitor_delta: float | None,
) -> float:
    """Compute a composite 0-100 perception score.

    Weights: 50% recommendation share, 30% position quality, 20% competitor delta.
    """
    share_score = recommendation_share * 100.0

    if position_avg is not None:
        position_score = max(0.0, (POSITION_MAX - position_avg) / POSITION_MAX * 100.0)
    else:
        position_score = NEUTRAL_SCORE

    if competitor_delta is not None:
        delta_score = max(0.0, min(100.0, (competitor_delta + 1.0) / 2.0 * 100.0))
    else:
        delta_score = NEUTRAL_SCORE

    raw = SHARE_WEIGHT * share_score + POSITION_WEIGHT * position_score + DELTA_WEIGHT * delta_score
    return max(0.0, min(100.0, raw))


async def get_previous_score(
    project_id: str,
    term_id: str | None,
    provider_name: str | None,
    lookback_days: int = 7,
) -> float | None:
    """Fetch the most recent recommendation_share for the given project/term/provider.

    Returns None if no historical score exists within the lookback window.
    """
    cutoff = (datetime.now(tz=UTC) - timedelta(days=lookback_days)).isoformat()
    async with get_db_connection() as db:
        if term_id is not None and provider_name is not None:
            cursor = await db.execute(
                "SELECT recommendation_share FROM perception_scores"
                " WHERE project_id = ? AND term_id = ? AND provider_name = ? AND created_at > ?"
                " ORDER BY created_at DESC LIMIT 1",
                (project_id, term_id, provider_name, cutoff),
            )
        elif term_id is not None:
            cursor = await db.execute(
                "SELECT recommendation_share FROM perception_scores"
                " WHERE project_id = ? AND term_id = ? AND provider_name IS NULL AND created_at > ?"
                " ORDER BY created_at DESC LIMIT 1",
                (project_id, term_id, cutoff),
            )
        elif provider_name is not None:
            cursor = await db.execute(
                "SELECT recommendation_share FROM perception_scores"
                " WHERE project_id = ? AND term_id IS NULL AND provider_name = ? AND created_at > ?"
                " ORDER BY created_at DESC LIMIT 1",
                (project_id, provider_name, cutoff),
            )
        else:
            cursor = await db.execute(
                "SELECT recommendation_share FROM perception_scores"
                " WHERE project_id = ? AND term_id IS NULL AND provider_name IS NULL AND created_at > ?"
                " ORDER BY created_at DESC LIMIT 1",
                (project_id, cutoff),
            )
        row = await cursor.fetchone()
    if row is None:
        return None
    return float(row["recommendation_share"])


async def calculate_run_scores(run_id: str, project_id: str) -> list[ScoreResult]:
    """Calculate perception scores for every (term, provider) group in a run.

    Also produces a project-level aggregate with term_id=None and provider_name=None.
    """
    async with get_db_connection() as db:
        # Fetch all non-error responses for this run
        cursor = await db.execute(
            "SELECT r.id AS response_id, r.term_id, r.provider_name"
            " FROM responses r"
            " WHERE r.run_id = ? AND r.error_message IS NULL",
            (run_id,),
        )
        responses = await cursor.fetchall()

        if not responses:
            return []

        response_ids = [r["response_id"] for r in responses]
        placeholders = ",".join("?" for _ in response_ids)

        # Fetch all mentions for those responses
        cursor = await db.execute(
            f"SELECT m.response_id, m.mention_type, m.target_name, m.list_position"
            f" FROM mentions m WHERE m.response_id IN ({placeholders})",
            response_ids,
        )
        mentions = await cursor.fetchall()

    # Build lookup: response_id -> list of mentions
    mention_map: dict[str, list[dict[str, object]]] = defaultdict(list)
    for m in mentions:
        mention_map[m["response_id"]].append({
            "mention_type": m["mention_type"],
            "target_name": m["target_name"],
            "list_position": m["list_position"],
        })

    # Group responses by (term_id, provider_name)
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in responses:
        key = (r["term_id"], r["provider_name"])
        groups[key].append(r["response_id"])

    results: list[ScoreResult] = []

    for (term_id, provider_name), resp_ids in groups.items():
        score = await _score_group(
            resp_ids, mention_map, project_id, term_id, provider_name,
        )
        results.append(score)

    # Project-level aggregate (term_id=None, provider_name=None)
    all_resp_ids = [r["response_id"] for r in responses]
    aggregate = await _score_group(all_resp_ids, mention_map, project_id, None, None)
    results.append(aggregate)

    return results


async def _score_group(
    resp_ids: list[str],
    mention_map: dict[str, list[dict[str, object]]],
    project_id: str,
    term_id: str | None,
    provider_name: str | None,
) -> ScoreResult:
    """Score a group of responses for a given (term_id, provider_name) slice."""
    total = len(resp_ids)
    brand_count = 0
    brand_positions: list[int] = []
    competitor_shares: dict[str, int] = defaultdict(int)

    for rid in resp_ids:
        has_brand = False
        response_competitors: set[str] = set()
        for m in mention_map.get(rid, []):
            if m["mention_type"] == MentionType.BRAND.value:
                has_brand = True
                if m["list_position"] is not None:
                    brand_positions.append(int(str(m["list_position"])))
            elif m["mention_type"] == MentionType.COMPETITOR.value:
                response_competitors.add(str(m["target_name"]))
        if has_brand:
            brand_count += 1
        for comp in response_competitors:
            competitor_shares[comp] += 1

    recommendation_share = brand_count / total if total > 0 else 0.0
    position_avg = sum(brand_positions) / len(brand_positions) if brand_positions else None

    # Competitor delta: brand share minus top competitor share
    competitor_delta: float | None = None
    if competitor_shares:
        top_competitor_share = max(competitor_shares.values()) / total
        competitor_delta = recommendation_share - top_competitor_share

    overall = calculate_overall_score(recommendation_share, position_avg, competitor_delta)
    previous = await get_previous_score(project_id, term_id, provider_name)
    trend = calculate_trend(recommendation_share, previous)

    return ScoreResult(
        term_id=term_id,
        provider_name=provider_name,
        recommendation_share=recommendation_share,
        position_avg=position_avg,
        competitor_delta=competitor_delta,
        overall_score=overall,
        trend_direction=trend,
    )


async def store_scores(
    project_id: str,
    scores: list[ScoreResult],
    period_type: PeriodType = PeriodType.DAILY,
) -> list[str]:
    """Persist a list of score results into the perception_scores table.

    Returns the list of newly created score IDs.
    """
    if not scores:
        return []

    now = datetime.now(tz=UTC).isoformat()
    ids: list[str] = []

    async with get_db_connection() as db:
        for score in scores:
            score_id = uuid.uuid4().hex
            await db.execute(
                "INSERT INTO perception_scores"
                " (id, project_id, term_id, provider_name, recommendation_share,"
                "  position_avg, competitor_delta, overall_score, trend_direction,"
                "  period_type, period_start, period_end, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    score_id,
                    project_id,
                    score.term_id,
                    score.provider_name,
                    score.recommendation_share,
                    score.position_avg,
                    score.competitor_delta,
                    score.overall_score,
                    score.trend_direction.value,
                    period_type.value,
                    now,
                    now,
                    now,
                ),
            )
            ids.append(score_id)
        await db.commit()

    logger.info("Stored %d perception scores for project %s", len(ids), project_id)
    return ids


async def calculate_and_store_scores(run_id: str, project_id: str) -> list[str]:
    """Pipeline: calculate run scores then persist them.

    Returns the list of stored score IDs.
    """
    with logfire.span('score calculation', run_id=run_id, project_id=project_id):
        scores = await calculate_run_scores(run_id, project_id)
        return await store_scores(project_id, scores)
