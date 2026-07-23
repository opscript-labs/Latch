from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from latch.domain.environment import Environment
from latch.domain.execution import EC2DestructionConfirmation, EC2InstanceLifecycleState
from latch.infrastructure.dynamodb_active_registration_adapter import (
    ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND,
    DynamoDBActiveRegistrationAdapter,
    canonical_registration_timestamp,
    immutable_registration_fingerprint,
    target_ownership_identifier,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


def make_environment(
    *,
    identifier: str = "env-123",
    created_at: datetime = CREATED_AT,
    ttl_expires_at: datetime = TTL_EXPIRES_AT,
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
) -> Environment:
    return Environment(
        identifier=identifier,
        created_at=created_at,
        ttl_expires_at=ttl_expires_at,
        owner="team-platform",
        resource_target_arns=resource_target_arns,
    )


def confirmed(environment: Environment) -> EC2DestructionConfirmation:
    return EC2DestructionConfirmation(
        environment=environment,
        reported_states=[
            EC2InstanceLifecycleState(target_arn=target_arn, lifecycle_state="terminated")
            for target_arn in environment.resource_target_arns
        ],
    )


def not_confirmed(environment: Environment) -> EC2DestructionConfirmation:
    return EC2DestructionConfirmation(environment=environment, reported_states=[])


def conditional_failure() -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "condition failed",
            }
        },
        "PutItem",
    )


def transaction_conditional_failure() -> ClientError:
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


def service_failure() -> ClientError:
    return ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "service unavailable"}},
        "UpdateItem",
    )


def test_registration_writes_complete_immutable_record_with_fingerprint() -> None:
    client = Mock()
    environment = make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(environment)

    transaction_items = client.transact_write_items.call_args.kwargs["TransactItems"]
    item = transaction_items[0]["Put"]["Item"]
    assert item == {
        "record_kind": {"S": ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND},
        "identifier": {"S": "env-123"},
        "owner": {"S": "team-platform"},
        "created_at": {"S": "2026-07-23T08:00:00.000000Z"},
        "ttl_expires_at": {"S": "2026-07-23T10:00:00.000000Z"},
        "resource_target_arns": {"SS": sorted({FIRST_TARGET, SECOND_TARGET})},
        "registration_fingerprint": {"S": immutable_registration_fingerprint(environment)},
    }


def test_registration_uses_one_transaction_with_registration_and_ownership_puts() -> None:
    client = Mock()
    environment = make_environment(
        resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET})
    )

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(environment)

    transact_items = client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(transact_items) == 3
    assert transact_items[0]["Put"]["ConditionExpression"] == (
        "attribute_not_exists(identifier)"
    )
    ownership_puts = [item["Put"] for item in transact_items[1:]]
    assert {put["Item"]["target_arn"]["S"] for put in ownership_puts} == {
        FIRST_TARGET,
        SECOND_TARGET,
    }
    assert all(
        put["ConditionExpression"] == "attribute_not_exists(identifier)"
        for put in ownership_puts
    )


def test_ownership_records_contain_exact_target_owner_and_fingerprint() -> None:
    client = Mock()
    environment = make_environment()

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(environment)

    ownership_item = client.transact_write_items.call_args.kwargs["TransactItems"][1][
        "Put"
    ]["Item"]
    assert ownership_item == {
        "identifier": {"S": target_ownership_identifier(FIRST_TARGET)},
        "target_arn": {"S": FIRST_TARGET},
        "owning_environment_identifier": {"S": "env-123"},
        "owning_registration_fingerprint": {
            "S": immutable_registration_fingerprint(environment)
        },
    }


def test_ownership_keys_cannot_collide_with_environment_identifier_keys() -> None:
    assert target_ownership_identifier(FIRST_TARGET) != FIRST_TARGET
    assert target_ownership_identifier(FIRST_TARGET).startswith("TARGET_OWNERSHIP#")


def test_ownership_records_omit_ttl_due_gsi_attributes() -> None:
    client = Mock()

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(
        make_environment()
    )

    ownership_item = client.transact_write_items.call_args.kwargs["TransactItems"][1][
        "Put"
    ]["Item"]
    assert "record_kind" not in ownership_item
    assert "ttl_expires_at" not in ownership_item


