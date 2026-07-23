import re
from datetime import UTC, datetime
from typing import Any

from latch.domain.environment import Environment, TtlDueEnvironmentSelection
from latch.infrastructure.dynamodb_active_registration_adapter import (
    ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND,
    canonical_registration_timestamp,
    immutable_registration_fingerprint,
)

TTL_DUE_REGISTRATION_INDEX_NAME = "ttl-due-environment-registrations"
_CANONICAL_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


class DynamoDBTtlDueRegistrationQueryAdapter:
    def __init__(self, dynamodb_client: Any, table_name: str) -> None:
        if not table_name.strip():
            raise ValueError("table_name must be non-empty")

        self._dynamodb_client = dynamodb_client
        self._table_name = table_name

    def select_due(self, selection_time: datetime) -> TtlDueEnvironmentSelection:
        if selection_time.tzinfo is None or selection_time.utcoffset() is None:
            raise ValueError("selection_time must be timezone-aware")

        response = self._dynamodb_client.query(
            TableName=self._table_name,
            IndexName=TTL_DUE_REGISTRATION_INDEX_NAME,
            KeyConditionExpression=(
                "record_kind = :record_kind AND ttl_expires_at <= :selection_time"
            ),
            ExpressionAttributeValues={
                ":record_kind": {"S": ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND},
                ":selection_time": {"S": canonical_registration_timestamp(selection_time)},
            },
        )

        environments = [_environment_from_item(item) for item in response.get("Items", [])]
        return TtlDueEnvironmentSelection(
            selection_time=selection_time,
            environments=environments,
            page_has_last_evaluated_key="LastEvaluatedKey" in response,
        )


def _environment_from_item(item: dict[str, Any]) -> Environment:
    record_kind = _required_string(item, "record_kind")
    if record_kind != ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND:
        raise ValueError("item record_kind is not an active environment registration")

    environment = Environment(
        identifier=_required_string(item, "identifier"),
        owner=_required_string(item, "owner"),
        created_at=_required_timestamp(item, "created_at"),
        ttl_expires_at=_required_timestamp(item, "ttl_expires_at"),
        resource_target_arns=_required_string_set(item, "resource_target_arns"),
    )

    persisted_fingerprint = _required_string(item, "registration_fingerprint")
    if persisted_fingerprint != immutable_registration_fingerprint(environment):
        raise ValueError("item registration_fingerprint does not match environment")

    return environment


def _required_string(item: dict[str, Any], name: str) -> str:
    try:
        value = item[name]["S"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"item {name} must be a DynamoDB string") from error

    if not isinstance(value, str):
        raise ValueError(f"item {name} must be a DynamoDB string")

    return value


def _required_string_set(item: dict[str, Any], name: str) -> frozenset[str]:
    try:
        values = item[name]["SS"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"item {name} must be a DynamoDB string set") from error

    if not isinstance(values, list):
        raise ValueError(f"item {name} must be a DynamoDB string set")

    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"item {name} must be a DynamoDB string set")

    return frozenset(values)


def _required_timestamp(item: dict[str, Any], name: str) -> datetime:
    value = _required_string(item, name)
    if _CANONICAL_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise ValueError(f"item {name} must use canonical UTC timestamp form")

    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
