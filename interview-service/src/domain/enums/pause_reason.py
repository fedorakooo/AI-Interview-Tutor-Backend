from enum import StrEnum


class PauseReason(StrEnum):
    DISCONNECT = "disconnect"
    INACTIVITY = "inactivity"
    CANDIDATE_REQUEST = "candidate_request"
