import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from latch.domain.environment import Environment
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
)


class DynamoDBActiveRegistrationAdapter:
    def __init__(self, dynamodb_client: Any, table_name: str) -> None:
        if not table_name.strip():
            raise ValueError("table_name must be non-empty")

        self._dynamodb_client = dynamodb_client
        self._table_name = table_name

    def register(self, environment: Environment) -> None:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        self._dynamodb_client.put_item(
            TableName=self._table_name,
            Item=_item_for_environment(environment),
            ConditionExpression="attribute_not_exists(identifier)",
        )

    def deregister_confirmed(self, confirmation: EC2DestructionConfirmation) -> None:
        if not isinstance(confirmation, EC2DestructionConfirmation):
            raise ValueError("confirmation must be an EC2DestructionConfirmation")

        if (
            confirmation.outcome
            is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED
        ):
            return

        environment = confirmation.environment
        self._dynamodb_client.delete_item(
            TableName=self._table_name,
            Key={"identifier": {"S": environment.identifier}},
            ConditionExpression="registration_fingerprint = :registration_fingerprint",
            ExpressionAttributeValues={
                ":registration_fingerprint": {
                    "S": immutable_registration_fingerprint(environment)
                }
            },
        )


def immutable_registration_fingerprint(environment: Environment) -> str:
    canonical_environment = {
        "created_at": _canonical_datetime(environment.created_at),
        "identifier": environment.identifier,
        "owner": environment.owner,
        "resource_target_arns": sorted(environment.resource_target_arns),
        "ttl_expires_at": _canonical_datetime(environment.ttl_expires_at),
    }
    canonical_json = json.dumps(
        canonical_environment,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _item_for_environment(environment: Environment) -> dict[str, Any]:
    return {
        "identifier": {"S": environment.identifier},
        "owner": {"S": environment.owner},
        "created_at": {"S": _canonical_datetime(environment.created_at)},
        "ttl_expires_at": {"S": _canonical_datetime(environment.ttl_expires_at)},
        "resource_target_arns": {
            "SS": sorted(environment.resource_target_arns),
        },
        "registration_fingerprint": {
            "S": immutable_registration_fingerprint(environment),
        },
    }


def _canonical_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
