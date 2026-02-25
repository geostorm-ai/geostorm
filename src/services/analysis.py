"""Analysis pipeline orchestrator for GeoStorm monitoring runs."""

from __future__ import annotations

import json
import logging

import logfire

from src.database import get_db_connection
from src.notifications.dispatcher import dispatch_alerts
from src.services.change_detection import detect_and_store_alerts
from src.services.mention_service import detect_and_store_mentions_for_response
from src.services.scoring_service import calculate_and_store_scores

logger = logging.getLogger(__name__)


async def analyze_run(run_id: str, project_id: str) -> None:
    """Run the full analysis pipeline for a completed monitoring run.

    Steps:
    1. Load brand name, aliases, competitors from DB
    2. Load all non-error responses for this run
    3. For each response: detect and store mentions
    4. Calculate and store perception scores
    5. Detect changes and store alerts

    Errors are logged but do NOT fail the run.
    """
    with logfire.span('analysis pipeline', run_id=run_id, project_id=project_id):
        # 1. Load brand info
        async with get_db_connection() as db:
            cursor = await db.execute(
                "SELECT name, aliases_json FROM brands WHERE project_id = ?",
                (project_id,),
            )
            brand_row = await cursor.fetchone()

            if not brand_row:
                logger.warning("No brand configured for project %s, skipping analysis", project_id)
                return

            brand_name: str = brand_row["name"]
            brand_aliases: list[str] = json.loads(brand_row["aliases_json"])

            # Load competitors
            cursor = await db.execute(
                "SELECT name FROM competitors WHERE project_id = ? AND is_active = 1",
                (project_id,),
            )
            competitor_rows = await cursor.fetchall()
            competitors: list[str] = [row["name"] for row in competitor_rows]

            # 2. Load non-error responses for this run
            cursor = await db.execute(
                "SELECT id, response_text FROM responses WHERE run_id = ? AND error_message IS NULL",
                (run_id,),
            )
            responses = list(await cursor.fetchall())

        # 3. Detect mentions for each response
        with logfire.span('mention detection', response_count=len(responses)):
            for response in responses:
                try:
                    await detect_and_store_mentions_for_response(
                        response_id=response["id"],
                        response_text=response["response_text"],
                        brand_name=brand_name,
                        brand_aliases=brand_aliases,
                        competitors=competitors,
                    )
                except Exception:
                    logger.exception("Mention detection failed for response %s", response["id"])

        # 4. Calculate and store scores
        with logfire.span('score calculation'):
            try:
                await calculate_and_store_scores(run_id, project_id)
            except Exception:
                logger.exception("Score calculation failed for run %s", run_id)

        # 5. Detect changes and store alerts
        with logfire.span('change detection'):
            try:
                alert_ids = await detect_and_store_alerts(project_id, run_id)
            except Exception:
                logger.exception("Change detection failed for run %s", run_id)
                alert_ids = []

        # 6. Dispatch notifications for new alerts
        if alert_ids:
            with logfire.span('alert dispatch', alert_count=len(alert_ids)):
                try:
                    await dispatch_alerts(project_id, alert_ids)
                except Exception:
                    logger.exception("Alert dispatch failed for run %s", run_id)

        logger.info("Analysis pipeline completed for run %s", run_id)