def test_canonical_index_timestamps_have_fixed_utc_microsecond_precision() -> None:
    timestamp = datetime(
        2026,
        7,
        23,
        13,
        30,
        1,
        234,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    assert canonical_registration_timestamp(timestamp) == "2026-07-23T08:00:01.000234Z"


def test_target_input_order_does_not_change_persisted_fingerprint() -> None:
    first = make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    second = make_environment(resource_target_arns=frozenset({SECOND_TARGET, FIRST_TARGET}))

    assert immutable_registration_fingerprint(first) == (immutable_registration_fingerprint(second))


def test_timestamp_offsets_for_same_instant_produce_same_fingerprint() -> None:
    first = make_environment()
    second = make_environment(
        created_at=datetime(
            2026,
            7,
            23,
            13,
            30,
            tzinfo=timezone(timedelta(hours=5, minutes=30)),
        ),
        ttl_expires_at=datetime(
            2026,
            7,
            23,
            15,
            30,
            tzinfo=timezone(timedelta(hours=5, minutes=30)),
        ),
    )

    assert immutable_registration_fingerprint(first) == (immutable_registration_fingerprint(second))


def test_creation_uses_conditional_reject_on_existing_semantics() -> None:
    client = Mock()

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(make_environment())

    registration_put = client.transact_write_items.call_args.kwargs["TransactItems"][0][
        "Put"
    ]
    assert registration_put["ConditionExpression"] == "attribute_not_exists(identifier)"


@pytest.mark.parametrize(
    "reason",
    ["duplicate identifier", "target already owned by another registration"],
)
def test_transaction_conditional_creation_failure_aborts_without_partial_writes(
    reason: str,
) -> None:
    client = Mock()
    error = transaction_conditional_failure()
    client.transact_write_items.side_effect = error

    with pytest.raises(ClientError) as raised:
        DynamoDBActiveRegistrationAdapter(client, "active-environments").register(
            make_environment()
        )

    assert raised.value is error
    client.transact_write_items.assert_called_once()
    client.put_item.assert_not_called()
    assert reason


def test_successful_due_claim_returns_claim_and_writes_metadata() -> None:
    client = Mock()
    claim_time = datetime(
        2026,
        7,
        23,
        15,
        30,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    with patch(
        "latch.domain.environment.retirement_evaluation_claim.uuid.uuid4",
        return_value="claim-token",
    ):
        claim = DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).acquire_retirement_evaluation_claim(make_environment(), claim_time)

    assert claim is not None
    assert claim.claim_token == "claim-token"
    assert claim.claim_time == TTL_EXPIRES_AT
    client.update_item.assert_called_once()
    assert client.update_item.call_args.kwargs["UpdateExpression"] == (
        "SET evaluation_claim_token = :evaluation_claim_token, "
        "evaluation_claim_time = :evaluation_claim_time"
    )
    assert client.update_item.call_args.kwargs["ExpressionAttributeValues"][
        ":evaluation_claim_token"
    ] == {"S": "claim-token"}
    assert client.update_item.call_args.kwargs["ExpressionAttributeValues"][
        ":evaluation_claim_time"
    ] == {"S": "2026-07-23T10:00:00.000000Z"}


def test_exact_ttl_expiry_can_be_claimed() -> None:
    client = Mock()

    claim = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).acquire_retirement_evaluation_claim(make_environment(), TTL_EXPIRES_AT)

    assert claim is not None
    assert client.update_item.call_args.kwargs["ExpressionAttributeValues"][
        ":evaluation_claim_time"
    ] == {"S": "2026-07-23T10:00:00.000000Z"}


@pytest.mark.parametrize(
    "failure_reason",
    [
        "not-yet-due",
        "fingerprint-mismatch",
        "existing-claim-token",
        "concurrent-second-acquisition",
    ],
)
def test_conditional_claim_failure_returns_no_claim(failure_reason: str) -> None:
    client = Mock()
    client.update_item.side_effect = conditional_failure()

    claim = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).acquire_retirement_evaluation_claim(make_environment(), TTL_EXPIRES_AT)

    assert claim is None
    client.update_item.assert_called_once()
    client.get_item.assert_not_called()
    client.put_item.assert_not_called()
    client.delete_item.assert_not_called()
    assert failure_reason


def test_claim_condition_includes_identifier_fingerprint_absence_and_ttl() -> None:
    client = Mock()
    environment = make_environment()

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).acquire_retirement_evaluation_claim(environment, TTL_EXPIRES_AT)

    update_kwargs = client.update_item.call_args.kwargs
    assert update_kwargs["Key"] == {"identifier": {"S": "env-123"}}
    assert update_kwargs["ConditionExpression"] == (
        "identifier = :identifier AND "
        "registration_fingerprint = :registration_fingerprint AND "
        "attribute_not_exists(evaluation_claim_token) AND "
        "ttl_expires_at <= :evaluation_claim_time"
    )
    assert update_kwargs["ExpressionAttributeValues"][":identifier"] == {"S": "env-123"}
    assert update_kwargs["ExpressionAttributeValues"][":registration_fingerprint"] == {
        "S": immutable_registration_fingerprint(environment)
    }


def test_non_conditional_claim_failure_propagates_unchanged() -> None:
    client = Mock()
    error = service_failure()
    client.update_item.side_effect = error

    with pytest.raises(ClientError) as raised:
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).acquire_retirement_evaluation_claim(make_environment(), TTL_EXPIRES_AT)

    assert raised.value is error


