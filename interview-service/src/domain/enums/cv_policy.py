from enum import StrEnum


class CvPolicy(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    NONE = "none"
