from datetime import UTC, datetime
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

_NAMESPACE = UUID("6f1c2a4e-0b7d-4c1a-9a55-3d2f8e6b7c10")
MOCK_STARTED_AT = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
MOCK_SECONDS_PER_EVENT = 20

MOCK_ORGANIZATION_ID = uuid5(_NAMESPACE, "organization")
MOCK_VACANCY_ID = uuid5(_NAMESPACE, "vacancy")
MOCK_INVITATION_ID = uuid5(_NAMESPACE, "invitation")
MOCK_TEMPLATE_VERSION = 2
MOCK_GENERATOR_VERSION = "mock-1"

GIL_SIGNAL = "Explains GIL impact on CPU-bound vs I/O-bound work"
GENERATOR_SIGNAL = "Uses generators and context managers idiomatically"
WEAK_REFERENCES_SIGNAL = "Cannot explain how the code they wrote works"
INDEX_SIGNAL = "Chooses indexes based on query plans"
ISOLATION_SIGNAL = "Understands transaction isolation trade-offs"
ORM_SIGNAL = "Relies on the ORM without reading generated SQL"
IDEMPOTENCY_SIGNAL = "Designs idempotent write endpoints"
ERROR_MODEL_SIGNAL = "Defines a consistent error model"
BLOCKING_SIGNAL = "Distinguishes awaiting from blocking calls"
EVENT_LOOP_SIGNAL = "Cannot explain the event loop beyond framework usage"
BLOCKING_MYTH_SIGNAL = "Believes blocking calls do not affect other requests"
TEST_SIGNAL = "Isolates external services with test doubles"
TEST_AVOIDANCE_SIGNAL = "Treats testing as someone else's job"
RED_FLAG_CODE = "Cannot explain code the candidate claims to have written"
RED_FLAG_TESTING = "Dismisses automated testing as someone else's job"


def mock_uid(*parts: object) -> UUID:
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
        red_flags=[RED_FLAG_CODE, RED_FLAG_TESTING],
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
                strong_signals=[GIL_SIGNAL, GENERATOR_SIGNAL],
                weak_signals=[WEAK_REFERENCES_SIGNAL],
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
                strong_signals=[INDEX_SIGNAL, ISOLATION_SIGNAL],
                weak_signals=[ORM_SIGNAL],
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
                strong_signals=[IDEMPOTENCY_SIGNAL, ERROR_MODEL_SIGNAL],
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
                strong_signals=[BLOCKING_SIGNAL],
                weak_signals=[EVENT_LOOP_SIGNAL, BLOCKING_MYTH_SIGNAL],
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
                strong_signals=[TEST_SIGNAL],
                weak_signals=[TEST_AVOIDANCE_SIGNAL],
                must_cover=["unit vs integration tests", "test doubles"],
                min_evidence=2,
                max_questions=2,
            ),
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
        cv_correlation_id=mock_uid("cv", cv_policy.value) if cv_policy == CvPolicy.REQUIRED else None,
        candidate_display_name="Alex Candidate",
        job_description="Middle Python backend developer: FastAPI, PostgreSQL, asynchronous services.",
        brief=template.brief,
    )


def mock_attempt_id(cv_policy: CvPolicy) -> UUID:
    return mock_uid("attempt", cv_policy.value)


def mock_session_id(cv_policy: CvPolicy) -> str:
    return f"mock-session-{cv_policy.value}"
