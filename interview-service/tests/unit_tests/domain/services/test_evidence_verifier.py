from dataclasses import replace

import pytest
from src.domain.enums.cv_policy import CvPolicy
from src.domain.events.evidence_recorded import EvidenceRecorded
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError
from src.domain.exceptions.session_errors import InconsistentJournalError
from src.domain.services.evidence_verifier import EvidenceVerifier
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.quote_ref import QuoteRef

from tests.fakes.builders import build_events

POLICIES = [CvPolicy.REQUIRED, CvPolicy.NONE]


@pytest.mark.parametrize("policy", POLICIES)
class TestEvidenceVerifier:
    def test_every_evidence_of_the_mock_journal_is_verifiable(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))

        assert state.evidence
        for item in state.evidence:
            EvidenceVerifier.verify_evidence(item, state.messages)

    def test_quote_with_a_shifted_span_is_rejected(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))
        quote = state.evidence[0].quotes[0]
        forged = QuoteRef(event_seq=quote.event_seq, start=quote.start + 1, end=quote.end + 1, text=quote.text)

        with pytest.raises(InconsistentJournalError, match="does not match"):
            EvidenceVerifier.verify_quote(forged, state.messages)

    def test_quote_must_reference_a_candidate_message(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))
        interviewer_seq = state.evidence[0].question_seq
        quote = QuoteRef(event_seq=interviewer_seq, start=0, end=3, text="abc")

        with pytest.raises(InconsistentJournalError, match="not a candidate message"):
            EvidenceVerifier.verify_quote(quote, state.messages)

    def test_evidence_must_point_at_an_interviewer_question(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))
        broken = replace(state.evidence[0], question_seq=1)

        with pytest.raises(InconsistentJournalError, match="not an interviewer message"):
            EvidenceVerifier.verify_evidence(broken, state.messages)

    def test_journal_with_forged_evidence_cannot_be_folded(self, policy: CvPolicy) -> None:
        events = build_events(policy)
        index = next(i for i, event in enumerate(events) if isinstance(event, EvidenceRecorded))
        original = events[index].evidence
        quote = original.quotes[0]
        forged = QuoteRef(event_seq=quote.event_seq, start=quote.start + 1, end=quote.end + 1, text=quote.text)
        events[index] = replace(events[index], evidence=replace(original, quotes=(forged,)))

        with pytest.raises(InconsistentJournalError, match="does not match"):
            JournalFolder.fold(events)


def test_quote_rejects_an_inconsistent_span() -> None:
    with pytest.raises(InvalidDomainValueError):
        QuoteRef(event_seq=1, start=0, end=5, text="abc")
