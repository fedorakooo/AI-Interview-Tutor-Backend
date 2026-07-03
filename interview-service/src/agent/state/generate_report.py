from shared_models.interview.report import InterviewReport

from src.agent.prompts.generate_report import GENERATE_REPORT_PROMPT
from src.agent.utils.format_messages import format_messages
from src.domain.models.interview_state import InterviewState
from src.domain.value_objects.interview_stage import OverallInterviewStage


async def generate_report_node(state: InterviewState) -> InterviewState:
    from langchain_core.prompts import ChatPromptTemplate

    from src.agent.llm import llm

    prompt = ChatPromptTemplate.from_template(GENERATE_REPORT_PROMPT)
    chain = prompt | llm
    response = await chain.ainvoke(
        {
            "conversation_context": format_messages(state.get("messages", [])),
            "cv_summary": str(state.get("cv_data", {})),
        }
    )
    content = response.content.strip()
    if content.startswith("```"):
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    report = InterviewReport.model_validate_json(content)
    state["interview_report"] = report.model_dump(mode="json")
    state["overall_stage"] = OverallInterviewStage.COMPLETED
    return state
