from uuid import UUID

from src.domain.entities.assessment import Assessment
from src.domain.entities.feedback_entry import FeedbackEntry
from src.domain.entities.review_entry import ReviewEntry
from src.domain.events.assessment_completed import AssessmentCompleted
from src.domain.events.session_event import SessionEvent
from src.domain.exceptions.session_errors import EventSeqConflictError
from src.domain.interfaces.repositories.assessment_repository import IAssessmentRepository
from src.domain.interfaces.repositories.attempt_data_repository import IAttemptDataRepository
from src.domain.interfaces.repositories.candidate_cv_repository import ICandidateCvRepository
from src.domain.interfaces.repositories.completion_outbox_repository import ICompletionOutboxRepository
from src.domain.interfaces.repositories.feedback_repository import IFeedbackRepository
from src.domain.interfaces.repositories.interview_event_repository import IInterviewEventRepository
from src.domain.value_objects.candidate_cv import CandidateCv


class InMemoryInterviewEventRepository(IInterviewEventRepository):
    def __init__(self) -> None:
        self.events: dict[str, list[SessionEvent]] = {}

    async def append(self, event: SessionEvent) -> None:
        stored = self.events.setdefault(event.session_id, [])
        if any(existing.seq == event.seq for existing in stored):
            raise EventSeqConflictError()
        stored.append(event)

    async def list_events(self, session_id: str) -> list[SessionEvent]:
        return sorted(self.events.get(session_id, []), key=lambda event: event.seq)


class FakeCvRepository(ICandidateCvRepository):
    def __init__(self, cv: CandidateCv | None = None) -> None:
        self.cv = cv
        self.requested: list[UUID] = []

    async def get(self, correlation_id: UUID) -> CandidateCv | None:
        self.requested.append(correlation_id)
        return self.cv


class InMemoryAssessmentRepository(IAssessmentRepository):
    def __init__(self) -> None:
        self.assessments: dict[UUID, Assessment] = {}
        self.reviews: list[tuple[UUID, str, ReviewEntry]] = []

    async def get(self, attempt_id: UUID) -> Assessment | None:
        return self.assessments.get(attempt_id)

    async def save(self, assessment: Assessment) -> None:
        self.assessments.setdefault(assessment.attempt_id, assessment)

    async def add_review(self, attempt_id: UUID, focus_id: str, entry: ReviewEntry) -> None:
        self.reviews.append((attempt_id, focus_id, entry))

    async def list_reviews(self, attempt_id: UUID) -> dict[str, list[ReviewEntry]]:
        grouped: dict[str, list[ReviewEntry]] = {}
        for stored_attempt, focus_id, entry in self.reviews:
            if stored_attempt == attempt_id:
                grouped.setdefault(focus_id, []).append(entry)
        return grouped


class InMemoryCompletionOutboxRepository(ICompletionOutboxRepository):
    def __init__(self) -> None:
        self.events: dict[UUID, AssessmentCompleted] = {}
        self.published: set[UUID] = set()

    async def enqueue(self, event: AssessmentCompleted) -> None:
        self.events.setdefault(event.event_id, event)

    async def list_pending(self, limit: int) -> list[AssessmentCompleted]:
        return [e for e in self.events.values() if e.event_id not in self.published][:limit]

    async def mark_published(self, event_id: UUID) -> None:
        self.published.add(event_id)


class InMemoryFeedbackRepository(IFeedbackRepository):
    def __init__(self) -> None:
        self.versions: list[FeedbackEntry] = []

    async def latest(self, attempt_id: UUID) -> FeedbackEntry | None:
        return max((v for v in self.versions if v.attempt_id == attempt_id), key=lambda v: v.version, default=None)

    async def append(self, feedback: FeedbackEntry) -> bool:
        if any(v.attempt_id == feedback.attempt_id and v.version == feedback.version for v in self.versions):
            return False
        self.versions.append(feedback)
        return True


class InMemoryAttemptDataRepository(IAttemptDataRepository):
    def __init__(self) -> None:
        self.erased: list[tuple[UUID, UUID | None]] = []

    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> dict[str, int]:
        self.erased.append((attempt_id, cv_correlation_id))
        return {"events": 0}
