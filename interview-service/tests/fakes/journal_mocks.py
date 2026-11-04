from dataclasses import dataclass
from datetime import timedelta

from shared_models.assessment.contracts import CvPolicy
from shared_models.assessment.evidence import EvidenceLevel, Verdict
from shared_models.assessment.mocks import (
    BLOCKING_MYTH_SIGNAL,
    ERROR_MODEL_SIGNAL,
    EVENT_LOOP_SIGNAL,
    GENERATOR_SIGNAL,
    GIL_SIGNAL,
    IDEMPOTENCY_SIGNAL,
    INDEX_SIGNAL,
    ISOLATION_SIGNAL,
    MOCK_GENERATOR_VERSION,
    MOCK_SECONDS_PER_EVENT,
    MOCK_STARTED_AT,
    MOCK_TEMPLATE_VERSION,
    ORM_SIGNAL,
    RED_FLAG_TESTING,
    TEST_AVOIDANCE_SIGNAL,
    mock_attempt_id,
    mock_session_id,
    mock_template,
    mock_uid,
)
from src.infrastructure.mongo.documents.assessment_document import (
    AssessmentCoverageDocument,
    AssessmentDocument,
    FocusAssessmentDocument,
    RedFlagFindingDocument,
)
from src.infrastructure.mongo.documents.evidence_document import EvidenceDocument, QuoteDocument
from src.infrastructure.mongo.documents.session_event_document import (
    CandidateMessageDocument,
    CompletionReason,
    CoverageStatus,
    EvidenceRecordedDocument,
    FocusCoverageChangedDocument,
    InterviewerMessageDocument,
    MessageKind,
    SessionCompletedDocument,
    SessionEventDocument,
    SessionStartedDocument,
)


@dataclass(frozen=True)
class _Turn:
    focus_id: str
    kind: MessageKind
    question: str
    answer: str
    level: EvidenceLevel
    signals: tuple[str, ...]
    quotes: tuple[str, ...]
    reasoning: str
    covered: tuple[str, ...]
    custom_question_index: int | None = None


_INTRO_QUESTION = "Hi! Before we start, could you briefly describe your relevant experience?"
_INTRO_ANSWER = (
    "I have about three years of backend work in Python, mostly FastAPI services on PostgreSQL, plus some Celery jobs."
)
_CLOSING = "Thank you, that was the last question. Your answers have been saved."

