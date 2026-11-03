from shared_models.assessment import AssessmentTemplateSnapshot

from src.application.dtos.template_draft import TemplateDraft


class TemplateDraftMapper:
    @staticmethod
    def to_snapshot(draft: TemplateDraft) -> AssessmentTemplateSnapshot:
        return AssessmentTemplateSnapshot.model_validate(
            {
                "mode": draft.mode,
                "question_count": draft.question_count,
                "duration_minutes": draft.duration_minutes,
                "attempt_limit": draft.attempt_limit,
                "criteria": [
                    {
                        "id": focus.id,
                        "skill": focus.skill,
                        "required": focus.required,
                        "weight": focus.weight,
                        "expected_level": focus.expected_level,
                        "guidance": focus.guidance,
                        "what_to_learn": focus.what_to_learn,
                        "method": focus.method,
                        "strong_signals": list(focus.strong_signals),
                        "weak_signals": list(focus.weak_signals),
                        "must_cover": list(focus.must_cover),
                        "min_evidence": focus.min_evidence,
                        "max_questions": focus.max_questions,
                    }
                    for focus in draft.criteria
                ],
                "brief": draft.brief,
                "skip": list(draft.skip),
                "red_flags": list(draft.red_flags),
                "custom_questions": [
                    {
                        "focus_id": question.focus_id,
                        "text": question.text,
                        "reference_answer": question.reference_answer,
                        "required": question.required,
                    }
                    for question in draft.custom_questions
                ],
                "language": draft.language,
                "candidate_feedback": draft.candidate_feedback,
                "cv_policy": draft.cv_policy,
            }
        )
