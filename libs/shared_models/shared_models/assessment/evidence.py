from enum import StrEnum


class Verdict(StrEnum):
    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
    NOT_ASSESSED = "not_assessed"


class EvidenceLevel(StrEnum):
    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
