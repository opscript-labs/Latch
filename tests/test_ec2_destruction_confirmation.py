from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.environment import Environment
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
    EC2InstanceLifecycleState,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"
OUTSIDE_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-11111111111111111"


def make_environment(
    *,
    identifier: str = "env-123",
    resource_target_arns: frozenset[str] | None = None,
) -> Environment:
    if resource_target_arns is None:
        resource_target_arns = frozenset({FIRST_TARGET})

    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=resource_target_arns,
    )


def state(target_arn: str, lifecycle_state: str) -> EC2InstanceLifecycleState:
    return EC2InstanceLifecycleState(
        target_arn=target_arn,
        lifecycle_state=lifecycle_state,
    )


def test_ec2_destruction_confirmation_has_exact_closed_vocabulary() -> None:
    assert list(EC2DestructionConfirmationOutcome) == [
        EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED,
        EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED,
    ]


def test_all_registered_targets_reported_terminated_is_confirmed() -> None:
    confirmation = EC2DestructionConfirmation(
        environment=make_environment(),
        reported_states=[state(FIRST_TARGET, "terminated")],
    )

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED


def test_one_missing_registered_target_is_not_confirmed() -> None:
    confirmation = EC2DestructionConfirmation(
        environment=make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET})),
        reported_states=[state(FIRST_TARGET, "terminated")],
    )

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_one_non_terminated_state_is_not_confirmed() -> None:
    confirmation = EC2DestructionConfirmation(
        environment=make_environment(),
        reported_states=[state(FIRST_TARGET, "stopped")],
    )

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_multiple_registered_targets_reported_terminated_are_confirmed() -> None:
    confirmation = EC2DestructionConfirmation(
        environment=make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET})),
        reported_states=[
            state(FIRST_TARGET, "terminated"),
            state(SECOND_TARGET, "terminated"),
        ],
    )

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED


def test_outside_registered_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="registered"):
        EC2DestructionConfirmation(
            environment=make_environment(),
            reported_states=[state(OUTSIDE_TARGET, "terminated")],
        )


def test_duplicate_state_for_one_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="one state per target"):
        EC2DestructionConfirmation(
            environment=make_environment(),
            reported_states=[
                state(FIRST_TARGET, "terminated"),
                state(FIRST_TARGET, "terminated"),
            ],
        )


@pytest.mark.parametrize("lifecycle_state", ["", " "])
def test_empty_or_whitespace_lifecycle_state_is_rejected(lifecycle_state: str) -> None:
    with pytest.raises(ValueError, match="lifecycle_state"):
        state(FIRST_TARGET, lifecycle_state)


def test_reported_state_set_order_does_not_affect_equality_or_hashing() -> None:
    environment = make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    first = EC2DestructionConfirmation(
        environment=environment,
        reported_states=[
            state(FIRST_TARGET, "terminated"),
            state(SECOND_TARGET, "terminated"),
        ],
    )
    second = EC2DestructionConfirmation(
        environment=environment,
        reported_states=[
            state(SECOND_TARGET, "terminated"),
            state(FIRST_TARGET, "terminated"),
        ],
    )

    assert first == second
    assert hash(first) == hash(second)


def test_changed_environment_changes_confirmation_identity() -> None:
    assert EC2DestructionConfirmation(
        environment=make_environment(),
        reported_states=[state(FIRST_TARGET, "terminated")],
    ) != EC2DestructionConfirmation(
        environment=make_environment(identifier="env-456"),
        reported_states=[state(FIRST_TARGET, "terminated")],
    )


def test_changed_reported_state_set_changes_confirmation_identity() -> None:
    environment = make_environment()

    assert EC2DestructionConfirmation(
        environment=environment,
        reported_states=[state(FIRST_TARGET, "terminated")],
    ) != EC2DestructionConfirmation(
        environment=environment,
        reported_states=[state(FIRST_TARGET, "stopped")],
    )


def test_derived_outcome_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        EC2DestructionConfirmation(
            environment=make_environment(),
            reported_states=[state(FIRST_TARGET, "terminated")],
            outcome=EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED,
        )


def test_ec2_destruction_confirmation_is_immutable() -> None:
    confirmation = EC2DestructionConfirmation(
        environment=make_environment(),
        reported_states=[state(FIRST_TARGET, "terminated")],
    )

    with pytest.raises(FrozenInstanceError):
        confirmation.outcome = EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_reported_lifecycle_state_is_immutable() -> None:
    reported_state = state(FIRST_TARGET, "terminated")

    with pytest.raises(FrozenInstanceError):
        reported_state.lifecycle_state = "stopped"


def test_confirmation_does_not_mutate_environment_input() -> None:
    environment = make_environment()
    resource_target_arns = environment.resource_target_arns

    confirmation = EC2DestructionConfirmation(
        environment=environment,
        reported_states=[state(FIRST_TARGET, "terminated")],
    )

    assert confirmation.environment == environment
    assert environment.resource_target_arns == resource_target_arns
