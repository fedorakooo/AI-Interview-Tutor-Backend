from src.agents.spec_drafter.schemas import SpecDraftSchema
from src.domain.value_objects.draft_custom_question import DraftCustomQuestion
from src.domain.value_objects.draft_focus import DraftFocus
from src.domain.value_objects.spec_draft import SpecDraft


class SpecDraftMapper:
    @staticmethod
    def to_domain(draft: SpecDraftSchema) -> SpecDraft:
        return SpecDraft(
            mode=draft.mode,
            question_count=draft.question_count,
            duration_minutes=draft.duration_minutes,
            focus_areas=tuple(
                DraftFocus(
                    skill=focus.skill,
                    what_to_learn=focus.what_to_learn,
                    required=focus.required,
                    weight=focus.weight,
                    expected_level=focus.expected_level,
                    guidance=focus.guidance,
                    method=focus.method,
                    strong_signals=tuple(focus.strong_signals),
                    weak_signals=tuple(focus.weak_signals),
                    must_cover=tuple(focus.must_cover),
                    min_evidence=focus.min_evidence,
                    max_questions=focus.max_questions,
                )
                for focus in draft.focus_areas
            ),
            skip=tuple(draft.skip),
            red_flags=tuple(draft.red_flags),
            custom_questions=tuple(
                DraftCustomQuestion(
                    focus_skill=question.focus_skill,
                    text=question.text,
                    reference_answer=question.reference_answer,
                    required=question.required,
                )
                for question in draft.custom_questions
            ),
        )
