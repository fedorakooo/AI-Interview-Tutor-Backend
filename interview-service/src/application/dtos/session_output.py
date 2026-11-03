from shared_models.assessment import InterviewerMessage, SessionCompleted

from src.application.dtos.message_delta import MessageDelta

SessionOutput = MessageDelta | InterviewerMessage | SessionCompleted
