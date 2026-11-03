from src.agents.assessment_writer.schemas import AssessmentTextsSchema
from src.domain.value_objects.assessment_texts import AssessmentTexts
from src.domain.value_objects.focus_text import FocusText
from src.domain.value_objects.red_flag_draft import RedFlagDraft


class AssessmentTextsMapper:
    @staticmethod
    def to_domain(texts: AssessmentTextsSchema) -> AssessmentTexts:
        return AssessmentTexts(
            overall_summary=texts.overall_summary,
            focus=tuple(
                FocusText(
                    focus_id=item.focus_id,
                    summary_short=item.summary_short,
                    rationale=item.rationale,
                    reference_comparison=item.reference_comparison,
                )
                for item in texts.focus
            ),
            red_flags=tuple(
                RedFlagDraft(flag=item.flag, quotes=tuple(item.quotes), reasoning=item.reasoning)
                for item in texts.red_flags
            ),
        )
