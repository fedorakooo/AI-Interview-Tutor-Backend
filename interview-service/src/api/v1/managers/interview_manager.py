import json
from datetime import datetime

from fastapi import WebSocket
from langgraph.graph import StateGraph

from src.agent.workflow import create_interview_workflow
from src.domain.models.cv_data import CVData
from src.domain.models.user_profile import UserProfile
from src.domain.value_objects.conversation_role import ConversationRole
from src.logger import app_logger
from src.services.utils.agent_initial_state import create_agent_initial_state


class InterviewConnectionManager:
    def __init__(self, interview_workflow: StateGraph):
        self.interview_workflow: StateGraph = interview_workflow
        self._active_interviews: dict[str, dict] = {}

    async def start_interview(self, websocket: WebSocket, user: UserProfile, cv_data: CVData) -> None:
        await websocket.accept()

        user_id = str(user.id)

        if user_id in self._active_interviews:
            await self.end_interview(user_id)

        initial_state = create_agent_initial_state(user, cv_data)

        self._active_interviews[user_id] = {
            "websocket": websocket,
            "state": initial_state,
            "started_at": datetime.now(),
            "is_active": True,
        }

        app_logger.info(f"Interview started for user: {user_id}")

        await self._process_interview_step(user_id)

    async def handle_user_message(self, user_id: str, message: str):
        if user_id not in self._active_interviews:
            app_logger.error(f"Interview for user {user_id} not found")
            return

        interview_data = self._active_interviews[user_id]
        interview_data["state"]["messages"].append((ConversationRole.USER, message))

        await self._process_interview_step(user_id)

    async def _process_interview_step(self, user_id: str):
        interview_data = self._active_interviews[user_id]
        state = interview_data["state"]

        try:
            config = {"configurable": {"thread_id": user_id}}

            updated_state = await self.interview_workflow.ainvoke(state, config)
            interview_data["state"] = updated_state

            last_message = updated_state["messages"][-1]
            if last_message[0] == ConversationRole.AGENT:
                await self._send_message(
                    user_id,
                    {
                        "type": "agent_message",
                        "content": last_message[1],
                        "stage": updated_state["overall_stage"].value,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            if updated_state["overall_stage"] == "END":
                await self._send_message(
                    user_id,
                    {
                        "type": "interview_complete",
                        "message": "Interview completed successfully",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                await self.end_interview(user_id)

        except Exception as exc:
            app_logger.error(f"Error processing interview step: {exc}")
            await self._send_message(
                user_id,
                {
                    "type": "error",
                    "message": "Error processing interview step",
                    "timestamp": datetime.now().isoformat(),
                },
            )

    async def _send_message(self, user_id: str, message: dict):
        if user_id not in self._active_interviews:
            return

        websocket = self._active_interviews[user_id]["websocket"]
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as exc:
            app_logger.error(f"Error sending message to user {user_id}: {exc}")

    async def end_interview(self, user_id: str):
        if user_id not in self._active_interviews:
            return

        interview_data = self._active_interviews[user_id]
        interview_data["is_active"] = False
        interview_data["completed_at"] = datetime.now()

        try:
            await interview_data["websocket"].close()
        except Exception as exc:
            app_logger.warning(f"Error closing websocket for user {user_id}: {exc}")

        del self._active_interviews[user_id]

        app_logger.info(f"Interview ended for user {user_id}")

    def disconnect_user(self, user_id: str):
        if user_id in self._active_interviews:
            print(f"User {user_id} disconnected")
            del self._active_interviews[user_id]

    def get_interview_status(self, user_id: str) -> dict | None:
        if user_id in self._active_interviews:
            interview_data = self._active_interviews[user_id]
            return {
                "user_id": user_id,
                "status": "active" if interview_data["is_active"] else "completed",
                "stage": interview_data["state"]["overall_stage"].value,
                "started_at": interview_data["started_at"],
                "message_count": len(interview_data["state"]["messages"]),
            }
        return None

    def get_user_interview(self, user_id: str) -> str | None:
        return user_id if user_id in self._active_interviews else None


interview_manager = InterviewConnectionManager(create_interview_workflow())
