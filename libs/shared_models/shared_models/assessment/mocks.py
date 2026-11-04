from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from shared_models.assessment.contracts import (
    AssessmentContext,
    AssessmentMode,
    AssessmentTemplateSnapshot,
    CustomQuestion,
    CvPolicy,
    FocusArea,
    FocusMethod,
)
from shared_models.assessment.evidence import EvidenceItem, EvidenceLevel, QuoteRef, Verdict
from shared_models.assessment.report import (
    Assessment,
    AssessmentCoverage,
    FocusAssessment,
    RedFlagFinding,
)
from shared_models.assessment.session_events import (
    CandidateMessage,
    CompletionReason,
    CoverageStatus,
    EvidenceRecorded,
    FocusCoverageChanged,
    InterviewerMessage,
    MessageKind,
    SessionCompleted,
    SessionEvent,
    SessionStarted,
)

_NAMESPACE = UUID("6f1c2a4e-0b7d-4c1a-9a55-3d2f8e6b7c10")
_STARTED_AT = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
_SECONDS_PER_EVENT = 20

MOCK_ORGANIZATION_ID = uuid5(_NAMESPACE, "organization")
MOCK_VACANCY_ID = uuid5(_NAMESPACE, "vacancy")
MOCK_INVITATION_ID = uuid5(_NAMESPACE, "invitation")
MOCK_TEMPLATE_VERSION = 2
MOCK_GENERATOR_VERSION = "mock-1"

_GIL_SIGNAL = "Explains GIL impact on CPU-bound vs I/O-bound work"
_GENERATOR_SIGNAL = "Uses generators and context managers idiomatically"
_WEAK_REFERENCES_SIGNAL = "Cannot explain how the code they wrote works"
_INDEX_SIGNAL = "Chooses indexes based on query plans"
_ISOLATION_SIGNAL = "Understands transaction isolation trade-offs"
_ORM_SIGNAL = "Relies on the ORM without reading generated SQL"
_IDEMPOTENCY_SIGNAL = "Designs idempotent write endpoints"
_ERROR_MODEL_SIGNAL = "Defines a consistent error model"
_BLOCKING_SIGNAL = "Distinguishes awaiting from blocking calls"
_EVENT_LOOP_SIGNAL = "Cannot explain the event loop beyond framework usage"
_BLOCKING_MYTH_SIGNAL = "Believes blocking calls do not affect other requests"
_TEST_SIGNAL = "Isolates external services with test doubles"
_TEST_AVOIDANCE_SIGNAL = "Treats testing as someone else's job"
_RED_FLAG_CODE = "Cannot explain code the candidate claims to have written"
_RED_FLAG_TESTING = "Dismisses automated testing as someone else's job"


def _uid(*parts: object) -> UUID:
    return uuid5(_NAMESPACE, "/".join(str(part) for part in parts))


