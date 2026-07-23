from datetime import UTC, datetime
from typing import Any

import pytest

from latch.application.retirement_admission_adapter import RetirementAdmissionAdapter
from latch.domain.admission import AdmissionVerdict, RetirementAdmissionVerdict
from latch.domain.environment import RetirementEvaluationClaim


class MockEvaluator:
    def __init__(self, verdict: RetirementAdmissionVerdict | None = None) -> None:
        self.verdict = verdict
        self.calls: list[RetirementEvaluationClaim] = []

    def evaluate(self, claim: RetirementEvaluationClaim) -> RetirementAdmissionVerdict | None:
        self.calls.append(claim)
        return self.verdict


@pytest.fixture
def valid_payload() -> dict[str, Any]:
    return {
        "version": "1",
        "environment": {
            "identifier": "env-123",
            "created_at": "2026-07-23T08:00:00Z",
            "ttl_expires_at": "2026-07-23T10:00:00Z",
            "owner": "team-platform",
            "resource_target_arns": [
                "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
            ],
        },
        "claim_time": "2026-07-23T10:00:00Z",
    }


def make_mock_verdict(verdict_enum: AdmissionVerdict) -> Any:
    # We construct a stub verdict object with a mocked lock_participation
    # because the domain verdict has a post_init validation that requires
    # lock_participation to be a RetirementLockParticipation
    from unittest.mock import Mock
    mock_verdict = Mock(spec=RetirementAdmissionVerdict)
    mock_verdict.verdict = verdict_enum
    return mock_verdict


def test_valid_request_constructs_exact_claim_and_calls_evaluator_once(
    valid_payload: dict[str, Any]
) -> None:
    mock_verdict = make_mock_verdict(AdmissionVerdict.SAFE)
    evaluator = MockEvaluator(mock_verdict)
    adapter = RetirementAdmissionAdapter(evaluator)

    result = adapter.handle(valid_payload)

    assert len(evaluator.calls) == 1
    claim = evaluator.calls[0]
    assert isinstance(claim, RetirementEvaluationClaim)
    assert claim.environment.identifier == "env-123"
    assert claim.environment.owner == "team-platform"
    assert claim.environment.created_at == datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
    assert claim.environment.ttl_expires_at == datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    assert claim.environment.resource_target_arns == {
        "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
    }
    assert claim.claim_time == datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    assert result["verdict"] == "safe"
    assert "claim_token" in result


@pytest.mark.parametrize(
    "verdict_enum,expected_str",
    [
        (AdmissionVerdict.SAFE, "safe"),
        (AdmissionVerdict.UNSAFE, "unsafe"),
        (AdmissionVerdict.INSUFFICIENT, "insufficient"),
    ],
)
def test_verdict_values_are_serialized_correctly(
    valid_payload: dict[str, Any], verdict_enum: AdmissionVerdict, expected_str: str
) -> None:
    mock_verdict = make_mock_verdict(verdict_enum)
    evaluator = MockEvaluator(mock_verdict)
    adapter = RetirementAdmissionAdapter(evaluator)

    result = adapter.handle(valid_payload)
    assert result["verdict"] == expected_str


def test_evaluator_returning_none_serializes_verdict_as_none(
    valid_payload: dict[str, Any]
) -> None:
    evaluator = MockEvaluator(None)
    adapter = RetirementAdmissionAdapter(evaluator)

    result = adapter.handle(valid_payload)
    assert result["verdict"] is None


@pytest.mark.parametrize(
    "missing_field",
    [
        "version",
        "environment",
        "claim_time",
    ],
)
def test_missing_root_fields_fail_closed(
    valid_payload: dict[str, Any], missing_field: str
) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    del valid_payload[missing_field]

    with pytest.raises(ValueError):
        adapter.handle(valid_payload)

    assert len(evaluator.calls) == 0


@pytest.mark.parametrize(
    "missing_env_field",
    [
        "identifier",
        "created_at",
        "ttl_expires_at",
        "owner",
        "resource_target_arns",
    ],
)
def test_missing_environment_fields_fail_closed(
    valid_payload: dict[str, Any], missing_env_field: str
) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    del valid_payload["environment"][missing_env_field]

    with pytest.raises(ValueError):
        adapter.handle(valid_payload)

    assert len(evaluator.calls) == 0


@pytest.mark.parametrize(
    "invalid_key,invalid_value",
    [
        ("version", "2"),
        ("claim_time", "not-a-datetime"),
        ("claim_time", "2026-07-23T10:00:00"),  # missing timezone
    ],
)
def test_invalid_root_field_values_fail_closed(
    valid_payload: dict[str, Any], invalid_key: str, invalid_value: Any
) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    valid_payload[invalid_key] = invalid_value

    with pytest.raises(ValueError):
        adapter.handle(valid_payload)

    assert len(evaluator.calls) == 0


@pytest.mark.parametrize(
    "invalid_key,invalid_value",
    [
        ("created_at", "not-a-datetime"),
        ("created_at", "2026-07-23T08:00:00"),  # missing timezone
        ("resource_target_arns", []),  # empty targets
        ("resource_target_arns", ["not-an-arn"]),  # invalid ARN
    ],
)
def test_invalid_env_field_values_fail_closed(
    valid_payload: dict[str, Any], invalid_key: str, invalid_value: Any
) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    valid_payload["environment"][invalid_key] = invalid_value

    with pytest.raises(ValueError):
        adapter.handle(valid_payload)

    assert len(evaluator.calls) == 0


def test_extra_root_fields_are_strictly_rejected(valid_payload: dict[str, Any]) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    valid_payload["extra_field"] = "value"

    with pytest.raises(ValueError):
        adapter.handle(valid_payload)

    assert len(evaluator.calls) == 0


def test_extra_environment_fields_are_strictly_rejected(valid_payload: dict[str, Any]) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    valid_payload["environment"]["extra_field"] = "value"

    with pytest.raises(ValueError):
        adapter.handle(valid_payload)

    assert len(evaluator.calls) == 0
