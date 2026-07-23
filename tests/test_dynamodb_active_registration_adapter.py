from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    OwnerRetirementApproval,
    RetirementLock,
)
from latch.domain.environment import Environment
from latch.domain.environment.retirement_evaluation_claim import RetirementEvaluationClaim
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


def make_claim(environment: Environment | None = None) -> RetirementEvaluationClaim:
    if environment is None:
        environment = make_environment()

    with patch(
        "latch.domain.environment.retirement_evaluation_claim.uuid.uuid4",
        return_value="claim-token",
    ):
        return RetirementEvaluationClaim(environment, TTL_EXPIRES_AT)


def make_context(claim: RetirementEvaluationClaim) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=claim.environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=claim.claim_time,
    )


def make_approval(claim: RetirementEvaluationClaim) -> OwnerRetirementApproval:
    return OwnerRetirementApproval(
        context=make_context(claim),
        approved_by=claim.environment.owner,
    )


def active_item_for_claim(
    claim: RetirementEvaluationClaim,
    *,
    include_approval: bool = False,
) -> dict[str, object]:
    item = {
        "identifier": {"S": claim.environment.identifier},
        "owner": {"S": claim.environment.owner},
        "registration_fingerprint": {"S": immutable_registration_fingerprint(claim.environment)},
        "evaluation_claim_token": {"S": claim.claim_token},
        "evaluation_claim_time": {"S": canonical_registration_timestamp(claim.claim_time)},
    }
    if include_approval:
        item.update(
            {
                "approval_claim_token": {"S": claim.claim_token},
                "approval_claim_time": {"S": canonical_registration_timestamp(claim.claim_time)},
                "approved_action": {"S": "retirement"},
                "approved_by": {"S": claim.environment.owner},
            }
        )
    return item


def active_item_for_environment(
    environment: Environment,
    *,
    include_lock: bool = False,
) -> dict[str, object]:
    item = {
        "identifier": {"S": environment.identifier},
        "owner": {"S": environment.owner},
        "registration_fingerprint": {"S": immutable_registration_fingerprint(environment)},
    }
    if include_lock:
        item["retirement_lock_state"] = {"S": "locked"}
    return item


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
    environment = make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(environment)

    transact_items = client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(transact_items) == 3
    assert transact_items[0]["Put"]["ConditionExpression"] == ("attribute_not_exists(identifier)")
    ownership_puts = [item["Put"] for item in transact_items[1:]]
    assert {put["Item"]["target_arn"]["S"] for put in ownership_puts} == {
        FIRST_TARGET,
        SECOND_TARGET,
    }
    assert all(
        put["ConditionExpression"] == "attribute_not_exists(identifier)" for put in ownership_puts
    )


def test_ownership_records_contain_exact_target_owner_and_fingerprint() -> None:
    client = Mock()
    environment = make_environment()

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(environment)

    ownership_item = client.transact_write_items.call_args.kwargs["TransactItems"][1]["Put"]["Item"]
    assert ownership_item == {
        "identifier": {"S": target_ownership_identifier(FIRST_TARGET)},
        "target_arn": {"S": FIRST_TARGET},
        "owning_environment_identifier": {"S": "env-123"},
        "owning_registration_fingerprint": {"S": immutable_registration_fingerprint(environment)},
    }


def test_ownership_keys_cannot_collide_with_environment_identifier_keys() -> None:
    assert target_ownership_identifier(FIRST_TARGET) != FIRST_TARGET
    assert target_ownership_identifier(FIRST_TARGET).startswith("TARGET_OWNERSHIP#")


def test_ownership_records_omit_ttl_due_gsi_attributes() -> None:
    client = Mock()

    DynamoDBActiveRegistrationAdapter(client, "active-environments").register(make_environment())

    ownership_item = client.transact_write_items.call_args.kwargs["TransactItems"][1]["Put"]["Item"]
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

    registration_put = client.transact_write_items.call_args.kwargs["TransactItems"][0]["Put"]
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


