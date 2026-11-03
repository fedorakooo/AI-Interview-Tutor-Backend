from shared_models.assessment import TemplateDraftRequest

from src.application.dtos.custom_question_draft import CustomQuestionDraft
from src.application.dtos.focus_area_draft import FocusAreaDraft
from src.application.dtos.template_draft import TemplateDraft
from src.domain.enums.cv_policy import CvPolicy
from src.domain.value_objects.draft_brief import DraftBrief
from src.domain.value_objects.interview_template import InterviewTemplate


class TemplateDraftMapper:
    @staticmethod
    def to_brief(request: TemplateDraftRequest) -> DraftBrief:
        return DraftBrief(
            brief=request.brief,
            job_description=request.job_description,
            title=request.title,
            seniority=request.seniority,
            language=request.language,
            cv_policy=CvPolicy(request.cv_policy.value),
            candidate_feedback=request.candidate_feedback,
        )

    @staticmethod
    def to_dto(template: InterviewTemplate) -> TemplateDraft:
        return TemplateDraft(
            mode=template.mode.value,
            question_count=template.question_count,
            duration_minutes=template.duration_minutes,
            attempt_limit=template.attempt_limit,
            criteria=tuple(
                FocusAreaDraft(
                    id=focus.id,
                    skill=focus.skill,
                    required=focus.required,
                    weight=focus.weight,
                    expected_level=focus.expected_level,
                    guidance=focus.guidance,
                    what_to_learn=focus.what_to_learn,
                    method=focus.method.value,
                    strong_signals=focus.strong_signals,
                    weak_signals=focus.weak_signals,
                    must_cover=focus.must_cover,
                    min_evidence=focus.min_evidence,
                    max_questions=focus.max_questions,
                )
                for focus in template.criteria
            ),
            brief=template.brief,
            skip=template.skip,
            red_flags=template.red_flags,
            custom_questions=tuple(
                CustomQuestionDraft(
                    focus_id=question.focus_id,
                    text=question.text,
                    reference_answer=question.reference_answer,
                    required=question.required,
                )
                for question in template.custom_questions
            ),
            language=template.language,
            candidate_feedback=template.candidate_feedback,
            cv_policy=template.cv_policy.value,
        )