def test_claim_acquisition_does_not_mutate_environment_input() -> None:
    client = Mock()
    environment = make_environment()
    targets = environment.resource_target_arns

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).acquire_retirement_evaluation_claim(environment, TTL_EXPIRES_AT)

    assert environment.resource_target_arns == targets
    assert environment.ttl_expires_at == TTL_EXPIRES_AT


def test_confirmed_matching_destruction_performs_conditional_delete() -> None:
    client = Mock()
    environment = make_environment()

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).deregister_confirmed(confirmed(environment))

    transact_items = client.transact_write_items.call_args.kwargs["TransactItems"]
    assert transact_items == [
        {
            "Delete": {
                "TableName": "active-environments",
                "Key": {"identifier": {"S": "env-123"}},
                "ConditionExpression": (
                    "registration_fingerprint = :registration_fingerprint"
                ),
                "ExpressionAttributeValues": {
                    ":registration_fingerprint": {
                        "S": immutable_registration_fingerprint(environment)
                    }
                },
            }
        },
        {
            "Delete": {
                "TableName": "active-environments",
                "Key": {"identifier": {"S": target_ownership_identifier(FIRST_TARGET)}},
                "ConditionExpression": (
                    "owning_environment_identifier = "
                    ":owning_environment_identifier AND "
                    "owning_registration_fingerprint = "
                    ":owning_registration_fingerprint"
                ),
                "ExpressionAttributeValues": {
                    ":owning_environment_identifier": {"S": "env-123"},
                    ":owning_registration_fingerprint": {
                        "S": immutable_registration_fingerprint(environment)
                    },
                },
            }
        },
    ]


def test_non_confirmed_destruction_performs_no_dynamodb_call() -> None:
    client = Mock()

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).deregister_confirmed(not_confirmed(make_environment()))

    client.delete_item.assert_not_called()
    client.transact_write_items.assert_not_called()


def test_stale_confirmation_cannot_delete_later_registration_with_same_identifier() -> None:
    client = Mock()
    environment = make_environment()

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).deregister_confirmed(confirmed(environment))

    delete = client.transact_write_items.call_args.kwargs["TransactItems"][0]["Delete"]
    assert delete["Key"] == {"identifier": {"S": "env-123"}}
    assert delete["ExpressionAttributeValues"] == {
        ":registration_fingerprint": {"S": immutable_registration_fingerprint(environment)}
    }


def test_mismatched_registration_cannot_be_deleted() -> None:
    original = make_environment()
    changed = make_environment(resource_target_arns=frozenset({SECOND_TARGET}))

    assert immutable_registration_fingerprint(original) != (
        immutable_registration_fingerprint(changed)
    )


def test_conditional_delete_failure_propagates_unchanged() -> None:
    client = Mock()
    error = transaction_conditional_failure()
    client.transact_write_items.side_effect = error

    with pytest.raises(ClientError) as raised:
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).deregister_confirmed(confirmed(make_environment()))

    assert raised.value is error
    client.delete_item.assert_not_called()


@pytest.mark.parametrize(
    "reason",
    ["stale fingerprint", "missing reservation", "mismatched reservation"],
)
def test_confirmed_deregistration_transaction_failure_aborts_all_deletes(
    reason: str,
) -> None:
    client = Mock()
    error = transaction_conditional_failure()
    client.transact_write_items.side_effect = error

    with pytest.raises(ClientError) as raised:
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).deregister_confirmed(confirmed(make_environment()))

    assert raised.value is error
    client.transact_write_items.assert_called_once()
    client.delete_item.assert_not_called()
    assert reason


def test_adapter_does_not_mutate_environment_or_confirmation_inputs() -> None:
    client = Mock()
    environment = make_environment()
    confirmation = confirmed(environment)
    targets = environment.resource_target_arns
    reported_states = confirmation.reported_states

    adapter = DynamoDBActiveRegistrationAdapter(client, "active-environments")
    adapter.register(environment)
    adapter.deregister_confirmed(confirmation)

    assert environment.resource_target_arns == targets
    assert confirmation.environment == environment
    assert confirmation.reported_states == reported_states


def test_target_reuse_succeeds_after_confirmed_deregistration() -> None:
    client = Mock()
    adapter = DynamoDBActiveRegistrationAdapter(client, "active-environments")
    first = make_environment(identifier="env-123")
    second = make_environment(identifier="env-456")

    adapter.register(first)
    adapter.deregister_confirmed(confirmed(first))
    adapter.register(second)

    assert client.transact_write_items.call_count == 3


def test_blank_table_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="table_name"):
        DynamoDBActiveRegistrationAdapter(Mock(), " ")