def test_successful_owner_approval_issuance_uses_exact_conditions() -> None:
    client = Mock()
    claim = make_claim()
    approval = make_approval(claim)

    issued = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).issue_owner_retirement_approval(claim, approval)

    assert issued == approval
    update_kwargs = client.update_item.call_args.kwargs
    assert update_kwargs["Key"] == {"identifier": {"S": "env-123"}}
    assert update_kwargs["UpdateExpression"] == (
        "SET approval_claim_token = :approval_claim_token, "
        "approval_claim_time = :approval_claim_time, "
        "approved_action = :approved_action, "
        "approved_by = :approved_by"
    )
    assert (
        "registration_fingerprint = :registration_fingerprint"
        in (update_kwargs["ConditionExpression"])
    )
    assert (
        "evaluation_claim_token = :evaluation_claim_token" in (update_kwargs["ConditionExpression"])
    )
    assert (
        "evaluation_claim_time = :evaluation_claim_time" in (update_kwargs["ConditionExpression"])
    )
    assert "owner = :approved_by" in update_kwargs["ConditionExpression"]
    assert update_kwargs["ExpressionAttributeValues"] == {
        ":registration_fingerprint": {"S": immutable_registration_fingerprint(claim.environment)},
        ":evaluation_claim_token": {"S": "claim-token"},
        ":evaluation_claim_time": {"S": "2026-07-23T10:00:00.000000Z"},
        ":approval_claim_token": {"S": "claim-token"},
        ":approval_claim_time": {"S": "2026-07-23T10:00:00.000000Z"},
        ":approved_action": {"S": "retirement"},
        ":approved_by": {"S": "team-platform"},
    }


def test_stored_approval_fields_do_not_affect_fingerprint_or_gsi_attributes() -> None:
    claim = make_claim()
    before = immutable_registration_fingerprint(claim.environment)
    item = active_item_for_claim(claim, include_approval=True)

    assert immutable_registration_fingerprint(claim.environment) == before
    assert "record_kind" not in {
        "approval_claim_token",
        "approval_claim_time",
        "approved_action",
        "approved_by",
    }
    assert "ttl_expires_at" not in {
        "approval_claim_token",
        "approval_claim_time",
        "approved_action",
        "approved_by",
    }
    assert item["approval_claim_token"] == {"S": "claim-token"}


def test_duplicate_owner_approval_issuance_is_idempotent() -> None:
    client = Mock()
    claim = make_claim()
    approval = make_approval(claim)

    first = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).issue_owner_retirement_approval(claim, approval)
    second = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).issue_owner_retirement_approval(claim, approval)

    assert first == second
    assert client.update_item.call_count == 2


@pytest.mark.parametrize(
    "reason",
    [
        "conflicting approval state",
        "stale fingerprint",
        "mismatched claim token",
        "mismatched claim time",
        "mismatched owner",
    ],
)
def test_owner_approval_issuance_condition_failure_rejects_without_extra_mutation(
    reason: str,
) -> None:
    client = Mock()
    error = conditional_failure()
    client.update_item.side_effect = error

    with pytest.raises(ClientError) as raised:
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).issue_owner_retirement_approval(make_claim(), make_approval(make_claim()))

    assert raised.value is error
    client.update_item.assert_called_once()
    client.put_item.assert_not_called()
    client.delete_item.assert_not_called()
    client.transact_write_items.assert_not_called()
    assert reason


def test_owner_approval_issuance_rejects_context_mismatch_before_write() -> None:
    client = Mock()
    claim = make_claim()
    other_claim = make_claim(make_environment(identifier="env-456"))
    approval = make_approval(other_claim)

    with pytest.raises(ValueError, match="Environment"):
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).issue_owner_retirement_approval(claim, approval)

    client.update_item.assert_not_called()


def test_retrieval_returns_absence_only_for_matching_registration_without_approval() -> None:
    client = Mock()
    claim = make_claim()
    client.get_item.return_value = {"Item": active_item_for_claim(claim)}

    approval = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).retrieve_owner_retirement_approval(claim, make_context(claim))

    assert approval is None


def test_retrieval_reconstructs_only_exact_matching_approval() -> None:
    client = Mock()
    claim = make_claim()
    client.get_item.return_value = {"Item": active_item_for_claim(claim, include_approval=True)}

    approval = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).retrieve_owner_retirement_approval(claim, make_context(claim))

    assert approval == make_approval(claim)
    assert approval is not None
    assert approval.approved_by == "team-platform"


