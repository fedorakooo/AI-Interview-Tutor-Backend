from collections.abc import AsyncIterator

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from src.agents.answer_evaluator.agent import AnswerEvaluator
from src.agents.answer_evaluator.prompts import render_evaluator_context
from src.agents.interviewer.agent import InterviewerAgent
from src.agents.interviewer.prompts import render_cv_summary, render_interviewer_context
from src.agents.models import parse_model_specs, resolve_model
from src.domain.enums.completion_reason import CompletionReason
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.message_kind import MessageKind
from src.domain.value_objects.ask_focus import AskFocus
from src.domain.value_objects.ask_intro import AskIntro
from src.domain.value_objects.candidate_cv import CandidateCv
from src.domain.value_objects.complete import Complete
from src.domain.value_objects.cv_experience import CvExperience
from src.domain.value_objects.evaluation_request import EvaluationRequest
from src.domain.value_objects.focus_coverage import FocusCoverage
from src.domain.value_objects.interviewer_request import InterviewerRequest
from src.domain.value_objects.message_record import MessageRecord

from tests.fakes.builders import build_template

TEMPLATE = build_template(CvPolicy.REQUIRED)
DATABASES = TEMPLATE.focus_by_id("databases")


def interviewer_request(action, **overrides) -> InterviewerRequest:
    values = {
        "template": TEMPLATE,
        "action": action,
        "focus": DATABASES if isinstance(action, AskFocus) else None,
        "transcript": (MessageRecord(seq=2, role="candidate", text="I use Postgres daily"),),
    }
    return InterviewerRequest(**(values | overrides))


def test_model_specs_are_parsed_and_resolved_lazily() -> None:
    assert parse_model_specs(" openai:gpt-4o-mini , anthropic:claude-haiku-5-5 ,") == [
        "openai:gpt-4o-mini",
        "anthropic:claude-haiku-5-5",
    ]
    assert resolve_model(["openai:gpt-4o-mini"]) == "openai:gpt-4o-mini"
    assert isinstance(resolve_model(["test", "test"]), FallbackModel)
    with pytest.raises(ValueError):
        resolve_model([])


async def test_evaluator_returns_structured_output_without_a_network() -> None:
    output = {
        "answer_was_complete": True,
        "evidence": [
            {
                "focus_id": "databases",
                "level": "strong",
                "matched_signals": [DATABASES.strong_signals[0]],
                "quotes": ["EXPLAIN ANALYZE"],
                "reasoning": "Plan-first investigation.",
            }
        ],
        "covered_must_cover": ["indexes"],
    }
    evaluator = AnswerEvaluator([], model=TestModel(custom_output_args=output))

    result = await evaluator.evaluate(
        EvaluationRequest(
            template=TEMPLATE,
            target_focus=DATABASES,
            question_text="How do you investigate a slow query?",
            answer_text="I run EXPLAIN ANALYZE first.",
        )
    )

    assert result.answer_was_complete is True
    assert result.evidence[0].focus_id == "databases"
    assert result.covered_must_cover == ("indexes",)


async def test_interviewer_streams_text_deltas_with_the_rendered_context() -> None:
    seen: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        seen.append(str(messages))
        yield "How would you "
        yield "investigate that?"

    agent = InterviewerAgent([], model=FunctionModel(stream_function=stream))

    deltas = [d async for d in agent.stream_message(interviewer_request(AskFocus("databases", MessageKind.QUESTION)))]

    assert "".join(deltas) == "How would you investigate that?"
    assert "SQL and PostgreSQL" in seen[0]
    assert "I use Postgres daily" in seen[0]


def test_evaluator_context_lists_the_rubric_signals() -> None:
    context = render_evaluator_context(TEMPLATE, DATABASES)

    assert DATABASES.strong_signals[0] in context
    assert DATABASES.weak_signals[0] in context
    assert "api_design" in context


@pytest.mark.parametrize(
    "action",
    [
        AskIntro(),
        AskFocus("databases", MessageKind.QUESTION, custom_question_index=0),
        Complete(CompletionReason.QUESTION_BUDGET),
    ],
)
def test_interviewer_context_never_leaks_the_rubric(action) -> None:
    custom = TEMPLATE.custom_questions[0] if isinstance(action, AskFocus) else None
    request = interviewer_request(
        action,
        custom_question=custom,
        coverage=FocusCoverage(focus_id="databases"),
        cv=CandidateCv(specialization="Backend", skills=("Python",)),
    )

    context = render_interviewer_context(request)

    secrets = {
        custom_question.reference_answer
        for custom_question in TEMPLATE.custom_questions
        if custom_question.reference_answer
    }
    secrets |= set(TEMPLATE.red_flags) | {TEMPLATE.brief}
    for focus in TEMPLATE.criteria:
        secrets |= set(focus.strong_signals) | set(focus.weak_signals)
    assert not any(secret in context for secret in secrets)
    assert "Backend" in context


def test_interviewer_context_uses_the_custom_question_text_and_remaining_topics() -> None:
    custom = render_interviewer_context(
        interviewer_request(
            AskFocus("databases", MessageKind.QUESTION, custom_question_index=0),
            custom_question=TEMPLATE.custom_questions[0],
        )
    )
    follow_up = render_interviewer_context(
        interviewer_request(
            AskFocus("databases", MessageKind.FOLLOW_UP),
            coverage=FocusCoverage(focus_id="databases", covered_must_cover=("indexes",)),
        )
    )

    assert TEMPLATE.custom_questions[0].text in custom
    assert "follow-up" in follow_up
    assert "transactions" in follow_up and "indexes" not in follow_up.split("subtopics:")[1]


def test_cv_summary_is_compact() -> None:
    cv = CandidateCv(
        specialization="Backend",
        skills=tuple(f"skill{i}" for i in range(30)),
        experience=(CvExperience(company="Acme", role="Developer", technologies=("Python", "Postgres")),),
    )

    summary = render_cv_summary(cv)

    assert "skill14" in summary and "skill15" not in summary
    assert "Developer at Acme; Python, Postgres" in summary
    assert render_cv_summary(CandidateCv()) == "No details available."
