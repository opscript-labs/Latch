from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from latch.domain.admission import AdmissionVerdict
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.execution import RetirementExecutionAuthorization
from latch.infrastructure.dynamodb_active_claim_validator import (
    ActiveClaimValidationResult,
    DynamoDBActiveClaimValidator,
)
from latch.infrastructure.dynamodb_active_registration_adapter import (
    canonical_registration_timestamp,
    immutable_registration_fingerprint,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"


def make_environment() -> Environment:
    return Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=[TARGET],
    )


def make_claim() -> RetirementEvaluationClaim:
    with patch(
        "latch.domain.environment.retirement_evaluation_claim.uuid.uuid4",
        return_value="claim-token",
    ):
        return RetirementEvaluationClaim(make_environment(), TTL_EXPIRES_AT)


def item_for_claim(claim: RetirementEvaluationClaim) -> dict[str, object]:
    return {
        "identifier": {"S": claim.environment.identifier},
        "registration_fingerprint": {"S": immutable_registration_fingerprint(claim.environment)},
        "evaluation_claim_token": {"S": claim.claim_token},
        "evaluation_claim_time": {"S": canonical_registration_timestamp(claim.claim_time)},
    }


def validate_item(item: dict[str, object] | None) -> tuple[ActiveClaimValidationResult, Mock]:
    client = Mock()
    client.get_item.return_value = {} if item is None else {"Item": item}
    result = DynamoDBActiveClaimValidator(client, "active-environments").validate(make_claim())
    return result, client


def test_active_claim_validation_has_exact_closed_vocabulary() -> None:
    assert list(ActiveClaimValidationResult) == [
        ActiveClaimValidationResult.VALID_ACTIVE_CLAIM,
        ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM,
    ]


def test_exact_active_registration_and_claim_returns_valid_active_claim() -> None:
    claim = make_claim()
    client = Mock()
    client.get_item.return_value = {"Item": item_for_claim(claim)}

    result = DynamoDBActiveClaimValidator(client, "active-environments").validate(claim)

    assert result is ActiveClaimValidationResult.VALID_ACTIVE_CLAIM


@pytest.mark.parametrize(
    "item_update",
    [
        {"registration_fingerprint": {"S": "stale"}},
        {"evaluation_claim_token": {"S": "other-token"}},
        {"evaluation_claim_time": {"S": "2026-07-23T10:00:00.000001Z"}},
        {"identifier": {"S": "env-456"}},
        {"evaluation_claim_token": {"S": ""}},
        {"evaluation_claim_time": {"N": "1"}},
    ],
)
def test_mismatch_or_malformed_claim_state_returns_invalid(
    item_update: dict[str, object],
) -> None:
    claim = make_claim()
    item = item_for_claim(claim)
    item.update(item_update)

    result, _ = validate_item(item)

    assert result is ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM


def test_missing_active_registration_returns_invalid() -> None:
    result, _ = validate_item(None)

    assert result is ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM


@pytest.mark.parametrize(
    "missing_name",
    [
        "identifier",
        "registration_fingerprint",
        "evaluation_claim_token",
        "evaluation_claim_time",
    ],
)
def test_incomplete_active_claim_state_returns_invalid(missing_name: str) -> None:
    item = item_for_claim(make_claim())
    item.pop(missing_name)

    result, _ = validate_item(item)

    assert result is ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM


def test_direct_strongly_consistent_read_is_used() -> None:
    claim = make_claim()
    client = Mock()
    client.get_item.return_value = {"Item": item_for_claim(claim)}

    DynamoDBActiveClaimValidator(client, "active-environments").validate(claim)

    client.get_item.assert_called_once_with(
        TableName="active-environments",
        Key={"identifier": {"S": "env-123"}},
        ConsistentRead=True,
    )


def test_validation_is_read_only_and_does_not_use_scan_query_or_mutation() -> None:
    result, client = validate_item(item_for_claim(make_claim()))

    assert result is ActiveClaimValidationResult.VALID_ACTIVE_CLAIM
    client.scan.assert_not_called()
    client.query.assert_not_called()
    client.put_item.assert_not_called()
    client.update_item.assert_not_called()
    client.delete_item.assert_not_called()
    client.transact_write_items.assert_not_called()


def test_validation_does_not_create_verdict_or_execution_artifact() -> None:
    result, _ = validate_item(item_for_claim(make_claim()))

    assert isinstance(result, ActiveClaimValidationResult)
    assert not isinstance(result, AdmissionVerdict)
    assert not isinstance(result, RetirementExecutionAuthorization)


def test_blank_table_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="table_name"):
        DynamoDBActiveClaimValidator(Mock(), " ")