@pytest.mark.parametrize(
    "item_update",
    [
        None,
        {"registration_fingerprint": {"S": "stale"}},
        {"evaluation_claim_token": {"S": "other-token"}},
        {"evaluation_claim_time": {"S": "2026-07-23T10:00:00.000001Z"}},
        {"approval_claim_token": {"S": "claim-token"}},
        {
            "approval_claim_token": {"S": "claim-token"},
            "approval_claim_time": {"S": "2026-07-23T10:00:00.000000Z"},
            "approved_action": {"S": "retirement"},
            "approved_by": {"S": "team-security"},
        },
        {
            "approval_claim_token": {"S": "claim-token"},
            "approval_claim_time": {"S": "2026-07-23T10:00:00.000000Z"},
            "approved_action": {"S": "rotation"},
            "approved_by": {"S": "team-platform"},
        },
    ],
)
def test_retrieval_rejects_missing_stale_partial_or_malformed_state(
    item_update: dict[str, object] | None,
) -> None:
    client = Mock()
    claim = make_claim()
    if item_update is None:
        client.get_item.return_value = {}
    else:
        item = active_item_for_claim(claim)
        item.update(item_update)
        client.get_item.return_value = {"Item": item}

    with pytest.raises(ValueError):
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).retrieve_owner_retirement_approval(claim, make_context(claim))


def test_retrieval_rejects_context_mismatch_before_read() -> None:
    client = Mock()
    claim = make_claim()
    mismatched_context = AdmissionEvaluationContext(
        environment=claim.environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=claim.claim_time + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="evaluated_at"):
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).retrieve_owner_retirement_approval(claim, mismatched_context)

    client.get_item.assert_not_called()


def test_successful_retirement_lock_issuance_uses_exact_registration_conditions() -> None:
    client = Mock()
    environment = make_environment()

    lock = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).issue_retirement_lock(environment)

    assert lock == RetirementLock(environment)
    update_kwargs = client.update_item.call_args.kwargs
    assert update_kwargs["Key"] == {"identifier": {"S": "env-123"}}
    assert update_kwargs["UpdateExpression"] == (
        "SET retirement_lock_state = :retirement_lock_state"
    )
    assert update_kwargs["ConditionExpression"] == (
        "identifier = :identifier AND "
        "registration_fingerprint = :registration_fingerprint AND "
        "("
        "attribute_not_exists(retirement_lock_state) OR "
        "retirement_lock_state = :retirement_lock_state"
        ")"
    )
    assert update_kwargs["ExpressionAttributeValues"] == {
        ":identifier": {"S": "env-123"},
        ":registration_fingerprint": {"S": immutable_registration_fingerprint(environment)},
        ":retirement_lock_state": {"S": "locked"},
    }


def test_duplicate_retirement_lock_issuance_is_idempotent() -> None:
    client = Mock()
    environment = make_environment()

    first = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).issue_retirement_lock(environment)
    second = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).issue_retirement_lock(environment)

    assert first == second
    assert client.update_item.call_count == 2


@pytest.mark.parametrize(
    "reason",
    [
        "missing registration",
        "stale fingerprint",
        "replaced registration",
        "mismatched registration",
        "conflicting lock state",
        "partial lock state",
        "malformed lock state",
    ],
)
def test_retirement_lock_issuance_condition_failure_rejects_without_extra_mutation(
    reason: str,
) -> None:
    client = Mock()
    error = conditional_failure()
    client.update_item.side_effect = error

    with pytest.raises(ClientError) as raised:
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).issue_retirement_lock(make_environment())

    assert raised.value is error
    client.update_item.assert_called_once()
    client.put_item.assert_not_called()
    client.delete_item.assert_not_called()
    client.transact_write_items.assert_not_called()
    assert reason


def test_retirement_lock_retrieval_returns_absence_for_exact_registration_without_lock() -> None:
    client = Mock()
    environment = make_environment()
    client.get_item.return_value = {"Item": active_item_for_environment(environment)}

    lock = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).retrieve_retirement_lock(environment)

    assert lock is None


def test_retirement_lock_retrieval_reconstructs_exact_lock() -> None:
    client = Mock()
    environment = make_environment()
    client.get_item.return_value = {
        "Item": active_item_for_environment(environment, include_lock=True)
    }

    lock = DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).retrieve_retirement_lock(environment)

    assert lock == RetirementLock(environment)


