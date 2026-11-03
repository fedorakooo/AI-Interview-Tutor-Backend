from src.application.dtos.message_completed import MessageCompleted
from src.application.dtos.message_delta import MessageDelta
from src.application.dtos.session_finished import SessionFinished

SessionOutput = MessageDelta | MessageCompleted | SessionFinished
