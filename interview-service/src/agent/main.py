import asyncio
import uuid

from langgraph.constants import END

from src.agent.data.sample_data import SAMPLE_CV
from src.agent.workflow import create_interview_workflow
from src.domain.models.user_profile import UserProfile
from src.domain.value_objects.conversation_role import ConversationRole
from src.domain.value_objects.interview_stage import IntermediateInterviewStage, OverallInterviewStage


async def run_interview(profile: UserProfile):
    interviewer = create_interview_workflow()
    interview_id = str(uuid.uuid4())

    state = {
        "user_profile": profile,
        "messages": [],
        "is_answer_complete": False,
        "overall_stage": OverallInterviewStage.GREETING,
        "cv_data": SAMPLE_CV.model_dump(),
        "intermediate_stage": IntermediateInterviewStage.SMALL_TALK,
        "soft_questions_turns": 0,
        "soft_question_completed": 0,
        "hard_questions_turns": 0,
        "hard_question_completed": 0,
    }

    config = {"configurable": {"thread_id": interview_id}}

    state = await interviewer.ainvoke(state, config)

    while True:
        last_message = state["messages"][-1]
        if last_message[0] == ConversationRole.AGENT:
            print(f"Interviewer: {last_message[1]}\n")

        user_input = input("You: ").strip()

        if not user_input:
            continue

        state["messages"].append((ConversationRole.USER, user_input))

        if state["overall_stage"] == END:
            break

        state = await interviewer.ainvoke(state, config)


if __name__ == "__main__":
    candidate_profile = UserProfile(id=uuid.uuid4())
    asyncio.run(run_interview(candidate_profile))
