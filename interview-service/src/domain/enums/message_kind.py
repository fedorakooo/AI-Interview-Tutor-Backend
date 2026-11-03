from enum import StrEnum


class MessageKind(StrEnum):
    INTRO = "intro"
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    CLOSING = "closing"
