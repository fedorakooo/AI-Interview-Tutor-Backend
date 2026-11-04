from src.domain.enums.evidence_level import EvidenceLevel
from src.domain.value_objects.evidence_item import EvidenceItem
from src.domain.value_objects.quote_ref import QuoteRef
from src.infrastructure.mongo.documents.evidence_document import EvidenceDocument, QuoteDocument


class EvidenceMapper:
    @staticmethod
    def quote_to_model(quote: QuoteRef) -> QuoteDocument:
        return QuoteDocument(event_seq=quote.event_seq, start=quote.start, end=quote.end, text=quote.text)

    @staticmethod
    def quote_to_domain(quote: QuoteDocument) -> QuoteRef:
        return QuoteRef(event_seq=quote.event_seq, start=quote.start, end=quote.end, text=quote.text)

    @staticmethod
    def to_model(item: EvidenceItem) -> EvidenceDocument:
        return EvidenceDocument(
            evidence_id=item.evidence_id,
            focus_id=item.focus_id,
            question_seq=item.question_seq,
            answer_seq=item.answer_seq,
            level=EvidenceLevel(item.level.value),
            matched_signals=list(item.matched_signals),
            quotes=[EvidenceMapper.quote_to_model(quote) for quote in item.quotes],
            reasoning=item.reasoning,
        )

    @staticmethod
    def to_domain(item: EvidenceDocument) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=item.evidence_id,
            focus_id=item.focus_id,
            question_seq=item.question_seq,
            answer_seq=item.answer_seq,
            level=EvidenceLevel(item.level.value),
            matched_signals=tuple(item.matched_signals),
            quotes=tuple(EvidenceMapper.quote_to_domain(quote) for quote in item.quotes),
            reasoning=item.reasoning,
        )
