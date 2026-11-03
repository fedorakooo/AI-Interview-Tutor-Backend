from src.domain.events.assessment_completed import AssessmentCompleted
from src.domain.interfaces.messaging.assessment_completed_publisher import IAssessmentCompletedPublisher


class RecordingPublisher(IAssessmentCompletedPublisher):
    def __init__(self) -> None:
        self.events: list[AssessmentCompleted] = []
        self.fail = False

    async def publish(self, event: AssessmentCompleted) -> None:
        if self.fail:
            raise ConnectionError("broker down")
        self.events.append(event)
