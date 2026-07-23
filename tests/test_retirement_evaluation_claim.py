from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from latch.domain.environment import Environment, RetirementEvaluationClaim

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
CLAIM_TIME = TTL_EXPIRES_AT
TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"


def make_environment(identifier: str = "env-123") -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=[TARGET],
    )


def test_successful_claim_is_immutable_with_generated_token_and_utc_time() -> None:
    claim_time = datetime(
        2026,
        7,
        23,
        15,
        30,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    claim = RetirementEvaluationClaim(make_environment(), claim_time)

    assert claim.claim_token.strip()
    assert claim.claim_time == datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    with pytest.raises(FrozenInstanceError):
        claim.claim_time = CLAIM_TIME


def test_token_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        RetirementEvaluationClaim(
            make_environment(),
            CLAIM_TIME,
            claim_token="caller-token",
        )


def test_naive_claim_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="claim_time"):
        RetirementEvaluationClaim(make_environment(), datetime(2026, 7, 23, 10, 0))


def test_claim_identity_excludes_claim_time_and_includes_environment_and_token() -> None:
    environment = make_environment()
    later_claim_time = CLAIM_TIME + timedelta(minutes=5)

    with patch(
        "latch.domain.environment.retirement_evaluation_claim.uuid.uuid4",
        return_value="same-token",
    ):
        first = RetirementEvaluationClaim(environment, CLAIM_TIME)
        second = RetirementEvaluationClaim(environment, later_claim_time)
        changed_environment = RetirementEvaluationClaim(
            make_environment(identifier="env-456"),
            CLAIM_TIME,
        )

    with patch(
        "latch.domain.environment.retirement_evaluation_claim.uuid.uuid4",
        return_value="different-token",
    ):
        changed_token = RetirementEvaluationClaim(environment, CLAIM_TIME)

    assert first == second
    assert hash(first) == hash(second)
    assert first != changed_environment
    assert first != changed_token
