from shared_models.assessment import FeedbackView

from src.domain.entities.feedback_entry import FeedbackEntry


class FeedbackViewMapper:
    @staticmethod
    def to_view(entry: FeedbackEntry) -> FeedbackView:
        return FeedbackView.model_validate(
            {
                "attempt_id": entry.attempt_id,
                "version": entry.version,
                "text": entry.text,
                "source": entry.source,
                "editor_id": entry.editor_id,
                "created_at": entry.created_at,
            }
        )
