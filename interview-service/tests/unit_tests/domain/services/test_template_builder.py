import pytest
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.spec_errors import EmptySpecDraftError
from src.domain.services.template_builder import TemplateBuilder
from src.domain.value_objects.draft_brief import DraftBrief
from src.domain.value_objects.draft_custom_question import DraftCustomQuestion
from src.domain.value_objects.draft_focus import DraftFocus
from src.domain.value_objects.interview_template import InterviewTemplate
from src.domain.value_objects.spec_draft import SpecDraft

REQUEST = DraftBrief(
    brief="I want to know how they debug production problems and whether they write tests.",
    job_description="Python backend developer",
    title="Backend developer",
    seniority="middle",
    language="en",
    cv_policy=CvPolicy.OPTIONAL,
    candidate_feedback=True,
)


def focus(skill: str, weight: int = 10, **overrides) -> DraftFocus:
    return DraftFocus(skill=skill, weight=weight, **overrides)


def test_draft_is_normalized_into_a_valid_template() -> None:
    draft = SpecDraft(
        question_count=500,
        duration_minutes=1,
        focus_areas=(
            focus(
                "Debugging production issues", 7, strong_signals=("Reads logs first",), min_evidence=9, max_questions=2
            ),
            focus("debugging production issues", 3),
            focus("Testing", 3, required=False),
            focus("  ", 5),
            focus("Python", 0),
        ),
        skip=("Frontend", "Frontend"),
    )

    template = TemplateBuilder.build(draft, REQUEST)

    assert isinstance(template, InterviewTemplate)
    assert [f.id for f in template.criteria] == ["debugging_production_issues", "testing", "python"]
    assert sum(f.weight for f in template.criteria) == 100 and min(f.weight for f in template.criteria) >= 1
    assert sum(1 for f in template.criteria if f.required) == 1 and template.criteria[0].required
    assert template.question_count == 30 and template.duration_minutes == 5
    assert template.criteria[0].min_evidence == 2 == template.criteria[0].max_questions
    assert template.skip == ("Frontend",)


def test_recruiter_text_and_request_options_are_kept_verbatim() -> None:
    template = TemplateBuilder.build(SpecDraft(focus_areas=(focus("Python"),)), REQUEST)

    assert template.brief == REQUEST.brief
    assert (template.cv_policy, template.language, template.candidate_feedback) == (CvPolicy.OPTIONAL, "en", True)
    assert template.attempt_limit == 1


def test_custom_questions_are_linked_by_skill_and_unknown_skills_are_dropped() -> None:
    draft = SpecDraft(
        focus_areas=(focus("SQL tuning"), focus("Python")),
        custom_questions=(
            DraftCustomQuestion(focus_skill="sql TUNING", text="Why is this query slow?", reference_answer="EXPLAIN"),
            DraftCustomQuestion(focus_skill="Rust", text="Unknown focus"),
            DraftCustomQuestion(focus_skill="Python", text="  "),
        ),
    )

    template = TemplateBuilder.build(draft, REQUEST)

    assert [(q.focus_id, q.text, q.reference_answer) for q in template.custom_questions] == [
        ("sql_tuning", "Why is this query slow?", "EXPLAIN")
    ]


def test_weights_always_total_one_hundred() -> None:
    for weights in ([1], [1, 1, 1], [5, 0, 0, 9, 2, 7, 1], [100] * 10, [3, 3, 3]):
        draft = SpecDraft(focus_areas=tuple(focus(f"Skill {i}", weight) for i, weight in enumerate(weights)))

        assert sum(f.weight for f in TemplateBuilder.build(draft, REQUEST).criteria) == 100


def test_a_draft_without_usable_focus_areas_is_rejected() -> None:
    with pytest.raises(EmptySpecDraftError):
        TemplateBuilder.build(SpecDraft(focus_areas=(focus(" "),)), REQUEST)
