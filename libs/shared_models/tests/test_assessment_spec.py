from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError
from shared_models.assessment import (
    AssessmentContext,
    AssessmentTemplateSnapshot,
    CvPolicy,
    RubricCriterion,
)
from shared_models.assessment.mocks import mock_assessment_context, mock_template

POLICIES = [CvPolicy.REQUIRED, CvPolicy.NONE]


def template_payload(**overrides: object) -> dict:
    return mock_template().model_dump(mode="json") | overrides


class TestTemplateValidation:
    def test_mock_template_is_valid(self) -> None:
        template = mock_template()

        assert template.schema_version == 2
        assert sum(focus.weight for focus in template.focus_areas) == 100

    def test_rejects_empty_focus_areas(self) -> None:
        with pytest.raises(ValidationError):
            AssessmentTemplateSnapshot.model_validate(template_payload(criteria=[]))

    def test_rejects_blank_skill(self) -> None:
        payload = template_payload()
        payload["criteria"][0]["skill"] = "   "

        with pytest.raises(ValidationError, match="must not be blank"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_rejects_duplicate_ids(self) -> None:
        payload = template_payload()
        payload["criteria"][1]["id"] = payload["criteria"][0]["id"]

        with pytest.raises(ValidationError, match="unique"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_rejects_weights_not_totalling_one_hundred(self) -> None:
        payload = template_payload()
        payload["criteria"][0]["weight"] = 30

        with pytest.raises(ValidationError, match="total 100"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_requires_at_least_one_required_focus(self) -> None:
        payload = template_payload()
        for focus in payload["criteria"]:
            focus["required"] = False

        with pytest.raises(ValidationError, match="must be required"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_rejects_custom_question_with_unknown_focus(self) -> None:
        payload = template_payload()
        payload["custom_questions"][0]["focus_id"] = "missing"

        with pytest.raises(ValidationError, match="unknown focus ids"):
            AssessmentTemplateSnapshot.model_validate(payload)

    @pytest.mark.parametrize(
        ("field", "value"),
        [("question_count", 0), ("question_count", 31), ("duration_minutes", 4)],
    )
    def test_rejects_out_of_range_limits(self, field: str, value: int) -> None:
        with pytest.raises(ValidationError):
            AssessmentTemplateSnapshot.model_validate(template_payload(**{field: value}))

    def test_rejects_min_evidence_above_max_questions(self) -> None:
        payload = template_payload()
        payload["criteria"][0]["min_evidence"] = 4
        payload["criteria"][0]["max_questions"] = 2

        with pytest.raises(ValidationError, match="min_evidence"):
            AssessmentTemplateSnapshot.model_validate(payload)


class TestV1Upcast:
    def v1_payload(self) -> dict:
        return {
            "mode": "technical",
            "question_count": 8,
            "duration_minutes": 30,
            "attempt_limit": 1,
            "criteria": [
                {"skill": "Python", "required": True, "weight": 60, "expected_level": "middle", "guidance": "Idioms"},
                {"skill": "Python", "required": False, "weight": 40, "expected_level": "junior"},
            ],
        }

    def test_v1_payload_upcasts_with_required_cv_policy(self) -> None:
        template = AssessmentTemplateSnapshot.model_validate(self.v1_payload())

        assert template.schema_version == 2
        assert template.cv_policy == CvPolicy.REQUIRED
        assert [focus.id for focus in template.criteria] == ["python", "python_2"]
        assert template.criteria[0].what_to_learn == "Idioms"
        assert template.criteria[1].what_to_learn == "Python"
        assert template.custom_questions == []

    def test_upcast_is_deterministic(self) -> None:
        first = AssessmentTemplateSnapshot.model_validate(self.v1_payload())
        second = AssessmentTemplateSnapshot.model_validate(self.v1_payload())

        assert first == second

    def test_python_v1_construction_with_rubric_criterion_instances(self) -> None:
        template = AssessmentTemplateSnapshot(
            mode="technical",
            question_count=5,
            duration_minutes=20,
            attempt_limit=1,
            criteria=[RubricCriterion(skill="SQL", required=True, weight=100, expected_level="senior")],
        )

        assert template.criteria[0].id == "sql"

    def test_explicit_v2_requires_ids(self) -> None:
        payload = self.v1_payload() | {"schema_version": 2}

        with pytest.raises(ValidationError):
            AssessmentTemplateSnapshot.model_validate(payload)


class TestAssessmentContext:
    def test_none_policy_allows_missing_cv_reference(self) -> None:
        context = mock_assessment_context(CvPolicy.NONE)

        assert context.cv_correlation_id is None
        assert context.cv_policy == CvPolicy.NONE

    def test_required_policy_needs_cv_reference(self) -> None:
        payload = mock_assessment_context(CvPolicy.REQUIRED).model_dump(mode="json")
        payload["cv_correlation_id"] = None

        with pytest.raises(ValidationError, match="cv_correlation_id"):
            AssessmentContext.model_validate(payload)

    def test_legacy_context_payload_is_still_accepted(self) -> None:
        context = AssessmentContext.model_validate(
            {
                "attempt_id": str(uuid4()),
                "organization_id": str(uuid4()),
                "vacancy_id": str(uuid4()),
                "invitation_id": str(uuid4()),
                "template_version": 1,
                "template": {
                    "mode": "technical",
                    "question_count": 5,
                    "duration_minutes": 20,
                    "attempt_limit": 1,
                    "criteria": [{"skill": "SQL", "required": True, "weight": 100, "expected_level": "senior"}],
                },
                "cv_correlation_id": str(uuid4()),
            }
        )

        assert context.cv_policy == CvPolicy.REQUIRED
        assert context.job_description is None

    def test_policy_must_match_template(self) -> None:
        payload = mock_assessment_context(CvPolicy.NONE).model_dump(mode="json")
        payload["cv_policy"] = "optional"

        with pytest.raises(ValidationError, match="must match"):
            AssessmentContext.model_validate(payload)


def _round_trip(model: BaseModel) -> BaseModel:
    return type(model).model_validate_json(model.model_dump_json())


@pytest.mark.parametrize("policy", POLICIES)
class TestJsonRoundTrip:
    def test_template(self, policy: CvPolicy) -> None:
        template = mock_template(policy)

        assert _round_trip(template) == template

    def test_context(self, policy: CvPolicy) -> None:
        context = mock_assessment_context(policy)

        assert _round_trip(context) == context
