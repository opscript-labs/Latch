from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import EndpointConnectionError

from latch.domain.environment import Environment
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
)
from latch.infrastructure.ec2_destruction_confirmation_adapter import (
    EC2DestructionConfirmationAdapter,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


def make_environment(
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
) -> Environment:
    return Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=resource_target_arns,
    )


def make_client(response: dict[str, object] | None = None) -> Mock:
    client = Mock()
    client.describe_instances.return_value = (
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "terminated"},
                        }
                    ]
                }
            ]
        }
        if response is None
        else response
    )
    return client


def test_one_regional_client_created_for_registered_target_region() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        EC2DestructionConfirmationAdapter().confirm(make_environment())

    session.client.assert_called_once_with("ec2", region_name="us-east-1")


def test_describe_instances_receives_exactly_registered_instance_ids() -> None:
    client = make_client(
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "terminated"},
                        },
                        {
                            "InstanceId": "i-0fedcba9876543210",
                            "State": {"Name": "terminated"},
                        },
                    ]
                }
            ]
        }
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        EC2DestructionConfirmationAdapter().confirm(
            make_environment(frozenset({FIRST_TARGET, SECOND_TARGET}))
        )

    requested_ids = client.describe_instances.call_args.kwargs["InstanceIds"]
    assert set(requested_ids) == {"i-0123456789abcdef0", "i-0fedcba9876543210"}


def test_complete_explicit_terminated_response_confirms_destruction() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert isinstance(confirmation, EC2DestructionConfirmation)
    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED


def test_one_non_terminated_state_does_not_confirm_destruction() -> None:
    client = make_client(
        {
            "Reservations": [
                {"Instances": [{"InstanceId": "i-0123456789abcdef0", "State": {"Name": "stopped"}}]}
            ]
        }
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_missing_registered_target_does_not_confirm_destruction() -> None:
    client = make_client(
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "terminated"},
                        }
                    ]
                }
            ]
        }
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(
            make_environment(frozenset({FIRST_TARGET, SECOND_TARGET}))
        )

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_duplicate_response_target_does_not_confirm_destruction() -> None:
    client = make_client(
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "terminated"},
                        },
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "terminated"},
                        },
                    ]
                }
            ]
        }
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_unexpected_response_target_does_not_confirm_destruction() -> None:
    client = make_client(
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "terminated"},
                        },
                        {
                            "InstanceId": "i-11111111111111111",
                            "State": {"Name": "terminated"},
                        },
                    ]
                }
            ]
        }
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


@pytest.mark.parametrize(
    "response",
    [
        {"Reservations": [{}]},
        {"Reservations": [{"Instances": [{"State": {"Name": "terminated"}}]}]},
        {"Reservations": [{"Instances": [{"InstanceId": "i-0123456789abcdef0"}]}]},
        {"Reservations": [{"Instances": [{"InstanceId": "i-0123456789abcdef0", "State": {}}]}]},
    ],
)
def test_malformed_reservation_instance_id_or_state_does_not_confirm_destruction(
    response: dict[str, object],
) -> None:
    client = make_client(response)
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_aws_sdk_request_failure_does_not_confirm_destruction() -> None:
    client = Mock()
    client.describe_instances.side_effect = EndpointConnectionError(
        endpoint_url="https://ec2.us-east-1.amazonaws.com"
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_credential_factory_failure_prevents_client_construction_and_request() -> None:
    with (
        patch(
            "latch.infrastructure.ec2_destruction_confirmation_adapter"
            ".create_ecs_task_role_session",
            side_effect=RuntimeError("credentials unavailable"),
        ),
        pytest.raises(RuntimeError, match="credentials unavailable"),
    ):
        EC2DestructionConfirmationAdapter().confirm(make_environment())


def test_adapter_never_invokes_terminate_instances() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        EC2DestructionConfirmationAdapter().confirm(make_environment())

    client.terminate_instances.assert_not_called()


def test_no_static_credentials_are_passed_to_client_creation() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert set(session.client.call_args.kwargs) == {"region_name"}


def test_returned_object_is_existing_confirmation_artifact() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_destruction_confirmation_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        confirmation = EC2DestructionConfirmationAdapter().confirm(make_environment())

    assert isinstance(confirmation, EC2DestructionConfirmation)
