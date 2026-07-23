from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from latch.domain.environment import Environment, TtlDueEnvironmentSelection
from latch.infrastructure.dynamodb_active_registration_adapter import (
    ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND,
    canonical_registration_timestamp,
    immutable_registration_fingerprint,
)
from latch.infrastructure.dynamodb_ttl_due_registration_query_adapter import (
    TTL_DUE_REGISTRATION_INDEX_NAME,
    DynamoDBTtlDueRegistrationQueryAdapter,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
SELECTION_TIME = TTL_EXPIRES_AT
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


def item_for(environment: Environment) -> dict[str, object]:
    return {
        "record_kind": {"S": ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND},
        "identifier": {"S": environment.identifier},
        "owner": {"S": environment.owner},
        "created_at": {"S": canonical_registration_timestamp(environment.created_at)},
        "ttl_expires_at": {"S": canonical_registration_timestamp(environment.ttl_expires_at)},
        "resource_target_arns": {"SS": sorted(environment.resource_target_arns)},
        "registration_fingerprint": {"S": immutable_registration_fingerprint(environment)},
    }


def query_adapter(client: Mock) -> DynamoDBTtlDueRegistrationQueryAdapter:
    return DynamoDBTtlDueRegistrationQueryAdapter(client, "active-environments")


def test_selection_time_is_normalized_to_utc() -> None:
    selection = TtlDueEnvironmentSelection(
        selection_time=datetime(
            2026,
            7,
            23,
            15,
            30,
            tzinfo=timezone(timedelta(hours=5, minutes=30)),
        ),
        environments=[],
        page_has_last_evaluated_key=False,
    )

    assert selection.selection_time == datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def test_naive_selection_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="selection_time"):
        TtlDueEnvironmentSelection(
            selection_time=datetime(2026, 7, 23, 10, 0),
            environments=[],
            page_has_last_evaluated_key=False,
        )


def test_gsi_query_uses_due_time_bound_and_no_scan() -> None:
    client = Mock()
    client.query.return_value = {"Items": []}

    query_adapter(client).select_due(SELECTION_TIME)

    client.query.assert_called_once_with(
        TableName="active-environments",
        IndexName=TTL_DUE_REGISTRATION_INDEX_NAME,
        KeyConditionExpression=("record_kind = :record_kind AND ttl_expires_at <= :selection_time"),
        ExpressionAttributeValues={
            ":record_kind": {"S": ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND},
            ":selection_time": {"S": "2026-07-23T10:00:00.000000Z"},
        },
    )
    client.scan.assert_not_called()


def test_exact_ttl_expiry_is_selected_by_query_condition() -> None:
    client = Mock()
    client.query.return_value = {"Items": []}

    query_adapter(client).select_due(TTL_EXPIRES_AT)

    expression_values = client.query.call_args.kwargs["ExpressionAttributeValues"]
    assert expression_values[":selection_time"] == {"S": "2026-07-23T10:00:00.000000Z"}


def test_empty_page_creates_valid_empty_non_partial_selection() -> None:
    client = Mock()
    client.query.return_value = {"Items": []}

    selection = query_adapter(client).select_due(SELECTION_TIME)

    assert selection.environments == frozenset()
    assert selection.is_partial is False


def test_last_evaluated_key_creates_partial_selection() -> None:
    client = Mock()
    client.query.return_value = {"Items": [], "LastEvaluatedKey": {"identifier": {"S": "x"}}}

    selection = query_adapter(client).select_due(SELECTION_TIME)

    assert selection.is_partial is True


def test_returned_valid_records_reconstruct_exact_immutable_environments() -> None:
    environment = make_environment(resource_target_arns=frozenset({SECOND_TARGET, FIRST_TARGET}))
    client = Mock()
    client.query.return_value = {"Items": [item_for(environment)]}

    selection = query_adapter(client).select_due(SELECTION_TIME)

    assert selection.environments == frozenset({environment})


def test_target_ordering_does_not_affect_reconstructed_environment_identity() -> None:
    environment = make_environment(resource_target_arns=frozenset({SECOND_TARGET, FIRST_TARGET}))
    reversed_item = item_for(environment)
    reversed_item["resource_target_arns"] = {"SS": [SECOND_TARGET, FIRST_TARGET]}
    client = Mock()
    client.query.return_value = {"Items": [reversed_item]}

    selection = query_adapter(client).select_due(SELECTION_TIME)

    assert selection.environments == frozenset({environment})


def test_malformed_item_fails_query_operation() -> None:
    client = Mock()
    client.query.return_value = {"Items": [{"identifier": {"S": "env-123"}}]}

    with pytest.raises(ValueError):
        query_adapter(client).select_due(SELECTION_TIME)


def test_fingerprint_mismatch_fails_query_operation() -> None:
    environment = make_environment()
    item = item_for(environment)
    item["registration_fingerprint"] = {"S": "not-the-fingerprint"}
    client = Mock()
    client.query.return_value = {"Items": [item]}

    with pytest.raises(ValueError, match="registration_fingerprint"):
        query_adapter(client).select_due(SELECTION_TIME)


@pytest.mark.parametrize(
    "member_name",
    ["created_at", "ttl_expires_at"],
)
def test_invalid_persisted_timestamp_fails(member_name: str) -> None:
    item = item_for(make_environment())
    item[member_name] = {"S": "2026-07-23T10:00:00Z"}
    client = Mock()
    client.query.return_value = {"Items": [item]}

    with pytest.raises(ValueError, match="canonical UTC timestamp"):
        query_adapter(client).select_due(SELECTION_TIME)


def test_invalid_persisted_target_set_fails() -> None:
    item = item_for(make_environment())
    item["resource_target_arns"] = {"SS": ["arn:aws:s3:::not-ec2"]}
    item["registration_fingerprint"] = {"S": "not-used-after-environment-validation"}
    client = Mock()
    client.query.return_value = {"Items": [item]}

    with pytest.raises(ValueError, match="EC2 instance ARNs"):
        query_adapter(client).select_due(SELECTION_TIME)


def test_selection_and_source_environment_values_are_immutable_and_not_mutated() -> None:
    environment = make_environment()
    original_targets = environment.resource_target_arns
    selection = TtlDueEnvironmentSelection(
        selection_time=SELECTION_TIME,
        environments=[environment],
        page_has_last_evaluated_key=False,
    )

    with pytest.raises(FrozenInstanceError):
        selection.environments = frozenset()

    assert selection.environments == frozenset({environment})
    assert environment.resource_target_arns == original_targets
