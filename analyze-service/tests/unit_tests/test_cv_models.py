from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from shared_models.cv.cv_data import CVData
from shared_models.cv.cv_items import SkillItem
from shared_models.messaging.common import AnalysisStatus, ExtractionMetadata
from shared_models.messaging.cv_analysis import (
    CVAnalysisDocument,
    CVAnalysisJobMessage,
    CVAnalysisResultMessage,
)

class TestCVAnalysisJobMessage:
    def test_accepts_legacy_url_field(self) -> None:
        message = CVAnalysisJobMessage.model_validate(
            {
                "user_id": str(uuid4()),
                "url": "cvs/user/resume.pdf",
                "published_at": "2026-07-03T10:00:00+00:00",
            }
        )

        assert message.s3_object_key == "cvs/user/resume.pdf"
        assert message.correlation_id is not None

    def test_rejects_missing_s3_object_key(self) -> None:
        with pytest.raises(ValidationError):
            CVAnalysisJobMessage.model_validate(
                {
                    "correlation_id": str(uuid4()),
                    "user_id": str(uuid4()),
                    "published_at": datetime.now(UTC).isoformat(),
                }
            )


class TestCVAnalysisResultMessage:
    def test_serializes_to_json(self) -> None:
        message = CVAnalysisResultMessage(
            correlation_id=uuid4(),
            user_id=uuid4(),
            s3_object_key="cvs/user/resume.pdf",
            status=AnalysisStatus.COMPLETED,
            mongo_document_id="abc123",
            published_at=datetime.now(UTC),
        )

        payload = message.model_dump(mode="json")
        assert payload["status"] == "completed"
        assert payload["mongo_document_id"] == "abc123"


class TestCVData:
    def test_coerces_legacy_string_skills(self) -> None:
        cv_data = CVData.model_validate(
            {
                "user_name": "Jane Doe",
                "skills": ["Python", "postgres", "K8S"],
            }
        )

        assert [skill.name for skill in cv_data.skills] == ["Python", "postgres", "K8S"]

    def test_accepts_structured_skills(self) -> None:
        cv_data = CVData.model_validate(
            {
                "user_name": "Jane Doe",
                "skills": [
                    {"name": "LangChain", "category": "tool"},
                    {"name": "FastAPI", "category": "framework"},
                ],
            }
        )

        assert cv_data.skills == [
            SkillItem(name="LangChain", category="tool"),
            SkillItem(name="FastAPI", category="framework"),
        ]


class TestCVAnalysisDocument:
    def test_to_mongo_dict_flattens_cv_and_metadata(self) -> None:
        document = CVAnalysisDocument(
            correlation_id=uuid4(),
            user_id=uuid4(),
            s3_object_key="cvs/user/resume.pdf",
            published_at=datetime.now(UTC),
            analyzed_at=datetime.now(UTC),
            extraction_metadata=ExtractionMetadata(
                method="docling",
                page_count=2,
                char_count=100,
                duration_ms=500,
            ),
            cv=CVData(user_name="Jane Doe", skills=[SkillItem(name="Python")]),
        )

        mongo_document = document.to_mongo_dict()

        assert mongo_document["user_name"] == "Jane Doe"
        assert mongo_document["s3_object_key"] == "cvs/user/resume.pdf"
        assert mongo_document["source_url"] == "cvs/user/resume.pdf"
        assert mongo_document["skills"][0]["name"] == "Python"
        assert mongo_document["extraction_metadata"]["method"] == "docling"
