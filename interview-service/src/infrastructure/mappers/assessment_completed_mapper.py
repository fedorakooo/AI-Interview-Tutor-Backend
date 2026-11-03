from shared_models.assessment import AssessmentCompleted as ContractAssessmentCompleted

from src.domain.events.assessment_completed import AssessmentCompleted


class AssessmentCompletedMapper:
    @staticmethod
    def to_contract(event: AssessmentCompleted) -> ContractAssessmentCompleted:
        return ContractAssessmentCompleted(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            organization_id=event.organization_id,
            vacancy_id=event.vacancy_id,
            invitation_id=event.invitation_id,
            attempt_id=event.attempt_id,
            session_id=event.session_id,
            report_reference=event.report_reference,
            report_version=event.report_version,
        )

    @staticmethod
    def to_domain(event: ContractAssessmentCompleted) -> AssessmentCompleted:
        return AssessmentCompleted(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            organization_id=event.organization_id,
            vacancy_id=event.vacancy_id,
            invitation_id=event.invitation_id,
            attempt_id=event.attempt_id,
            session_id=event.session_id,
            report_reference=event.report_reference,
            report_version=event.report_version,
        )
