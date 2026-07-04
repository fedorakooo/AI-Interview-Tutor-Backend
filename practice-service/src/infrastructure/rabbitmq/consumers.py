import asyncio
import json
import logging
import socket
import time

from aio_pika import IncomingMessage, connect_robust
from pydantic import ValidationError
from shared_models.messaging.retry_policy import MAX_RETRIES, MessageRetryPolicy, get_retry_count
from shared_models.practice.messaging import InterviewCompletedEvent, PracticePlanJobMessage
from src.config import settings
from src.domain.exceptions.practice_errors import PlanGenerationFailedError, PlanNotFoundError
from src.logger import app_logger


def wait_for_rabbitmq(
    host: str = settings.rabbitmq_settings.host,
    port: int = settings.rabbitmq_settings.port,
    timeout: float = settings.rabbitmq_settings.timeout,
) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                app_logger.info("RabbitMQ connection established")
                return
        except OSError:
            time.sleep(1.0)
            app_logger.info("Waiting for RabbitMQ connection")
    raise TimeoutError("RabbitMQ connection timed out")


class PracticeConsumers:
    def __init__(
        self,
        generate_plan_use_case,
        handle_interview_completed_use_case,
        retry_policy: MessageRetryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._generate_plan = generate_plan_use_case
        self._handle_interview = handle_interview_completed_use_case
        self._retry_policy = retry_policy or MessageRetryPolicy()
        self._logger = logger or app_logger
        self._connection = None
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._connection is not None:
            await self._connection.close()

    async def _run(self) -> None:
        wait_for_rabbitmq()
        connection = await connect_robust(settings.rabbitmq_settings.url)
        self._connection = connection
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=3)

            plan_dlq = await channel.declare_queue(
                settings.rabbitmq_settings.practice_plan_dlq_queue_name, durable=True
            )
            interview_dlq = await channel.declare_queue(
                settings.rabbitmq_settings.interview_completed_dlq_queue_name,
                durable=True,
            )
            plan_queue = await channel.declare_queue(settings.rabbitmq_settings.practice_plan_queue_name, durable=True)
            interview_queue = await channel.declare_queue(
                settings.rabbitmq_settings.interview_completed_queue_name,
                durable=True,
            )

            await plan_queue.consume(
                lambda message: self._on_plan_job(
                    message, channel, plan_dlq.name, settings.rabbitmq_settings.practice_plan_queue_name
                )
            )
            await interview_queue.consume(
                lambda message: self._on_interview_completed(
                    message,
                    channel,
                    interview_dlq.name,
                    settings.rabbitmq_settings.interview_completed_queue_name,
                )
            )

            self._logger.info("Practice consumers started")
            await self._stop_event.wait()

    async def _on_plan_job(self, message: IncomingMessage, channel, dlq_name: str, queue_name: str) -> None:
        retry_count = get_retry_count(message.headers)
        try:
            payload = json.loads(message.body.decode())
            job = PracticePlanJobMessage.model_validate(payload)
            await self._generate_plan.execute(job)
            await message.ack()
        except json.JSONDecodeError:
            await self._send_dlq(channel, dlq_name, message, queue_name, retry_count, "invalid_json")
            await message.ack()
        except ValidationError as exc:
            self._logger.error("Invalid plan job payload: %s", exc)
            await self._send_dlq(channel, dlq_name, message, queue_name, retry_count, "validation_error")
            await message.ack()
        except PlanNotFoundError as exc:
            self._logger.error("Plan not found: %s", exc)
            await self._send_dlq(channel, dlq_name, message, queue_name, retry_count, "plan_not_found")
            await message.ack()
        except PlanGenerationFailedError:
            await message.ack()
        except Exception:
            self._logger.exception("Plan job processing failed")
            if retry_count < MAX_RETRIES:
                await self._retry_policy.republish_with_retry(channel, message, retry_count + 1)
            else:
                await self._send_dlq(channel, dlq_name, message, queue_name, retry_count, "unknown_error")
            await message.ack()

    async def _on_interview_completed(
        self,
        message: IncomingMessage,
        channel,
        dlq_name: str,
        queue_name: str,
    ) -> None:
        retry_count = get_retry_count(message.headers)
        try:
            payload = json.loads(message.body.decode())
            event = InterviewCompletedEvent.model_validate(payload)
            await self._handle_interview.execute(event)
            await message.ack()
        except json.JSONDecodeError:
            await self._send_dlq(channel, dlq_name, message, queue_name, retry_count, "invalid_json")
            await message.ack()
        except ValidationError as exc:
            self._logger.error("Invalid interview completed payload: %s", exc)
            await self._send_dlq(channel, dlq_name, message, queue_name, retry_count, "validation_error")
            await message.ack()
        except Exception:
            self._logger.exception("Interview completed processing failed")
            if retry_count < MAX_RETRIES:
                await self._retry_policy.republish_with_retry(channel, message, retry_count + 1)
            else:
                await self._send_dlq(channel, dlq_name, message, queue_name, retry_count, "unknown_error")
            await message.ack()

    async def _send_dlq(self, channel, dlq_name, message, queue_name, retry_count, reason) -> None:
        await self._retry_policy.send_to_dlq(
            channel,
            dlq_name,
            message.body,
            reason=reason,
            original_queue=queue_name,
            retry_count=retry_count,
            logger=self._logger,
        )