_TURNS: tuple[_Turn, ...] = (
    _Turn(
        "python_core",
        MessageKind.QUESTION,
        "How does the GIL affect a service that does both CPU-heavy work and network calls?",
        "The GIL means only one thread runs Python bytecode at a time, so threads don't speed up CPU-bound work. "
        "For network calls threads or asyncio are fine because the GIL is released while waiting on I/O. "
        "For CPU-heavy parts I would use multiprocessing or move the work to a worker.",
        EvidenceLevel.STRONG,
        (GIL_SIGNAL,),
        ("threads don't speed up CPU-bound work", "the GIL is released while waiting on I/O"),
        "Correctly separates CPU-bound from I/O-bound work and names a practical alternative.",
        ("GIL",),
    ),
    _Turn(
        "python_core",
        MessageKind.FOLLOW_UP,
        "Can you give an example where a generator is a better choice than returning a list?",
        "Streaming a large CSV export: a generator yields rows one by one so memory stays flat, and the response "
        "can start before the whole file is built. I'd also use it with a context manager so the file is closed.",
        EvidenceLevel.ADEQUATE,
        (GENERATOR_SIGNAL,),
        ("a generator yields rows one by one so memory stays flat",),
        "Gives a concrete use case and mentions resource cleanup, without discussing generator pitfalls.",
        ("generators",),
    ),
    _Turn(
        "databases",
        MessageKind.QUESTION,
        "A report query on a 50M-row orders table became slow after a release. How do you investigate?",
        "First I'd get the actual plan with EXPLAIN ANALYZE to see if it's a sequential scan or a bad join order. "
        "Then check whether a recent migration dropped an index or the statistics are stale, so I'd run ANALYZE. "
        "If an index is missing I'd add a composite one matching the filter and sort columns, creating it "
        "concurrently in production.",
        EvidenceLevel.STRONG,
        (INDEX_SIGNAL,),
        ("get the actual plan with EXPLAIN ANALYZE", "composite one matching the filter and sort columns"),
        "Plan-first investigation with a safe production index rollout.",
        ("indexes",),
        custom_question_index=0,
    ),
    _Turn(
        "databases",
        MessageKind.FOLLOW_UP,
        "How do you decide on a transaction isolation level, and what do you watch for when using an ORM?",
        "Read committed is the default in Postgres and is enough for most requests. When I need to avoid lost "
        "updates I'd use SELECT FOR UPDATE or a version column rather than raising isolation. With the ORM I "
        "mostly trust it, I rarely look at the generated SQL.",
        EvidenceLevel.ADEQUATE,
        (ISOLATION_SIGNAL, ORM_SIGNAL),
        ("SELECT FOR UPDATE or a version column rather than raising isolation", "I rarely look at the generated SQL"),
        "Sound locking choices, but admits not inspecting ORM-generated SQL.",
        ("transactions",),
    ),
    _Turn(
        "api_design",
        MessageKind.QUESTION,
        "You expose POST /payments and a client retries after a timeout. How do you avoid charging twice?",
        "I'd require an Idempotency-Key header and store the key with the response for some time. A repeated "
        "request with the same key returns the stored result instead of creating a new payment. The key should be "
        "unique per client and the insert guarded by a unique constraint.",
        EvidenceLevel.STRONG,
        (IDEMPOTENCY_SIGNAL,),
        ("require an Idempotency-Key header", "the insert guarded by a unique constraint"),
        "Complete idempotency design including a race-safe constraint.",
        ("idempotency",),
    ),
    _Turn(
        "api_design",
        MessageKind.FOLLOW_UP,
        "How would you paginate a list endpoint that grows to millions of rows, and how do you report errors?",
        "Offset pagination gets slow on big tables, so I'd use keyset pagination on an indexed column like "
        "created_at plus id. For errors I use proper status codes and a JSON body with a code and message, and "
        "domain exceptions are mapped in one place.",
        EvidenceLevel.ADEQUATE,
        (ERROR_MODEL_SIGNAL,),
        ("use keyset pagination", "domain exceptions are mapped in one place"),
        "Knows the keyset trade-off and centralises error mapping.",
        ("pagination", "error handling"),
    ),
    _Turn(
        "async_io",
        MessageKind.QUESTION,
        "What happens if you call time.sleep() inside an async endpoint, and how would you fix it?",
        "It would just slow that one request down, I think. Other requests are served by other workers, so it's "
        "not a big deal. I'd probably leave it or add more workers.",
        EvidenceLevel.WEAK,
        (BLOCKING_MYTH_SIGNAL,),
        ("It would just slow that one request down", "not a big deal"),
        "Does not recognise that a blocking call stalls the whole event loop.",
        (),
        custom_question_index=1,
    ),
    _Turn(
        "async_io",
        MessageKind.FOLLOW_UP,
        "What does the event loop do while your handler awaits a database call?",
        "It switches to other coroutines I guess. I haven't used asyncio much directly, FastAPI handles it for me.",
        EvidenceLevel.WEAK,
        (EVENT_LOOP_SIGNAL,),
        ("I haven't used asyncio much directly",),
        "Vague on the event loop; relies on the framework.",
        ("event loop",),
    ),
    _Turn(
        "testing",
        MessageKind.QUESTION,
        "How do you test a service function that calls an external payment API?",
        "Honestly QA handles most of that on our team. I write a few unit tests when I remember, and I'd mock "
        "the HTTP client.",
        EvidenceLevel.WEAK,
        (TEST_AVOIDANCE_SIGNAL,),
        ("QA handles most of that on our team",),
        "Delegates testing to QA; only a single mention of mocking.",
        ("test doubles",),
    ),
)

