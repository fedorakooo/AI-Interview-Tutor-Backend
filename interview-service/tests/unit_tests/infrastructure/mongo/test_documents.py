from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from shared_models.assessment import CvPolicy, Verdict
from src.infrastructure.mongo.documents.assessment_document import AssessmentDocument, ReviewEntryDocument
from src.infrastructure.mongo.documents.evidence_document import QuoteDocument
from src.infrastructure.mongo.documents.session_event_document import (
    SessionCompletedDocument,
    SessionEventAdapter,
    SessionStartedDocument,
)

from tests.fakes import journal_mocks

POLICIES = [CvPolicy.REQUIRED, CvPolicy.NONE]


@pytest.mark.parametrize("policy", POLICIES)
def test_assessment_document_round_trips_through_json(policy: CvPolicy) -> None:
    assessment = journal_mocks.mock_assessment(policy)

    restored = AssessmentDocument.model_validate_json(assessment.model_dump_json())

    assert restored == assessment


@pytest.mark.parametrize("policy", POLICIES)
def test_event_documents_round_trip_through_the_discriminated_union(policy: CvPolicy) -> None:
    events = journal_mocks.mock_session_events(policy)

    restored = [SessionEventAdapter.validate_json(SessionEventAdapter.dump_json(event)) for event in events]

    assert restored == events
    assert isinstance(restored[0], SessionStartedDocument)
    assert isinstance(restored[-1], SessionCompletedDocument)


def test_quote_document_rejects_an_inconsistent_span() -> None:
    with pytest.raises(ValidationError):
        QuoteDocument(event_seq=1, start=0, end=5, text="abc")


def test_review_entry_document_accepts_a_manual_verdict_as_a_string() -> None:
    entry = ReviewEntryDocument.model_validate(
        {
            "review_id": str(uuid4()),
            "author_id": str(uuid4()),
            "created_at": datetime(2026, 11, 3, tzinfo=UTC).isoformat(),
            "comment": "note",
            "manual_verdict": "adequate",
        }
    )

    assert entry.manual_verdict == Verdict.ADEQUATE
