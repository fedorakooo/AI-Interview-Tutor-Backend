import pytest
from src.application.mappers.report_view_mapper import ReportViewMapper
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.verdict import Verdict
from src.domain.services.journal_folder import JournalFolder

from tests.fakes.builders import build_assessment, build_events, build_template


@pytest.mark.parametrize("policy", [CvPolicy.REQUIRED, CvPolicy.NONE])
class TestReportViewMapper:
    def test_overview_has_no_quotes_and_carries_importance(self, policy: CvPolicy) -> None:
        overview = ReportViewMapper.overview(build_assessment(policy), build_template(policy))

        dumped = overview.model_dump_json()
        assert '"quotes"' not in dumped and '"text"' not in dumped
        by_id = {item.focus_id: item for item in overview.focus}
        assert by_id["databases"].required is True and by_id["databases"].weight == 25
        assert by_id["databases"].matched_weak_signals
        assert by_id["testing"].verdict == Verdict.NOT_ASSESSED
        assert overview.red_flags[0].flag

    def test_focus_detail_builds_the_timeline_from_the_journal(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))

        detail = ReportViewMapper.focus_detail(build_assessment(policy), build_template(policy), state, "databases")

        assert [entry.custom_question for entry in detail.timeline] == [True, False]
        assert all(entry.evidence is not None for entry in detail.timeline)
        assert detail.timeline[0].answer_text.startswith("First I'd get the actual plan")
        assert detail.reference_answer and "EXPLAIN" in detail.reference_answer
        assert detail.focus.focus_id == "databases"

    def test_focus_without_a_custom_question_has_no_reference(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))

        detail = ReportViewMapper.focus_detail(build_assessment(policy), build_template(policy), state, "api_design")

        assert detail.reference_answer is None