def mock_template(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> AssessmentTemplateSnapshot:
    return AssessmentTemplateSnapshot(
        mode=AssessmentMode.TECHNICAL,
        question_count=9,
        duration_minutes=45,
        attempt_limit=1,
        brief=(
            "We need a middle backend developer for an internal Python/FastAPI service on PostgreSQL. "
            "Focus on practical problem solving rather than trivia."
        ),
        skip=["Frontend frameworks", "Cloud vendor certifications"],
        red_flags=[_RED_FLAG_CODE, _RED_FLAG_TESTING],
        custom_questions=[
            CustomQuestion(
                focus_id="databases",
                text="A report query on a 50M-row orders table became slow after a release. How do you investigate?",
                reference_answer=(
                    "Read the plan with EXPLAIN (ANALYZE, BUFFERS), look for sequential scans or bad join order, "
                    "check statistics and recent migrations, then add or fix an index matching filter and sort columns."
                ),
                required=True,
            ),
            CustomQuestion(
                focus_id="async_io",
                text="What happens if you call time.sleep() inside an async endpoint, and how would you fix it?",
                reference_answer=(
                    "It blocks the whole event loop, stalling every request on that worker; "
                    "use asyncio.sleep or move blocking work to a thread or process pool."
                ),
            ),
        ],
        language="en",
        candidate_feedback=True,
        cv_policy=cv_policy,
        criteria=[
            FocusArea(
                id="python_core",
                skill="Python fundamentals",
                required=True,
                weight=25,
                expected_level="middle",
                what_to_learn="Whether the candidate knows the runtime well enough to write idiomatic, safe code.",
                method=FocusMethod.QUESTIONS,
                strong_signals=[_GIL_SIGNAL, _GENERATOR_SIGNAL],
                weak_signals=[_WEAK_REFERENCES_SIGNAL],
                must_cover=["GIL", "generators", "type hints"],
                min_evidence=2,
                max_questions=3,
            ),
            FocusArea(
                id="databases",
                skill="SQL and PostgreSQL",
                required=True,
                weight=25,
                expected_level="middle",
                what_to_learn="Query tuning, transactions and awareness of what the ORM generates.",
                strong_signals=[_INDEX_SIGNAL, _ISOLATION_SIGNAL],
                weak_signals=[_ORM_SIGNAL],
                must_cover=["indexes", "transactions", "N+1 queries"],
                min_evidence=2,
                max_questions=3,
            ),
            FocusArea(
                id="api_design",
                skill="REST API design with FastAPI",
                required=True,
                weight=20,
                expected_level="middle",
                what_to_learn="Safe write endpoints, pagination and error handling.",
                strong_signals=[_IDEMPOTENCY_SIGNAL, _ERROR_MODEL_SIGNAL],
                weak_signals=["Returns 200 with error bodies"],
                must_cover=["idempotency", "pagination", "error handling"],
                min_evidence=2,
                max_questions=3,
            ),
            FocusArea(
                id="async_io",
                skill="Async and concurrency",
                required=False,
                weight=15,
                expected_level="middle",
                what_to_learn="Understanding of the event loop and blocking calls.",
                strong_signals=[_BLOCKING_SIGNAL],
                weak_signals=[_EVENT_LOOP_SIGNAL, _BLOCKING_MYTH_SIGNAL],
                must_cover=["event loop", "blocking calls", "task cancellation"],
                min_evidence=2,
                max_questions=3,
            ),
            FocusArea(
                id="testing",
                skill="Testing and code quality",
                required=False,
                weight=15,
                expected_level="middle",
                what_to_learn="How the candidate tests code that talks to external systems.",
                method=FocusMethod.PROBE,
                strong_signals=[_TEST_SIGNAL],
                weak_signals=[_TEST_AVOIDANCE_SIGNAL],
                must_cover=["unit vs integration tests", "test doubles"],
                min_evidence=2,
                max_questions=2,
            ),
        ],
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
        (_GIL_SIGNAL,),
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
        (_GENERATOR_SIGNAL,),
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
        (_INDEX_SIGNAL,),
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
        (_ISOLATION_SIGNAL, _ORM_SIGNAL),
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
        (_IDEMPOTENCY_SIGNAL,),
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
        (_ERROR_MODEL_SIGNAL,),
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
        (_BLOCKING_MYTH_SIGNAL,),
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
        (_EVENT_LOOP_SIGNAL,),
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
        (_TEST_AVOIDANCE_SIGNAL,),
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


def mock_session_events(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> list[SessionEvent]:
    """Build a completed session journal, with an intro turn when no CV is attached."""
    template = mock_template(cv_policy)
    cv_attached = cv_policy != CvPolicy.NONE
    session_id = mock_session_id(cv_policy)
    events: list[SessionEvent] = []
    turn_number = 0

    def emit(event_type: type, **fields: object) -> int:
        seq = len(events) + 1
        events.append(
            event_type(
                event_id=_uid("event", session_id, seq),
                session_id=session_id,
                seq=seq,
                occurred_at=_STARTED_AT + timedelta(seconds=_SECONDS_PER_EVENT * seq),
                **fields,
            )
        )
        return seq

    def exchange(question: str, answer: str, kind: MessageKind, **question_fields: object) -> tuple[int, int]:
        nonlocal turn_number
        turn_number += 1
        turn_id = _uid("turn", session_id, turn_number)
        question_seq = emit(InterviewerMessage, turn_id=turn_id, kind=kind, text=question, **question_fields)
        answer_seq = emit(CandidateMessage, turn_id=turn_id, text=answer)
        return question_seq, answer_seq

    emit(
        SessionStarted,
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
            EvidenceRecorded,
            evidence=EvidenceItem(
                evidence_id=_uid("evidence", session_id, index),
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
            FocusCoverageChanged,
            focus_id=turn.focus_id,
            status=CoverageStatus.COVERED if enough else CoverageStatus.IN_PROGRESS,
            evidence_count=evidence_counts[turn.focus_id],
            covered_must_cover=list(covered[turn.focus_id]),
        )

    emit(InterviewerMessage, turn_id=_uid("turn", session_id, "closing"), kind=MessageKind.CLOSING, text=_CLOSING)
    emit(SessionCompleted, reason=CompletionReason.QUESTION_BUDGET)
    return events


def mock_assessment(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> Assessment:
    """Build a report consistent with the mock template and journal."""
    template = mock_template(cv_policy)
    events = mock_session_events(cv_policy)
    all_evidence = [event.evidence for event in events if isinstance(event, EvidenceRecorded)]
    coverage = {event.focus_id: event for event in events if isinstance(event, FocusCoverageChanged)}
    questions_asked = len(
        [
            event
            for event in events
            if isinstance(event, InterviewerMessage) and event.kind in (MessageKind.QUESTION, MessageKind.FOLLOW_UP)
        ]
    )

    focus_assessments: list[FocusAssessment] = []
    for focus in template.criteria:
        summary, rationale, comparison = _FOCUS_TEXTS[focus.id]
        evidence = [item for item in all_evidence if item.focus_id == focus.id]
        verdict, confidence = _FOCUS_VERDICTS[focus.id]
        covered = coverage[focus.id].covered_must_cover
        focus_assessments.append(
            FocusAssessment(
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
    return Assessment(
        assessment_id=_uid("assessment", cv_policy.value),
        attempt_id=mock_attempt_id(cv_policy),
        session_id=mock_session_id(cv_policy),
        template_version=MOCK_TEMPLATE_VERSION,
        generator_version=MOCK_GENERATOR_VERSION,
        generated_at=_STARTED_AT + timedelta(hours=1),
        coverage=AssessmentCoverage(
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
            RedFlagFinding(
                flag=_RED_FLAG_TESTING,
                quotes=[_quote(testing_answer_seq, testing_turn.answer, testing_turn.quotes[0])],
                reasoning="The candidate attributes testing to QA and writes unit tests only occasionally.",
            )
        ],
    )


def mock_assessment_context(cv_policy: CvPolicy = CvPolicy.REQUIRED) -> AssessmentContext:
    template = mock_template(cv_policy)
    return AssessmentContext(
        attempt_id=mock_attempt_id(cv_policy),
        organization_id=MOCK_ORGANIZATION_ID,
        vacancy_id=MOCK_VACANCY_ID,
        invitation_id=MOCK_INVITATION_ID,
        template_version=MOCK_TEMPLATE_VERSION,
        template=template,
        cv_correlation_id=_uid("cv", cv_policy.value) if cv_policy == CvPolicy.REQUIRED else None,
        candidate_display_name="Alex Candidate",
        job_description="Middle Python backend developer: FastAPI, PostgreSQL, asynchronous services.",
        brief=template.brief,
    )


def mock_attempt_id(cv_policy: CvPolicy) -> UUID:
    return _uid("attempt", cv_policy.value)


def mock_session_id(cv_policy: CvPolicy) -> str:
    return f"mock-session-{cv_policy.value}"


def _quote(event_seq: int, message: str, text: str) -> QuoteRef:
    start = message.index(text)
    return QuoteRef(event_seq=event_seq, start=start, end=start + len(text), text=text)
