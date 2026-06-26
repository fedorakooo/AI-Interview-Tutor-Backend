import asyncio
from datetime import datetime
from typing import Any

from src.agent.services.cv_analyzer import ICVAnalyzer
from src.domain.adapters.outbound.mongo import IMongoRepository
from src.domain.adapters.outbound.pdf_loader import IPDFLoader
from src.domain.adapters.outbound.rabbitmq_producer import IRabbitMQProducer
from src.domain.adapters.outbound.s3 import IS3Client
from src.domain.models.cv_analyze_messages import CVInitialAnalysisMessage, CVResultAnalysisMessage


class CVAnalyzeUseCase:
    def __init__(
        self,
        s3_client: IS3Client,
        cv_analyzer: ICVAnalyzer,
        pdf_loader: IPDFLoader,
        mongo_repository: IMongoRepository,
        rabbitmq_producer: IRabbitMQProducer,
    ):
        self.s3_client = s3_client
        self.cv_analyzer = cv_analyzer
        self.pdf_loader = pdf_loader
        self.mongo_repository = mongo_repository
        self.rabbitmq_producer = rabbitmq_producer

    async def __call__(self, event_data: dict[str, Any]) -> None:
        received_message = CVInitialAnalysisMessage(**event_data)

        pdf_bytes = await self.s3_client.get_file(received_message.url)

        extracted_text: str = await asyncio.to_thread(self.pdf_loader.load, pdf_bytes)

        analysis_result = await self.cv_analyzer.analyze(content=extracted_text)

        analysis_document = {
            **analysis_result.model_dump(mode="json"),
            "user_id": str(received_message.user_id),
            "source_url": received_message.url,
            "published_at": received_message.published_at.isoformat(),
        }
        await self.mongo_repository.insert_one(analysis_document)

        message_to_sent = CVResultAnalysisMessage(
            user_id=received_message.user_id,
            subject=analysis_result.model_dump_json(indent=2),
            url=received_message.url,
            body="CV Analyze Result",
            published_at=datetime.now(),
        )

        await self.rabbitmq_producer.send_message(message_to_sent.model_dump_json())
