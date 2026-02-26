"""Analysis pipeline orchestrator for GeoStorm monitoring runs."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import logfire

if TYPE_CHECKING:
    from src.repos.project_repo import ProjectRepo
    from src.repos.response_repo import ResponseRepo
    from src.services.change_detection import ChangeDetectionService
    from src.services.mention_service import MentionService
    from src.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)

DispatchAlerts = Callable[[str, list[str]], Coroutine[Any, Any, None]]


class AnalysisService:
    def __init__(  # noqa: PLR0913
        self,
        project_repo: ProjectRepo,
        response_repo: ResponseRepo,
        mention_service: MentionService,
        scoring_service: ScoringService,
        change_detection_service: ChangeDetectionService,
        dispatch_alerts: DispatchAlerts,
    ) -> None:
        self._project_repo = project_repo
        self._response_repo = response_repo
        self._mention_service = mention_service
        self._scoring_service = scoring_service
        self._change_detection_service = change_detection_service
        self._dispatch_alerts = dispatch_alerts

    async def analyze_run(self, run_id: str, project_id: str) -> None:
        """Run the full analysis pipeline for a completed monitoring run.

        Steps:
        1. Load brand name, aliases, competitors from repos
        2. Load all non-error responses for this run
        3. For each response: detect and store mentions
        4. Calculate and store perception scores
        5. Detect changes and store alerts

        Errors are logged but do NOT fail the run.
        """
        with logfire.span("analysis pipeline", run_id=run_id, project_id=project_id):
            # 1. Load brand info
            brand_info = await self._project_repo.get_brand_with_aliases(project_id)
            if not brand_info:
                logger.warning("No brand configured for project %s, skipping analysis", project_id)
                return

            brand_name, brand_aliases = brand_info
            competitors = await self._project_repo.list_active_competitor_names(project_id)

            # 2. Load non-error responses for this run
            responses = await self._response_repo.get_non_error_responses(run_id)

            # 3. Detect mentions for each response
            with logfire.span("mention detection", response_count=len(responses)):
                for response in responses:
                    try:
                        await self._mention_service.detect_and_store_mentions_for_response(
                            response_id=response["id"],
                            response_text=response["response_text"],
                            brand_name=brand_name,
                            brand_aliases=brand_aliases,
                            competitors=competitors,
                        )
                    except Exception:
                        logger.exception("Mention detection failed for response %s", response["id"])

            # 4. Calculate and store scores
            with logfire.span("score calculation"):
                try:
                    await self._scoring_service.calculate_and_store_scores(run_id, project_id)
                except Exception:
                    logger.exception("Score calculation failed for run %s", run_id)

            # 5. Detect changes and store alerts
            with logfire.span("change detection"):
                try:
                    alert_ids = await self._change_detection_service.detect_and_store_alerts(project_id, run_id)
                except Exception:
                    logger.exception("Change detection failed for run %s", run_id)
                    alert_ids = []

            # 6. Dispatch notifications for new alerts
            if alert_ids:
                with logfire.span("alert dispatch", alert_count=len(alert_ids)):
                    try:
                        await self._dispatch_alerts(project_id, alert_ids)
                    except Exception:
                        logger.exception("Alert dispatch failed for run %s", run_id)

            logger.info("Analysis pipeline completed for run %s", run_id)
