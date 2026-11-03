from src.agents.answer_evaluator.schemas import EvaluationResultSchema
from src.domain.value_objects.evaluation_result import EvaluationResult
from src.domain.value_objects.evidence_draft import EvidenceDraft


class EvaluationMapper:
    @staticmethod
    def to_domain(result: EvaluationResultSchema) -> EvaluationResult:
        return EvaluationResult(
            answer_was_complete=result.answer_was_complete,
            evidence=tuple(
                EvidenceDraft(
                    focus_id=item.focus_id,
                    level=item.level,
                    quotes=tuple(item.quotes),
                    reasoning=item.reasoning,
                    matched_signals=tuple(item.matched_signals),
                )
                for item in result.evidence
            ),
            covered_must_cover=tuple(result.covered_must_cover),
        )
