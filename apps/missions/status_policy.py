"""Politique centralisée du cycle de vie des missions (miroir Flutter MissionStatusPolicy)."""

from apps.core.choices import MissionStatus

AGENT_ACTIVE_MISSION_STATUSES = (
    MissionStatus.ACCEPTED,
    MissionStatus.ON_THE_WAY,
    MissionStatus.ARRIVED,
    MissionStatus.IN_PROGRESS,
    MissionStatus.IN_PROGRESS_REVIEW,
)

CLIENT_ONGOING_MISSION_STATUSES = (
    MissionStatus.PENDING,
    *AGENT_ACTIVE_MISSION_STATUSES,
)

TERMINAL_MISSION_STATUSES = (
    MissionStatus.COMPLETED,
    MissionStatus.CANCELLED,
)


def is_agent_active(status: str) -> bool:
    return status in AGENT_ACTIVE_MISSION_STATUSES


def is_client_ongoing(status: str) -> bool:
    return status in CLIENT_ONGOING_MISSION_STATUSES


def is_terminal(status: str) -> bool:
    return status in TERMINAL_MISSION_STATUSES
