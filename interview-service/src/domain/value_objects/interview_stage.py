from enum import StrEnum


class OverallInterviewStage(StrEnum):
    GREETING = "Greeting"
    SOFT_QUESTIONS = "Soft Questions"
    HARD_QUESTIONS = "Hard Questions"
    WRAP_UP = "Wrap Up"


class IntermediateInterviewStage(StrEnum):
    SMALL_TALK = "Small Talk"
    QUESTION = "Question"