_FOCUS_TEXTS: dict[str, tuple[str, str, str | None]] = {
    "python_core": (
        "Solid grasp of the GIL and idiomatic generator use; type hints were not discussed.",
        "Both answers show practical understanding. The GIL answer separates CPU- and I/O-bound work and proposes "
        "multiprocessing; the generator example is concrete. Type hints remain unassessed within the budget.",
        None,
    ),
    "databases": (
        "Strong query investigation; weaker on ORM awareness and N+1 queries.",
        "The slow-query answer is plan-driven with a safe index rollout. Transaction choices are sound, but the "
        "candidate rarely inspects ORM SQL and N+1 queries were not covered.",
        "Matches the reference on plan-first investigation and indexing; does not mention BUFFERS output.",
    ),
    "api_design": (
        "Designs idempotent endpoints, knows keyset pagination and centralises error handling.",
        "Idempotency was answered completely, including the unique-constraint race. Pagination and error mapping "
        "were covered at a practical level.",
        None,
    ),
    "async_io": (
        "Believes blocking calls only slow one request; limited asyncio understanding.",
        "The time.sleep answer misses that the event loop is blocked, and the follow-up relies on framework "
        "defaults. Blocking calls and task cancellation were not covered.",
        "Diverges from the reference: the answer misses that a blocking call stalls the whole event loop.",
    ),
    "testing": (
        "Only one answer collected; below the required evidence for this focus area.",
        "The single answer suggests testing is delegated to QA, but one data point is not enough for a verdict.",
        None,
    ),
}


_FOCUS_VERDICTS: dict[str, tuple[Verdict, float]] = {
    "python_core": (Verdict.STRONG, 0.75),
    "databases": (Verdict.ADEQUATE, 0.75),
    "api_design": (Verdict.STRONG, 0.75),
    "async_io": (Verdict.WEAK, 0.75),
    "testing": (Verdict.NOT_ASSESSED, 0.2),
}


