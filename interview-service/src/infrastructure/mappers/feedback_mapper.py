from shared_models.assessment import FeedbackView

from src.domain.entities.feedback_entry import FeedbackEntry


class FeedbackMapper:
    @staticmethod
    def to_contract(entry: FeedbackEntry) -> FeedbackView:
        return FeedbackView(
            attempt_id=entry.attempt_id,
            version=entry.version,
            text=entry.text,
            source=entry.source,
            editor_id=entry.editor_id,
            created_at=entry.created_at,
        )

    @staticmethod
    def to_domain(view: FeedbackView) -> FeedbackEntry:
        return FeedbackEntry(
            attempt_id=view.attempt_id,
            version=view.version,
            text=view.text,
            source=view.source,
            editor_id=view.editor_id,
            created_at=view.created_at,
        )
