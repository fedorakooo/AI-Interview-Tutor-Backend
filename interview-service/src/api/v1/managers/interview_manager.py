import json
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from fastapi import WebSocket
from langgraph.graph.state import CompiledStateGraph
from shared_models.cv.cv_data import CVData
from shared_models.interview.report import InterviewReport
from shared_models.interview.session import InterviewSessionStatus
from shared_models.practice.messaging import InterviewCompletedEvent

from src.domain.models.interview_state import InterviewState
from src.domain.models.user_profile import UserProfile
from src.domain.value_objects.conversation_role import ConversationRole
from src.domain.value_objects.interview_stage import OverallInterviewStage
from src.infrastructure.rabbitmq.interview_completed_producer import InterviewCompletedProducer
from src.infrastructure.redis.session_registry import RedisSessionRegistry
from src.logger import app_logger
from src.repositories.interview_session_repository import InterviewSessionRepository
from src.services.utils.agent_initial_state import create_agent_initial_state

SERVER_SHUTDOWN_CLOSE_CODE = 4002


@dataclass
class ActiveSession:
    session_id: str
    user_id: str
    websocket: WebSocket
    started_at: datetime
    cv_correlation_id: str | None = None


class InterviewConnectionManager:
    def __init__(
        self,
        interview_workflow: CompiledStateGraph,
        session_registry: RedisSessionRegistry,
        session_repository: InterviewSessionRepository,
        instance_id: str,
        interview_completed_producer: InterviewCompletedProducer | None = None,
    ) -> None:
        self.interview_workflow = interview_workflow
        self.session_registry = session_registry
        self.session_repository = session_repository
        self.instance_id = instance_id
        self.interview_completed_producer = interview_completed_producer
        self._active_sessions: dict[str, ActiveSession] = {}
        self._accepting_connections = True
        self._is_shutting_down = False

    @staticmethod
    def resolve_instance_id(configured_id: str) -> str:
        if configured_id:
            return configured_id
        return socket.gethostname() or str(uuid4())

    def _graph_config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    async def start_interview(
        self,
        websocket: WebSocket,
        user: UserProfile,
        cv_data: CVData,
        *,
        cv_correlation_id: str | None = None,
    ) -> str:
        if not self._accepting_connections:
            await websocket.close(code=SERVER_SHUTDOWN_CLOSE_CODE)
            raise RuntimeError("Service is shutting down")

        await websocket.accept()
        user_id = str(user.id)
        session_id = str(uuid4())
        initial_state = create_agent_initial_state(user, cv_data)

        await self.session_repository.create_session(
            session_id,
            user_id,
            cv_correlation_id=cv_correlation_id,
            instance_id=self.instance_id,
        )
        await self.session_registry.register_session(session_id, user_id)

        self._active_sessions[session_id] = ActiveSession(
            session_id=session_id,
            user_id=user_id,
            websocket=websocket,
            started_at=datetime.now(UTC),
            cv_correlation_id=cv_correlation_id,
        )

        app_logger.info("Interview started for user=%s session=%s", user_id, session_id)
        await self._process_interview_step(session_id, initial_state)
        return session_id

    async def handle_user_message(self, session_id: str, message: str) -> None:
        session = self._active_sessions.get(session_id)
        if not session:
            app_logger.error("Interview session %s not found", session_id)
            return

        snapshot = await self.interview_workflow.aget_state(self._graph_config(session_id))
        if not snapshot or not snapshot.values:
            app_logger.error("Checkpoint missing for session %s", session_id)
            return

        state = cast(InterviewState, dict(snapshot.values))
        state["messages"].append((ConversationRole.USER, message))
        await self._process_interview_step(session_id, state)

    async def _process_interview_step(self, session_id: str, state: InterviewState) -> None:
        session = self._active_sessions.get(session_id)
        if not session:
            return

        try:
            updated_state = await self.interview_workflow.ainvoke(state, self._graph_config(session_id))
            await self.session_registry.refresh_session(session_id)
            await self.session_repository.update_session(
                session_id,
                overall_stage=str(updated_state["overall_stage"]),
                message_count=len(updated_state.get("messages", [])),
            )

            messages = updated_state.get("messages", [])
            if messages and messages[-1][0] == ConversationRole.AGENT:
                await self._send_message(
                    session_id,
                    {
                        "type": "agent_message",
                        "content": messages[-1][1],
                        "stage": str(updated_state["overall_stage"]),
                        "session_id": session_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

            if updated_state["overall_stage"] == OverallInterviewStage.COMPLETED:
                await self._complete_interview(session_id, updated_state)
        except Exception as exc:
            app_logger.error("Error processing interview step for session %s: %s", session_id, exc)
            await self.session_repository.update_session(
                session_id,
                status=InterviewSessionStatus.FAILED,
                completed_at=datetime.now(UTC),
            )
            await self._send_message(
                session_id,
                {
                    "type": "error",
                    "message": "Error processing interview step",
                    "session_id": session_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

    async def _complete_interview(self, session_id: str, state: InterviewState) -> None:
        report_data = state.get("interview_report")
        report = InterviewReport.model_validate(report_data) if report_data else None
        await self.session_repository.update_session(
            session_id,
            status=InterviewSessionStatus.COMPLETED,
            overall_stage=str(state["overall_stage"]),
            message_count=len(state.get("messages", [])),
            report=report,
            completed_at=datetime.now(UTC),
        )
        await self.session_registry.update_status(session_id, InterviewSessionStatus.COMPLETED)
        await self._publish_interview_completed_event(session_id)
        await self._send_message(
            session_id,
            {
                "type": "interview_complete",
                "message": "Interview completed successfully",
                "session_id": session_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        if report:
            await self._send_message(
                session_id,
                {
                    "type": "report_ready",
                    "session_id": session_id,
                    "report": report.model_dump(mode="json"),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        await self._close_session(session_id)

    async def _publish_interview_completed_event(self, session_id: str) -> None:
        if self.interview_completed_producer is None:
            return

        session = self._active_sessions.get(session_id)
        if session is None:
            app_logger.warning("Cannot publish interview completed event: session %s not found", session_id)
            return

        event = InterviewCompletedEvent(
            event_id=uuid4(),
            user_id=UUID(session.user_id),
            session_id=session_id,
            cv_correlation_id=session.cv_correlation_id,
            published_at=datetime.now(UTC),
        )
        try:
            await self.interview_completed_producer.publish(event)
        except Exception as exc:
            app_logger.error(
                "Failed to publish interview completed event for session %s: %s",
                session_id,
                exc,
            )

    async def _close_session(self, session_id: str) -> None:
        session = self._active_sessions.pop(session_id, None)
        if not session:
            return
        await self.session_registry.unregister_session(session_id, session.user_id)
        try:
            await session.websocket.close()
        except Exception as exc:
            app_logger.warning("Error closing websocket for session %s: %s", session_id, exc)

    async def _send_message(self, session_id: str, message: dict) -> None:
        session = self._active_sessions.get(session_id)
        if not session:
            return
        try:
            await session.websocket.send_text(json.dumps(message))
        except Exception as exc:
            app_logger.error("Error sending message to session %s: %s", session_id, exc)

    async def end_interview(self, session_id: str) -> None:
        session = self._active_sessions.get(session_id)
        if not session:
            return

        await self.session_repository.update_session(
            session_id,
            status=InterviewSessionStatus.SUSPENDED,
            completed_at=datetime.now(UTC),
        )
        await self._close_session(session_id)
        app_logger.info("Interview ended for session %s", session_id)

    async def disconnect_user(self, session_id: str) -> None:
        session = self._active_sessions.get(session_id)
        if not session:
            return

        snapshot = await self.interview_workflow.aget_state(self._graph_config(session_id))
        overall_stage = "Unknown"
        message_count = 0
        if snapshot and snapshot.values:
            overall_stage = str(snapshot.values.get("overall_stage", "Unknown"))
            message_count = len(snapshot.values.get("messages", []))

        await self.session_repository.update_session(
            session_id,
            status=InterviewSessionStatus.SUSPENDED,
            overall_stage=overall_stage,
            message_count=message_count,
            completed_at=datetime.now(UTC),
        )
        await self.session_registry.unregister_session(session_id, session.user_id)
        self._active_sessions.pop(session_id, None)
        app_logger.info("WebSocket disconnected for session %s", session_id)

    def get_interview_status(self, session_id: str) -> dict | None:
        session = self._active_sessions.get(session_id)
        if not session:
            return None
        return {
            "session_id": session_id,
            "user_id": session.user_id,
            "status": "active",
            "started_at": session.started_at.isoformat(),
        }

    @property
    def is_shutting_down(self) -> bool:
        return self._is_shutting_down

    @property
    def accepting_connections(self) -> bool:
        return self._accepting_connections

    async def shutdown(self) -> None:
        self._is_shutting_down = True
        self._accepting_connections = False
        session_ids = list(self._active_sessions.keys())
        for session_id in session_ids:
            session = self._active_sessions.get(session_id)
            if not session:
                continue

            snapshot = await self.interview_workflow.aget_state(self._graph_config(session_id))
            overall_stage = "Unknown"
            message_count = 0
            if snapshot and snapshot.values:
                overall_stage = str(snapshot.values.get("overall_stage", "Unknown"))
                message_count = len(snapshot.values.get("messages", []))

            await self.session_repository.update_session(
                session_id,
                status=InterviewSessionStatus.SUSPENDED,
                overall_stage=overall_stage,
                message_count=message_count,
                completed_at=datetime.now(UTC),
            )
            await self._send_message(
                session_id,
                {
                    "type": "server_shutdown",
                    "message": "Interview service is shutting down. Your progress has been saved.",
                    "session_id": session_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            await self.session_registry.unregister_session(session_id, session.user_id)
            try:
                await session.websocket.close(code=SERVER_SHUTDOWN_CLOSE_CODE)
            except Exception as exc:
                app_logger.warning("Error closing websocket during shutdown for %s: %s", session_id, exc)
            self._active_sessions.pop(session_id, None)

        app_logger.info("Graceful shutdown completed for instance %s", self.instance_id)
