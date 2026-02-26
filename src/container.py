"""Dependency injection container — single wiring point for repos and services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src import database

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    import aiosqlite

from src.repos.alert_repo import AlertRepo
from src.repos.change_detection_repo import ChangeDetectionRepo
from src.repos.project_repo import ProjectRepo
from src.repos.provider_repo import ProviderRepo
from src.repos.response_repo import ResponseRepo
from src.repos.run_repo import RunRepo
from src.repos.schedule_repo import ScheduleRepo
from src.repos.score_repo import ScoreRepo
from src.repos.settings_repo import SettingsRepo
from src.repos.term_repo import TermRepo
from src.services.alert_service import AlertService
from src.services.analysis import AnalysisService
from src.services.change_detection import ChangeDetectionService
from src.services.mention_service import MentionService
from src.services.project_service import ProjectService
from src.services.provider_service import ProviderService
from src.services.run_service import RunService
from src.services.schedule_service import ScheduleService
from src.services.scoring_service import ScoringService
from src.services.settings_service import SettingsService
from src.services.term_service import TermService


def _get_connection() -> AbstractAsyncContextManager[aiosqlite.Connection]:
    """Wrap database.get_db_connection with a deferred attribute lookup.

    Tests patch ``src.database.get_db_connection`` and the change flows
    through because this function performs the lookup at call time.
    """
    return database.get_db_connection()


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

alert_repo = AlertRepo(_get_connection)
change_detection_repo = ChangeDetectionRepo(_get_connection)
project_repo = ProjectRepo(_get_connection)
provider_repo = ProviderRepo(_get_connection)
response_repo = ResponseRepo(_get_connection)
run_repo = RunRepo(_get_connection)
schedule_repo = ScheduleRepo(_get_connection)
score_repo = ScoreRepo(_get_connection)
settings_repo = SettingsRepo(_get_connection)
term_repo = TermRepo(_get_connection)

# ---------------------------------------------------------------------------
# Services — tier 1 (repo-only dependencies)
# ---------------------------------------------------------------------------

alert_service = AlertService(alert_repo)
mention_service = MentionService(response_repo)
scoring_service = ScoringService(score_repo)
term_service = TermService(term_repo)
schedule_service = ScheduleService(schedule_repo)
provider_service = ProviderService(provider_repo)
settings_service = SettingsService(settings_repo, project_repo)
run_service = RunService(run_repo, response_repo, score_repo, term_repo)

# ---------------------------------------------------------------------------
# Services — tier 2 (cross-service dependencies)
# ---------------------------------------------------------------------------

change_detection_service = ChangeDetectionService(change_detection_repo, alert_repo)
project_service = ProjectService(project_repo, provider_repo, run_repo, schedule_repo, term_repo)

# ---------------------------------------------------------------------------
# Services — tier 3 (orchestrator)
# ---------------------------------------------------------------------------

async def _dispatch_alerts(project_id: str, alert_ids: list[str]) -> None:
    """Lazy wrapper to avoid circular import with notifications.dispatcher."""
    from src.notifications.dispatcher import dispatch_alerts  # noqa: PLC0415

    await dispatch_alerts(project_id, alert_ids)


analysis_service = AnalysisService(
    project_repo, response_repo, mention_service,
    scoring_service, change_detection_service, _dispatch_alerts,
)
