from datetime import UTC, datetime

import pytest
from botocore.exceptions import ClientError

from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.execution import EC2DestructionConfirmation, EC2InstanceLifecycleState
from latch.infrastructure.claim_fenced_confirmed_deregistration import (
    ClaimFencedConfirmedDeregistration,
)
from latch.infrastructure.dynamodb_active_claim_validator import ActiveClaimValidationResult

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"


def make_environment(
    *,
    identifier: str = "env-123",
) -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns={TARGET},
    )


def make_claim(environment: Environment | None = None) -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(environment or make_environment(), TTL_EXPIRES_AT)


def confirmed(environment: Environment) -> EC2DestructionConfirmation:
    return EC2DestructionConfirmation(
        environment,
        [EC2InstanceLifecycleState(TARGET, "terminated")],
    )


def not_confirmed(environment: Environment) -> EC2DestructionConfirmation:
    return EC2DestructionConfirmation(environment, [])


def transaction_failure() -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "transaction cancelled",
            },
            "CancellationReasons": [{"Code": "ConditionalCheckFailed"}],
        },
        "TransactWriteItems",
    )


class ActiveClaimValidatorStub:
    def __init__(self, result: ActiveClaimValidationResult) -> None:
        self.result = result
        self.calls: list[RetirementEvaluationClaim] = []

    def validate(
        self,
        claim: RetirementEvaluationClaim,
    ) -> ActiveClaimValidationResult:
        self.calls.append(claim)
        return self.result


class ActiveRegistrationAdapterStub:
    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[RetirementEvaluationClaim, EC2DestructionConfirmation]] = []

    def deregister_confirmed(
        self,
        claim: RetirementEvaluationClaim,
        confirmation: EC2DestructionConfirmation,
    ) -> None:
        self.calls.append((claim, confirmation))
        if self.failure is not None:
            raise self.failure


def make_coordinator(
    validator: ActiveClaimValidatorStub,
    adapter: ActiveRegistrationAdapterStub,
) -> ClaimFencedConfirmedDeregistration:
    return ClaimFencedConfirmedDeregistration(
        active_claim_validator=validator,
        active_registration_adapter=adapter,
    )


def test_confirmed_destruction_with_valid_claim_invokes_deregistration_once() -> None:
    claim = make_claim()
    confirmation = confirmed(claim.environment)
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = ActiveRegistrationAdapterStub()

    result = make_coordinator(validator, adapter).deregister(claim, confirmation)

    assert result is None
    assert validator.calls == [claim]
    assert adapter.calls == [(claim, confirmation)]


def test_not_confirmed_destruction_skips_validator_and_mutation() -> None:
    claim = make_claim()
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = ActiveRegistrationAdapterStub()

    result = make_coordinator(validator, adapter).deregister(
        claim,
        not_confirmed(claim.environment),
    )

    assert result is None
    assert validator.calls == []
    assert adapter.calls == []


def test_confirmation_environment_mismatch_skips_validator_and_mutation() -> None:
    claim = make_claim()
    other_environment = make_environment(identifier="env-456")
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = ActiveRegistrationAdapterStub()

    result = make_coordinator(validator, adapter).deregister(
        claim,
        confirmed(other_environment),
    )

    assert result is None
    assert validator.calls == []
    assert adapter.calls == []


def test_invalid_final_claim_skips_dynamodb_mutation() -> None:
    claim = make_claim()
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM)
    adapter = ActiveRegistrationAdapterStub()

    result = make_coordinator(validator, adapter).deregister(
        claim,
        confirmed(claim.environment),
    )

    assert result is None
    assert validator.calls == [claim]
    assert adapter.calls == []


def test_failed_transaction_condition_propagates_unchanged_and_does_not_retry() -> None:
    claim = make_claim()
    error = transaction_failure()
    adapter = ActiveRegistrationAdapterStub(failure=error)

    with pytest.raises(ClientError) as raised:
        make_coordinator(
            ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
            adapter,
        ).deregister(claim, confirmed(claim.environment))

    assert raised.value is error
    assert len(adapter.calls) == 1


def test_inputs_remain_unchanged() -> None:
    claim = make_claim()
    environment = claim.environment
    confirmation = confirmed(environment)
    reported_states = confirmation.reported_states

    make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        ActiveRegistrationAdapterStub(),
    ).deregister(claim, confirmation)

    assert claim.environment == environment
    assert confirmation.environment == environment
    assert confirmation.reported_states == reported_states
