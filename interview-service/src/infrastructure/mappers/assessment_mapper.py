from src.domain.entities.assessment import Assessment
from src.domain.entities.focus_assessment import FocusAssessment
from src.domain.enums.verdict import Verdict
from src.domain.value_objects.assessment_coverage import AssessmentCoverage
from src.domain.value_objects.red_flag_finding import RedFlagFinding
from src.infrastructure.mappers.evidence_mapper import EvidenceMapper
from src.infrastructure.mappers.review_entry_mapper import ReviewEntryMapper
from src.infrastructure.mongo.documents.assessment_document import (
    AssessmentCoverageDocument,
    AssessmentDocument,
    FocusAssessmentDocument,
    RedFlagFindingDocument,
)


class AssessmentMapper:
    @staticmethod
    def to_model(assessment: Assessment) -> AssessmentDocument:
        return AssessmentDocument(
            assessment_id=assessment.assessment_id,
            attempt_id=assessment.attempt_id,
            session_id=assessment.session_id,
            template_version=assessment.template_version,
            report_version=assessment.report_version,
            generator_version=assessment.generator_version,
            generated_at=assessment.generated_at,
            coverage=AssessmentCoverageDocument(
                focus_total=assessment.coverage.focus_total,
                focus_assessed=assessment.coverage.focus_assessed,
                required_total=assessment.coverage.required_total,
                required_assessed=assessment.coverage.required_assessed,
                questions_asked=assessment.coverage.questions_asked,
            ),
            overall_summary=assessment.overall_summary,
            focus=[
                FocusAssessmentDocument(
                    focus_id=item.focus_id,
                    verdict=item.verdict.value,
                    confidence=item.confidence,
                    summary_short=item.summary_short,
                    rationale=item.rationale,
                    evidence=[EvidenceMapper.to_model(evidence) for evidence in item.evidence],
                    covered_must_cover=list(item.covered_must_cover),
                    missed_must_cover=list(item.missed_must_cover),
                    reference_comparison=item.reference_comparison,
                    review=[ReviewEntryMapper.to_model(entry) for entry in item.review],
                )
                for item in assessment.focus
            ],
            red_flags=[
                RedFlagFindingDocument(
                    flag=finding.flag,
                    quotes=[EvidenceMapper.quote_to_model(quote) for quote in finding.quotes],
                    reasoning=finding.reasoning,
                )
                for finding in assessment.red_flags
            ],
        )

    @staticmethod
    def to_domain(assessment: AssessmentDocument) -> Assessment:
        return Assessment(
            assessment_id=assessment.assessment_id,
            attempt_id=assessment.attempt_id,
            session_id=assessment.session_id,
            template_version=assessment.template_version,
            report_version=assessment.report_version,
            generator_version=assessment.generator_version,
            generated_at=assessment.generated_at,
            coverage=AssessmentCoverage(
                focus_total=assessment.coverage.focus_total,
                focus_assessed=assessment.coverage.focus_assessed,
                required_total=assessment.coverage.required_total,
                required_assessed=assessment.coverage.required_assessed,
                questions_asked=assessment.coverage.questions_asked,
            ),
            overall_summary=assessment.overall_summary,
            focus=tuple(
                FocusAssessment(
                    focus_id=item.focus_id,
                    verdict=Verdict(item.verdict.value),
                    confidence=item.confidence,
                    summary_short=item.summary_short,
                    rationale=item.rationale,
                    evidence=tuple(EvidenceMapper.to_domain(evidence) for evidence in item.evidence),
                    covered_must_cover=tuple(item.covered_must_cover),
                    missed_must_cover=tuple(item.missed_must_cover),
                    reference_comparison=item.reference_comparison,
                    review=tuple(ReviewEntryMapper.to_domain(entry) for entry in item.review),
                )
                for item in assessment.focus
            ),
            red_flags=tuple(
                RedFlagFinding(
                    flag=finding.flag,
                    quotes=tuple(EvidenceMapper.quote_to_domain(quote) for quote in finding.quotes),
                    reasoning=finding.reasoning,
                )
                for finding in assessment.red_flags
            ),
        )
