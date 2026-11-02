from uuid import UUID, uuid5

from shared_models.assessment import AssessmentTemplateSnapshot, EvidenceItem, QuoteRef

from src.domain.interview.dto import EvidenceDraft

EVIDENCE_NAMESPACE = UUID("2c0a7a0e-5d0b-4d5e-9d57-1f7c9b3a6e44")
MAX_REASONING_LENGTH = 1000


def build_evidence_items(
    drafts: list[EvidenceDraft],
    template: AssessmentTemplateSnapshot,
    session_id: str,
    question_seq: int,
    answer_seq: int,
    answer_text: str,
) -> list[EvidenceItem]:
    """Turn model drafts into verified evidence, dropping any quote that is not in the answer."""
    items: list[EvidenceItem] = []
    seen_focus: set[str] = set()
    ids = {focus.id for focus in template.criteria}
    for index, draft in enumerate(drafts):
        if draft.focus_id not in ids or draft.focus_id in seen_focus:
            continue
        quotes = _locate_quotes(draft.quotes, answer_seq, answer_text)
        if not quotes:
            continue
        focus = template.focus_by_id(draft.focus_id)
        known_signals = set(focus.strong_signals) | set(focus.weak_signals)
        items.append(
            EvidenceItem(
                evidence_id=uuid5(EVIDENCE_NAMESPACE, f"{session_id}/{answer_seq}/{index}"),
                focus_id=draft.focus_id,
                question_seq=question_seq,
                answer_seq=answer_seq,
                level=draft.level,
                matched_signals=[signal for signal in draft.matched_signals if signal in known_signals],
                quotes=quotes,
                reasoning=draft.reasoning[:MAX_REASONING_LENGTH],
            )
        )
        seen_focus.add(draft.focus_id)
    return items


def _locate_quotes(candidates: list[str], answer_seq: int, answer_text: str) -> list[QuoteRef]:
    quotes: list[QuoteRef] = []
    for candidate in candidates[:5]:
        text = candidate.strip()
        start = answer_text.find(text) if text else -1
        if start >= 0 and len(text) <= 2000:
            quotes.append(QuoteRef(event_seq=answer_seq, start=start, end=start + len(text), text=text))
    return quotes
