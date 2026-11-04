from shared_models.assessment import mocks
from src.domain.entities.assessment import Assessment
from src.domain.enums.cv_policy import CvPolicy
from src.domain.events.session_event import SessionEvent
from src.domain.value_objects.assessment_context import AssessmentContext
from src.domain.value_objects.assessment_texts import AssessmentTexts
from src.domain.value_objects.focus_text import FocusText
from src.domain.value_objects.interview_template import InterviewTemplate
from src.domain.value_objects.red_flag_draft import RedFlagDraft
from src.infrastructure.mappers.assessment_context_mapper import AssessmentContextMapper
from src.infrastructure.mappers.assessment_mapper import AssessmentMapper
from src.infrastructure.mappers.session_event_mapper import SessionEventMapper

from tests.fakes import journal_mocks


def _contract_policy(cv_policy: CvPolicy):
    return mocks.CvPolicy(cv_policy.value)


def build_context(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> AssessmentContext:
    return AssessmentContextMapper.to_domain(mocks.mock_assessment_context(_contract_policy(cv_policy)))


def build_template(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> InterviewTemplate:
    return AssessmentContextMapper.template_to_domain(mocks.mock_template(_contract_policy(cv_policy)))


def build_events(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> list[SessionEvent]:
    return [
        SessionEventMapper.to_domain(event) for event in journal_mocks.mock_session_events(_contract_policy(cv_policy))
    ]


def build_assessment(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> Assessment:
    return AssessmentMapper.to_domain(journal_mocks.mock_assessment(_contract_policy(cv_policy)))


def build_texts(template: InterviewTemplate, **overrides) -> AssessmentTexts:
    flag = template.red_flags[1]
    values = {
        "overall_summary": "A solid backend candidate with gaps in async.",
        "focus": tuple(
            FocusText(
                focus_id=focus.id,
                summary_short=f"Summary of {focus.id}",
                rationale=f"Rationale of {focus.id}",
                reference_comparison="Matches the reference." if focus.id in {"databases", "async_io"} else "Ignored.",
            )
            for focus in template.criteria
        ),
        "red_flags": (
            RedFlagDraft(flag=flag, quotes=("QA handles most of that on our team",), reasoning="Delegates testing."),
        ),
    }
    return AssessmentTexts(**(values | overrides))
