from datetime import UTC, datetime
from uuid import uuid4

import aio_pika
from src.domain.events.assessment_completed import AssessmentCompleted
from src.infrastructure.rabbitmq.assessment_completed_publisher import AssessmentCompletedPublisher


async def test_publisher_reuses_one_connection_and_channel(monkeypatch) -> None:
    opened = []

    class Exchange:
        published = 0

        async def publish(self, message, routing_key):
            Exchange.published += 1

    class Channel:
        is_closed = False
        default_exchange = Exchange()

        async def declare_queue(self, name, durable):
            return None

    class Connection:
        is_closed = False

        async def channel(self):
            return Channel()

        async def close(self):
            self.is_closed = True

    async def connect(url):
        opened.append(url)
        return Connection()

    monkeypatch.setattr(aio_pika, "connect_robust", connect)
    publisher = AssessmentCompletedPublisher("amqp://x", "assessment-completed")
    event = AssessmentCompleted(
        event_id=uuid4(),
        occurred_at=datetime(2026, 11, 3, tzinfo=UTC),
        correlation_id=uuid4(),
        organization_id=uuid4(),
        vacancy_id=uuid4(),
        invitation_id=uuid4(),
        attempt_id=uuid4(),
        session_id="s",
        report_reference="interview-report:s",
    )

    await publisher.publish(event)
    await publisher.publish(event)
    await publisher.close()

    assert opened == ["amqp://x"] and Exchange.published == 2
