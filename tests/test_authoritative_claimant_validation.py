from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.infrastructure.dynamodb_active_claim_validator import ActiveClaimValidationResult
from latch.infrastructure.retirement_admission_coordinator import (
    RetirementAdmissionCoordinator,
)


class FakeClaimValidator:
    def __init__(self, db_owner: str) -> None:
        self.db_owner = db_owner
        self.validate_called = False

    def get_authoritative_owner(self, identifier: str) -> str | None:
        return self.db_owner

    def validate(self, claim: RetirementEvaluationClaim) -> ActiveClaimValidationResult:
        self.validate_called = True
        return ActiveClaimValidationResult.VALID_ACTIVE_CLAIM


@pytest.fixture
def environment() -> Environment:
    return Environment(
        identifier="env-123",
        created_at=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
        ttl_expires_at=datetime(2026, 7, 23, 10, 0, tzinfo=UTC),
        owner="real-owner",
        resource_target_arns=[
            "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
        ],
    )


@pytest.fixture
def claim(environment: Environment) -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(environment, datetime(2026, 7, 23, 10, 0, tzinfo=UTC))


def test_claimant_mismatch_against_database_owner_raises_value_error(
    claim: RetirementEvaluationClaim,
) -> None:
    # Authoritative owner in DB is "real-owner"
    validator = FakeClaimValidator("real-owner")
    coordinator = RetirementAdmissionCoordinator(
        active_claim_validator=validator,  # type: ignore[arg-type]
        evidence_collection=Mock(),
        active_registration_adapter=Mock(),
    )

    # Claimant matches the incoming payload ("false-owner"), but mismatches DB owner ("real-owner")
    msg = "Claimant identity does not match authoritative registered owner"
    with pytest.raises(ValueError, match=msg):
        coordinator.evaluate(claim, claimant_identity="false-owner")

    # The evaluator/validator must NOT be called for evaluation
    assert not validator.validate_called


def test_exact_claimant_match_against_db_owner_proceeds(
    claim: RetirementEvaluationClaim,
) -> None:
    validator = FakeClaimValidator("real-owner")
    coordinator = RetirementAdmissionCoordinator(
        active_claim_validator=validator,  # type: ignore[arg-type]
        evidence_collection=Mock(),
        active_registration_adapter=Mock(),
    )

    # Exact claimant match proceeds past claimant validation to evaluator delegation
    try:
        coordinator.evaluate(claim, claimant_identity="real-owner")
    except Exception as e:
        # It may fail downstream because we pass mocked dependencies,
        # but it must not be a claimant mismatch error
        assert "Claimant identity does not match" not in str(e)

    assert validator.validate_called


def test_case_mismatch_rejected(claim: RetirementEvaluationClaim) -> None:
    validator = FakeClaimValidator("real-owner")
    coordinator = RetirementAdmissionCoordinator(
        active_claim_validator=validator,  # type: ignore[arg-type]
        evidence_collection=Mock(),
        active_registration_adapter=Mock(),
    )

    # Case-only mismatch "REAL-OWNER" != "real-owner"
    msg = "Claimant identity does not match authoritative registered owner"
    with pytest.raises(ValueError, match=msg):
        coordinator.evaluate(claim, claimant_identity="REAL-OWNER")


def test_whitespace_mismatch_rejected(claim: RetirementEvaluationClaim) -> None:
    validator = FakeClaimValidator("real-owner")
    coordinator = RetirementAdmissionCoordinator(
        active_claim_validator=validator,  # type: ignore[arg-type]
        evidence_collection=Mock(),
        active_registration_adapter=Mock(),
    )

    # Whitespace mismatch (no trimming/normalization)
    msg = "Claimant identity does not match authoritative registered owner"
    with pytest.raises(ValueError, match=msg):
        coordinator.evaluate(claim, claimant_identity=" real-owner ")
