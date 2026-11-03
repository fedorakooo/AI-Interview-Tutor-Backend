from enum import StrEnum


class CompletionReason(StrEnum):
    ALL_COVERED = "all_covered"
    QUESTION_BUDGET = "question_budget"
    TIME_BUDGET = "time_budget"
    CANDIDATE_ENDED = "candidate_ended"