def mock_session_events(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> list[SessionEventDocument]:
    """Build a completed session journal, with an intro turn when no CV is attached."""
    template = mock_template(cv_policy)
    cv_attached = cv_policy != CvPolicy.NONE
    session_id = mock_session_id(cv_policy)
    events: list[SessionEventDocument] = []
    turn_number = 0

    def emit(event_type: type, **fields: object) -> int:
        seq = len(events) + 1
        events.append(
            event_type(
                event_id=mock_uid("event", session_id, seq),
                session_id=session_id,
                seq=seq,
                occurred_at=MOCK_STARTED_AT + timedelta(seconds=MOCK_SECONDS_PER_EVENT * seq),
                **fields,
            )
        )
        return seq

    def exchange(question: str, answer: str, kind: MessageKind, **question_fields: object) -> tuple[int, int]:
        nonlocal turn_number
        turn_number += 1
        turn_id = mock_uid("turn", session_id, turn_number)
        question_seq = emit(InterviewerMessageDocument, turn_id=turn_id, kind=kind, text=question, **question_fields)
        answer_seq = emit(CandidateMessageDocument, turn_id=turn_id, text=answer)
        return question_seq, answer_seq

    emit(
        SessionStartedDocument,
        attempt_id=mock_attempt_id(cv_policy),
        template_version=MOCK_TEMPLATE_VERSION,
        cv_attached=cv_attached,
    )
    if not cv_attached:
        exchange(_INTRO_QUESTION, _INTRO_ANSWER, MessageKind.INTRO)

    evidence_counts: dict[str, int] = {}
    covered: dict[str, list[str]] = {}
    for index, turn in enumerate(_TURNS, start=1):
        question_seq, answer_seq = exchange(
            turn.question,
            turn.answer,
            turn.kind,
            focus_id=turn.focus_id,
            custom_question_index=turn.custom_question_index,
        )
        emit(
            EvidenceRecordedDocument,
            evidence=EvidenceDocument(
                evidence_id=mock_uid("evidence", session_id, index),
                focus_id=turn.focus_id,
                question_seq=question_seq,
                answer_seq=answer_seq,
                level=turn.level,
                matched_signals=list(turn.signals),
                quotes=[_quote(answer_seq, turn.answer, text) for text in turn.quotes],
                reasoning=turn.reasoning,
            ),
        )
        evidence_counts[turn.focus_id] = evidence_counts.get(turn.focus_id, 0) + 1
        covered.setdefault(turn.focus_id, []).extend(turn.covered)
        focus = template.focus_by_id(turn.focus_id)
        enough = evidence_counts[turn.focus_id] >= focus.min_evidence
        emit(
            FocusCoverageChangedDocument,
            focus_id=turn.focus_id,
            status=CoverageStatus.COVERED if enough else CoverageStatus.IN_PROGRESS,
            evidence_count=evidence_counts[turn.focus_id],
            covered_must_cover=list(covered[turn.focus_id]),
        )

    emit(
        InterviewerMessageDocument,
        turn_id=mock_uid("turn", session_id, "closing"),
        kind=MessageKind.CLOSING,
        text=_CLOSING,
    )
    emit(SessionCompletedDocument, reason=CompletionReason.QUESTION_BUDGET)
    return events


def mock_assessment(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> AssessmentDocument:
    """Build a report consistent with the mock template and journal."""
    template = mock_template(cv_policy)
    events = mock_session_events(cv_policy)
    all_evidence = [event.evidence for event in events if isinstance(event, EvidenceRecordedDocument)]
    coverage = {event.focus_id: event for event in events if isinstance(event, FocusCoverageChangedDocument)}
    questions_asked = len(
        [
            event
            for event in events
            if isinstance(event, InterviewerMessageDocument)
            and event.kind in (MessageKind.QUESTION, MessageKind.FOLLOW_UP)
        ]
    )

    focus_assessments: list[FocusAssessmentDocument] = []
    for focus in template.criteria:
        summary, rationale, comparison = _FOCUS_TEXTS[focus.id]
        evidence = [item for item in all_evidence if item.focus_id == focus.id]
        verdict, confidence = _FOCUS_VERDICTS[focus.id]
        covered = coverage[focus.id].covered_must_cover
        focus_assessments.append(
            FocusAssessmentDocument(
                focus_id=focus.id,
                verdict=verdict,
                confidence=confidence,
                summary_short=summary,
                rationale=rationale,
                evidence=evidence,
                covered_must_cover=list(covered),
                missed_must_cover=[topic for topic in focus.must_cover if topic not in covered],
                reference_comparison=comparison,
            )
        )

    testing_turn = _TURNS[-1]
    testing_answer_seq = next(item.answer_seq for item in all_evidence if item.focus_id == "testing")
    assessed = [item for item in focus_assessments if item.verdict != Verdict.NOT_ASSESSED]
    required_ids = {focus.id for focus in template.criteria if focus.required}
    return AssessmentDocument(
        assessment_id=mock_uid("assessment", cv_policy.value),
        attempt_id=mock_attempt_id(cv_policy),
        session_id=mock_session_id(cv_policy),
        template_version=MOCK_TEMPLATE_VERSION,
        generator_version=MOCK_GENERATOR_VERSION,
        generated_at=MOCK_STARTED_AT + timedelta(hours=1),
        coverage=AssessmentCoverageDocument(
            focus_total=len(template.criteria),
            focus_assessed=len(assessed),
            required_total=len(required_ids),
            required_assessed=len([item for item in assessed if item.focus_id in required_ids]),
            questions_asked=questions_asked,
        ),
        overall_summary=(
            "Strong on Python fundamentals and API design, adequate on databases. Async knowledge is weak, and "
            "testing could not be assessed within the question budget."
        ),
        focus=focus_assessments,
        red_flags=[
            RedFlagFindingDocument(
                flag=RED_FLAG_TESTING,
                quotes=[_quote(testing_answer_seq, testing_turn.answer, testing_turn.quotes[0])],
                reasoning="The candidate attributes testing to QA and writes unit tests only occasionally.",
            )
        ],
    )


def _quote(event_seq: int, message: str, text: str) -> QuoteDocument:
    start = message.index(text)
    return QuoteDocument(event_seq=event_seq, start=start, end=start + len(text), text=text)
