from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

import pytest

from latch.application.retirement_admission_adapter import RetirementAdmissionAdapter
from latch.domain.admission import (
    AdmissionVerdict,
    RetirementAdmissionRequest,
    RetirementAdmissionRequested,
    RetirementAdmissionVerdict,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim


class MockEvaluator:
    def __init__(self, verdict: RetirementAdmissionVerdict | None = None) -> None:
        self.verdict = verdict
        self.calls: list[tuple[RetirementEvaluationClaim, str]] = []

    def evaluate(
        self,
        claim: RetirementEvaluationClaim,
        claimant_identity: str,
    ) -> RetirementAdmissionVerdict | None:
        self.calls.append((claim, claimant_identity))
        return self.verdict


@pytest.fixture
def valid_payload() -> dict[str, Any]:
    return {
        "product_event_type": "RETIREMENT_ADMISSION_REQUESTED",
        "version": "1",
        "claim_time": "2026-07-23T10:00:00Z",
        "request": {
            "environment_identity": {
                "identifier": "env-123",
                "created_at": "2026-07-23T08:00:00Z",
                "ttl_expires_at": "2026-07-23T10:00:00Z",
                "owner": "team-platform",
                "resource_target_arns": [
                    "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
                ],
            },
            "retirement_claim_identity": "claim-token-123",
            "claimant_identity": "team-platform",
        },
    }


def make_mock_verdict(verdict_enum: AdmissionVerdict) -> Any:
    mock_verdict = Mock(spec=RetirementAdmissionVerdict)
    mock_verdict.verdict = verdict_enum
    return mock_verdict


def test_valid_request_constructs_exact_claim_and_calls_evaluator_once(
    valid_payload: dict[str, Any]
) -> None:
    mock_verdict = make_mock_verdict(AdmissionVerdict.SAFE)
    evaluator = MockEvaluator(mock_verdict)
    adapter = RetirementAdmissionAdapter(evaluator)

    result = adapter.handle(valid_payload, producer_authority="RetirementAdmissionRequestProducer")

    assert len(evaluator.calls) == 1
    claim, claimant = evaluator.calls[0]
    assert isinstance(claim, RetirementEvaluationClaim)
    assert claim.environment.identifier == "env-123"
    assert claim.environment.owner == "team-platform"
    assert claimant == "team-platform"
    assert result["verdict"] == "safe"
    assert result["claim_token"] == "claim-token-123"


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

    result = adapter.handle(valid_payload, producer_authority="RetirementAdmissionRequestProducer")

    assert result["verdict"] == expected_str
    assert result["claim_token"] == "claim-token-123"


def test_coordinator_none_result_mapped_to_omitted_verdict(valid_payload: dict[str, Any]) -> None:
    evaluator = MockEvaluator(None)
    adapter = RetirementAdmissionAdapter(evaluator)

    result = adapter.handle(valid_payload, producer_authority="RetirementAdmissionRequestProducer")

    assert "verdict" not in result
    assert result["claim_token"] == "claim-token-123"


def test_unauthorized_direct_invocation_rejected(valid_payload: dict[str, Any]) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)

    with pytest.raises(ValueError, match="Unauthorized producer attribution"):
        adapter.handle(valid_payload)  # no producer authority passed


def test_incorrect_producer_authority_rejected(valid_payload: dict[str, Any]) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)

    with pytest.raises(ValueError, match="Unauthorized producer attribution"):
        adapter.handle(valid_payload, producer_authority="UntrustedProducer")


def test_payload_supplied_producer_does_not_authorize(valid_payload: dict[str, Any]) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    valid_payload["producer"] = "RetirementAdmissionRequestProducer"

    with pytest.raises(ValueError):
        adapter.handle(valid_payload, producer_authority="UntrustedProducer")


def test_missing_root_fields_fail_closed_without_calling_evaluator(
    valid_payload: dict[str, Any]
) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    del valid_payload["request"]

    with pytest.raises(ValueError):
        adapter.handle(valid_payload, producer_authority="RetirementAdmissionRequestProducer")

    assert len(evaluator.calls) == 0


def test_claimant_mismatch_fails_closed(valid_payload: dict[str, Any]) -> None:
    evaluator = MockEvaluator()
    adapter = RetirementAdmissionAdapter(evaluator)
    valid_payload["request"]["claimant_identity"] = "different-owner"

    with pytest.raises(ValueError):
        adapter.handle(valid_payload, producer_authority="RetirementAdmissionRequestProducer")

    assert len(evaluator.calls) == 0


def test_product_models_behavior() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
        ttl_expires_at=datetime(2026, 7, 23, 10, 0, tzinfo=UTC),
        owner="team-platform",
        resource_target_arns=[
            "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
        ],
    )
    request = RetirementAdmissionRequest(
        environment_identity=environment,
        retirement_claim_identity="claim-token",
        claimant_identity="team-platform",
    )
    event = RetirementAdmissionRequested(request=request)

    assert request.environment_identity == environment
    assert request.retirement_claim_identity == "claim-token"
    assert request.claimant_identity == "team-platform"
    assert event.product_event_type == "RETIREMENT_ADMISSION_REQUESTED"
    assert event.request == request

    with pytest.raises(ValueError):
        # Mismatch
        RetirementAdmissionRequest(
            environment_identity=environment,
            retirement_claim_identity="claim-token",
            claimant_identity="other-owner",
        )
