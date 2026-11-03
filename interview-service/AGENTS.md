# interview-service

## 1. Purpose and boundaries

Runs the AI-led structured interview of a candidate over WebSocket and builds the assessment report.

| In scope | Out of scope |
|---|---|
| Interview session lifecycle, event journal, turn flow | Vacancies, templates, users, invitations (user-management-service) |
| Evidence collection, assessment report, candidate feedback | CV analysis (analyze-service) |
| Template draft generation from recruiter text | Notifications (notification-service) |

Cross-service contracts live in `libs/shared_models` (template, context, `AssessmentCompleted`, views and requests). The session journal, evidence and the assessment are the internal model of this service and live in `domain`.

## 2. Layer map

```
src/
  api/             HTTP and WebSocket endpoints, schemas, error mapping
  app/             composition root, lifespan
  application/     services, service interfaces, DTOs, mappers
  domain/          entities, value objects, enums, events, services, interfaces, exceptions
  agents/          LLM agents implementing domain ports
  infrastructure/  Mongo, Redis, RabbitMQ, HTTP clients implementing domain ports
  config.py        settings; top-level module outside the layers
  logger.py        logging setup; top-level module outside the layers
  main.py          entry point; top-level module outside the layers
```

Allowed imports (row imports column):

| | domain | application | agents | infrastructure | api | app | shared_models | third-party |
|---|---|---|---|---|---|---|---|---|
| **domain** | yes | no | no | no | no | no | **no** | **no (stdlib only)** |
| **application** | yes | yes | no | no | no | no | views and requests only | no pydantic-ai, no drivers |
| **agents** | yes | no | yes | no | no | no | no | pydantic-ai, pydantic |
| **infrastructure** | yes | no | no | yes | no | no | contracts | drivers, httpx, pydantic |
| **api** | exceptions, entities | interfaces, DTOs | no | no | yes | no | yes | FastAPI, pydantic |
| **app** | yes | yes | yes | yes | no | yes | yes | yes |

Top-level modules `src/config.py`, `src/logger.py` and `src/main.py` stay where they are and are not part of the table:

- `src.config` may be imported by `api`, `infrastructure`, `app` and `src.logger`; `domain`, `application` and `agents` receive configuration through constructors.
- `src.logger` configures logging and is imported only by `src.main` and `app`.
- `src.main` is the entry point and may import any layer; nothing imports it.

- Libraries from `libs/` other than `shared_models` (for example `jwt_handler`) are imported only by `infrastructure` and `app`. Tokens are verified by an adapter behind a port.
- `api` receives services through the `ApiContainer` protocol in `api/dependencies/`, not by importing `app`.
- `api` maps service DTOs to contract schemas (for example the template draft DTO to `AssessmentTemplateSnapshot`), so `application` does not import the contract template.

`tests/unit_tests/test_architecture.py` enforces this table.

## 3. Where each kind of code goes

| Kind | Location | Notes |
|---|---|---|
| Entity | `domain/entities/` | Identity and behaviour, e.g. `InterviewConnection`, `SessionState` |
| Value object | `domain/value_objects/` | Frozen dataclass, e.g. `NextAction`, `InterviewTemplate`, `FocusArea`, `EvidenceDraft`, agent requests |
| Enum | `domain/enums/` | `StrEnum`, own copies of contract enums |
| Domain event | `domain/events/` | Session journal events, frozen dataclasses |
| Domain service | `domain/services/` | Pure rule, no I/O: `InterviewPlanner`, `EvidenceBuilder`, `AssessmentBuilder`, `FeedbackLeakDetector` |
| Port | `domain/interfaces/{repositories,ai,session,clients,messaging}/` | ABC with `I` prefix, accepts and returns domain types only |
| Domain exception | `domain/exceptions/` | All inherit `InterviewServiceError` |
| Application service | `application/services/` | One per area: `InterviewSessionService`, `AssessmentReportService`, `CandidateFeedbackService`, `TemplateDraftService`, `DataErasureService` |
| Service interface | `application/interfaces/` | `I…Service`, the only thing `api` depends on |
| Internal helper | `application/services/` | Turn flow steps, `CompletionPublisher`, `ReportLoader`, `CompletionOutboxDispatcher`; not exposed to `api` |
| DTO | `application/dtos/` | Stream outputs such as `MessageDelta`, `SessionOutput` |
| Mapper | `application/mappers/` | Domain to contract views, draft to template, assessment to feedback digest |
| Repository | `infrastructure/mongo/repositories/` | Maps documents to domain objects |
| Index creation | `app/container.py` | The container lists the four Mongo repositories and keeps those that satisfy the `IndexedRepository` protocol (`infrastructure/mongo/indexed_repository.py`); the lifespan calls `ensure_indexes` on them |
| Adapter | `infrastructure/{redis,rabbitmq,user_management,jwt}/` | Implements a port; uses the mappers for contract types |
| Infrastructure mapper | `infrastructure/mappers/` | Contract and document types to domain types and back, one class per aggregate; `AssessmentCompleted` has one mapper shared by the publisher and the outbox repository |
| LLM agent | `agents/<role>/` | `agent.py` and `prompts.py`; `schemas.py` (pydantic output schema) and `mapper.py` (schema to domain) only when the agent returns structured output |
| API schema | `api/v1/schemas/` | WebSocket protocol and HTTP bodies |
| Error mapping | `api/errors/error_mapping.py` | One table for HTTP and WebSocket |

