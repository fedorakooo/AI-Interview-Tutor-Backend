import random

from src.domain.models.interview_state import InterviewState
from src.domain.value_objects.conversation_role import ConversationRole
from src.domain.value_objects.interview_stage import OverallInterviewStage


def greeting_node(state: InterviewState) -> InterviewState:
    greetings = [
        "Hi! I’m your AI interviewer. Let’s start with some easy questions.",
        "Hello! Ready to begin? We'll start with a few soft questions.",
        "Hey! I’ll guide you through this interview. Let’s kick off.",
        "Hi! Thanks for joining. Let’s start with some intro questions.",
        "Hello! I’m here for a quick technical interview. Ready?",
        "Hey! Let’s start light and move to harder stuff soon.",
        "Hi there! I’ll be asking questions today. Let’s begin.",
        "Hello! Ready to dive in? We’ll start simple.",
        "Hey! Great to see you. Let’s start with some easy questions.",
        "Hi! Let’s begin with a few soft questions.",
    ]

    greeting = random.choice(greetings)

    state["messages"].append((ConversationRole.AGENT, greeting))
    state["overall_stage"] = OverallInterviewStage.SOFT_QUESTIONS

    return state
