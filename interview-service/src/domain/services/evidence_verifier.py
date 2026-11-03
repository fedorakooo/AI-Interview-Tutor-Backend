from collections.abc import Mapping

from src.domain.exceptions.session_errors import InconsistentJournalError
from src.domain.value_objects.evidence_item import EvidenceItem
from src.domain.value_objects.message_record import MessageRecord
from src.domain.value_objects.quote_ref import QuoteRef


class EvidenceVerifier:
    @staticmethod
    def verify_quote(quote: QuoteRef, messages: Mapping[int, MessageRecord]) -> None:
        message = messages.get(quote.event_seq)
        if message is None or message.role != "candidate":
            raise InconsistentJournalError(f"Quote references seq {quote.event_seq}, which is not a candidate message")
        if message.text[quote.start : quote.end] != quote.text:
            raise InconsistentJournalError(f"Quote at seq {quote.event_seq} does not match the message text")

    @staticmethod
    def verify_evidence(evidence: EvidenceItem, messages: Mapping[int, MessageRecord]) -> None:
        question = messages.get(evidence.question_seq)
        answer = messages.get(evidence.answer_seq)
        if question is None or question.role != "interviewer":
            raise InconsistentJournalError(
                f"Evidence question_seq {evidence.question_seq} is not an interviewer message"
            )
        if answer is None or answer.role != "candidate":
            raise InconsistentJournalError(f"Evidence answer_seq {evidence.answer_seq} is not a candidate message")
        for quote in evidence.quotes:
            EvidenceVerifier.verify_quote(quote, messages)
