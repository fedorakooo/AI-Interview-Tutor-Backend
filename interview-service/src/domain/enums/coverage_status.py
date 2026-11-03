from enum import StrEnum


class CoverageStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COVERED = "covered"
    EXHAUSTED = "exhausted"