@pytest.mark.parametrize(
    "item_update",
    [
        None,
        {"registration_fingerprint": {"S": "stale"}},
        {"identifier": {"S": "env-456"}},
        {"owner": {"S": "team-security"}},
        {"retirement_lock_state": {"S": ""}},
        {"retirement_lock_state": {"S": "unlocked"}},
        {"retirement_lock_state": {"N": "1"}},
    ],
)
def test_retirement_lock_retrieval_rejects_missing_stale_or_malformed_state(
    item_update: dict[str, object] | None,
) -> None:
    client = Mock()
    environment = make_environment()
    if item_update is None:
        client.get_item.return_value = {}
    else:
        item = active_item_for_environment(environment, include_lock=True)
        item.update(item_update)
        client.get_item.return_value = {"Item": item}

    with pytest.raises(ValueError):
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).retrieve_retirement_lock(environment)


def test_retirement_lock_fields_do_not_affect_fingerprint_or_gsi_attributes() -> None:
    environment = make_environment()
    before = immutable_registration_fingerprint(environment)
    item = active_item_for_environment(environment, include_lock=True)

    assert immutable_registration_fingerprint(environment) == before
    assert "record_kind" not in {"retirement_lock_state"}
    assert "ttl_expires_at" not in {"retirement_lock_state"}
    assert item["retirement_lock_state"] == {"S": "locked"}


def test_confirmed_matching_destruction_performs_conditional_delete() -> None:
    client = Mock()
    environment = make_environment()
    claim = make_claim(environment)

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).deregister_confirmed(claim, confirmed(environment))

    transact_items = client.transact_write_items.call_args.kwargs["TransactItems"]
    assert transact_items == [
        {
            "Delete": {
                "TableName": "active-environments",
                "Key": {"identifier": {"S": "env-123"}},
                "ConditionExpression": (
                    "identifier = :identifier AND "
                    "registration_fingerprint = :registration_fingerprint AND "
                    "evaluation_claim_token = :evaluation_claim_token AND "
                    "evaluation_claim_time = :evaluation_claim_time"
                ),
                "ExpressionAttributeValues": {
                    ":identifier": {"S": "env-123"},
                    ":registration_fingerprint": {
                        "S": immutable_registration_fingerprint(environment)
                    },
                    ":evaluation_claim_token": {"S": "claim-token"},
                    ":evaluation_claim_time": {"S": "2026-07-23T10:00:00.000000Z"},
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
    environment = make_environment()

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).deregister_confirmed(make_claim(environment), not_confirmed(environment))

    client.delete_item.assert_not_called()
    client.transact_write_items.assert_not_called()


def test_stale_confirmation_cannot_delete_later_registration_with_same_identifier() -> None:
    client = Mock()
    environment = make_environment()
    claim = make_claim(environment)

    DynamoDBActiveRegistrationAdapter(
        client,
        "active-environments",
    ).deregister_confirmed(claim, confirmed(environment))

    delete = client.transact_write_items.call_args.kwargs["TransactItems"][0]["Delete"]
    assert delete["Key"] == {"identifier": {"S": "env-123"}}
    assert delete["ExpressionAttributeValues"] == {
        ":identifier": {"S": "env-123"},
        ":registration_fingerprint": {"S": immutable_registration_fingerprint(environment)},
        ":evaluation_claim_token": {"S": "claim-token"},
        ":evaluation_claim_time": {"S": "2026-07-23T10:00:00.000000Z"},
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
        environment = make_environment()
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).deregister_confirmed(make_claim(environment), confirmed(environment))

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
        environment = make_environment()
        DynamoDBActiveRegistrationAdapter(
            client,
            "active-environments",
        ).deregister_confirmed(make_claim(environment), confirmed(environment))

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
    adapter.deregister_confirmed(make_claim(environment), confirmation)

    assert environment.resource_target_arns == targets
    assert confirmation.environment == environment
    assert confirmation.reported_states == reported_states


def test_target_reuse_succeeds_after_confirmed_deregistration() -> None:
    client = Mock()
    adapter = DynamoDBActiveRegistrationAdapter(client, "active-environments")
    first = make_environment(identifier="env-123")
    second = make_environment(identifier="env-456")

    adapter.register(first)
    adapter.deregister_confirmed(make_claim(first), confirmed(first))
    adapter.register(second)

    assert client.transact_write_items.call_count == 3


def test_blank_table_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="table_name"):
        DynamoDBActiveRegistrationAdapter(Mock(), " ")
