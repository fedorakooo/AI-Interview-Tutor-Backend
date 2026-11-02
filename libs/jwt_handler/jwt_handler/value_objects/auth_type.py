from enum import StrEnum


class AuthType(StrEnum):
    BEARER = "BEARER"


class TokenType(StrEnum):
    ACCESS = "ACCESS"
    REFRESH = "REFRESH"
    CANDIDATE_INTERVIEW = "CANDIDATE_INTERVIEW"