## 4. Naming and file layout

- One entity, value object, port or exception group per file; file name is the snake_case class name without the `I` prefix.
- Ports: `I` prefix (`IInterviewEventRepository`). Service interfaces: `I…Service`.
- Domain services: classes, named by role (`…Builder`, `…Planner`, `…Detector`); stateless rules as static methods, configuration through the constructor.
- Mappers: classes with static methods, `…Mapper`.
- Agents: `…Agent`, no framework name in the class name.
- Infrastructure implementations keep the port name without the prefix (`InterviewEventRepository`).
- Application services do not call each other's public methods; shared logic goes to internal helpers.
- A service is split when it exceeds 6 public methods or 250 lines.
- A service shared by several areas is not called through its public methods; the shared part is an internal helper (`ReportLoader`).

## 5. Error handling and logging

- Services and domain raise only `InterviewServiceError` subclasses; never `HTTPException` or library errors.
- Library exceptions (`TokenError`, driver errors) are translated to domain exceptions at the boundary. Driver errors become `DependencyUnavailableError` only in the adapters whose failure the caller handles (event repository, session lock, outbox repository); other driver errors are logged and returned as 500 by the common exception handler.
- `api/security.py` raises `HTTPException` for the internal service token; this is the one allowed exception to the rule above.
- `api/errors/error_mapping.py` maps each exception to `ErrorSpec(http_status, detail, ws_code, ws_close_code, retryable)`; endpoints do not use `except` chains. An unmapped `InterviewServiceError` is logged and returned as 500 / `INTERNAL_ERROR`. `EventSeqConflictError` maps to 409 / `SESSION_BUSY` (retryable).
- Domain does not log. Other layers use `logger = logging.getLogger(__name__)`; logging is configured once in `src/logger.py`.
- Never log tokens, candidate answers, CV content or personal data; log identifiers. A swallowed exception is logged with `logger.exception`.
- Observability (JSON logs, traces, GenAI spans) follows the platform contract and is a separate task.

## 6. Testing rules

- `tests/unit_tests/` mirrors `src/`; fakes live in `tests/fakes/`, one file per port group.
- Domain services are tested directly; application services through the public `I…Service` methods on fakes; agents with a substituted model; WebSocket through a container built by `build_container(...)` with fakes.
- `error_mapping` has a completeness test: every `InterviewServiceError` subclass is mapped or explicitly excluded.
- No network, no real LLM in unit tests. pytest with pytest-asyncio.

## 7. Code style, docstrings and commits

- Python 3.12, full type hints, async I/O, black and ruff, line length 120.
- No module docstrings. Comments are rare.
- Docstrings: ports and service interfaces (class and methods) and domain exceptions. None on entities, value objects, enums, dataclasses, domain services, mappers, schemas, settings or implementations. One plain sentence, no markdown or backticks: imperative for methods, a short noun phrase for a port or interface class, `Raised when …` for an exception and `Base for …` for the base exception of a group.
- Commits: `type(scope): Capitalized imperative summary`, one line, no body, no `Co-Authored-By` trailer. Branches `feat/…`, `bugfix/…`, `refactor/…`.

## 8. Checklist before finishing a change

- Imports follow the table in section 2; `test_architecture.py` passes.
- New domain code uses only the standard library.
- New port in the right `interfaces/` group, with a fake in `tests/fakes/`.
- New exception inherits `InterviewServiceError` and has an `error_mapping` entry.
- No logging in `domain`; no personal data in logs.
- Docstring and comment rules from section 7 hold (grep for `"""` and backticks in new files).
- Tests mirror the changed layer; ruff and black pass. Report what was not run.

## 9. Known deviations

| Deviation | Reason or plan |
|---|---|
| `libs/shared_models` still holds the old session and assessment model (`session_events`, `session_state`, `report`, `scoring`, `verification`, `mocks`) and `build_overview` / `build_focus_detail` in `views.py`; `interview-service` no longer imports them outside `infrastructure` (persistence format) and tests (`mocks`), but `user-management-service/tests/unit_tests/test_interview_report_client.py` uses `build_overview`, `build_focus_detail`, `fold_events` and `mocks`, and `libs/shared_models/tests/` uses `mocks` | Move the test data of those consumers to static fixtures, then delete the unused model from `shared_models`; `Verdict` stays a contract enum. The view-building logic now exists twice (`application/mappers/report_view_mapper.py` and `views.py`) until then |
| No Unit of Work, unlike the default | Append-only journal with unique `(session_id, seq)` and a Redis lock; revisit if two repositories need an atomic write and Mongo transactions are available |
| `record_evidence` appends events one by one, so it is not atomic: the `covered_must_cover` topics of an interrupted evaluation are lost, and a crash in the middle of several `EvidenceRecorded` events drops the remaining ones. Lost topics show up as false `missed_must_cover` in the report (`assessment_builder.py`) and in the growth topics of the candidate feedback (`feedback_digest_builder.py`) | Persist the topics in the evidence event or use a Mongo transaction (check the replica set first) |
| `InterviewerTurn.run` is not atomic either: a crash between `InterviewerMessage(CLOSING)` and `SessionCompleted` repeats the turn without completing the session, and a reconnect writes a second closing message | Same fix as above: one atomic append of the closing message and the completion event |
| Observability not wired | Separate task; `agents/` is the place for GenAI instrumentation |
| Mongo replica-set status unknown | Check before any transaction-based change |
