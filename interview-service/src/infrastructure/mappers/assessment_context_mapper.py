from shared_models.assessment import AssessmentContext as ContractContext
from shared_models.assessment import AssessmentTemplateSnapshot

from src.domain.enums.assessment_mode import AssessmentMode
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.focus_method import FocusMethod
from src.domain.value_objects.assessment_context import AssessmentContext
from src.domain.value_objects.custom_question import CustomQuestion
from src.domain.value_objects.focus_area import FocusArea
from src.domain.value_objects.interview_template import InterviewTemplate


class AssessmentContextMapper:
    @staticmethod
    def to_domain(context: ContractContext) -> AssessmentContext:
        return AssessmentContext(
            attempt_id=context.attempt_id,
            organization_id=context.organization_id,
            vacancy_id=context.vacancy_id,
            invitation_id=context.invitation_id,
            template_version=context.template_version,
            template=AssessmentContextMapper.template_to_domain(context.template),
            cv_policy=CvPolicy(context.cv_policy.value),
            cv_correlation_id=context.cv_correlation_id,
        )

    @staticmethod
    def template_to_domain(template: AssessmentTemplateSnapshot) -> InterviewTemplate:
        return InterviewTemplate(
            mode=AssessmentMode(template.mode.value),
            question_count=template.question_count,
            duration_minutes=template.duration_minutes,
            attempt_limit=template.attempt_limit,
            criteria=tuple(
                FocusArea(
                    id=focus.id,
                    skill=focus.skill,
                    required=focus.required,
                    weight=focus.weight,
                    expected_level=focus.expected_level,
                    guidance=focus.guidance,
                    what_to_learn=focus.what_to_learn,
                    method=FocusMethod(focus.method.value),
                    strong_signals=tuple(focus.strong_signals),
                    weak_signals=tuple(focus.weak_signals),
                    must_cover=tuple(focus.must_cover),
                    min_evidence=focus.min_evidence,
                    max_questions=focus.max_questions,
                )
                for focus in template.criteria
            ),
            brief=template.brief,
            skip=tuple(template.skip),
            red_flags=tuple(template.red_flags),
            custom_questions=tuple(
                CustomQuestion(
                    focus_id=question.focus_id,
                    text=question.text,
                    reference_answer=question.reference_answer,
                    required=question.required,
                )
                for question in template.custom_questions
            ),
            language=template.language,
            candidate_feedback=template.candidate_feedback,
            cv_policy=CvPolicy(template.cv_policy.value),
        )
