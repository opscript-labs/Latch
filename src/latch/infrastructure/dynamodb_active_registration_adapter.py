import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from latch.domain.environment import Environment
from latch.domain.environment.retirement_evaluation_claim import RetirementEvaluationClaim
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
)

ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND = "ACTIVE_ENVIRONMENT_REGISTRATION"
TARGET_OWNERSHIP_KEY_PREFIX = "TARGET_OWNERSHIP#"


class DynamoDBActiveRegistrationAdapter:
    def __init__(self, dynamodb_client: Any, table_name: str) -> None:
        if not table_name.strip():
            raise ValueError("table_name must be non-empty")

        self._dynamodb_client = dynamodb_client
        self._table_name = table_name

    def register(self, environment: Environment) -> None:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        self._dynamodb_client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": self._table_name,
                        "Item": _item_for_environment(environment),
                        "ConditionExpression": "attribute_not_exists(identifier)",
                    }
                },
                *[
                    {
                        "Put": {
                            "TableName": self._table_name,
                            "Item": _ownership_item_for_target(environment, target_arn),
                            "ConditionExpression": "attribute_not_exists(identifier)",
                        }
                    }
                    for target_arn in sorted(environment.resource_target_arns)
                ],
            ],
        )

    def acquire_retirement_evaluation_claim(
        self,
        environment: Environment,
        claim_time: datetime,
    ) -> RetirementEvaluationClaim | None:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        claim = RetirementEvaluationClaim(environment=environment, claim_time=claim_time)
        try:
            self._dynamodb_client.update_item(
                TableName=self._table_name,
                Key={"identifier": {"S": environment.identifier}},
                UpdateExpression=(
                    "SET evaluation_claim_token = :evaluation_claim_token, "
                    "evaluation_claim_time = :evaluation_claim_time"
                ),
                ConditionExpression=(
                    "identifier = :identifier AND "
                    "registration_fingerprint = :registration_fingerprint AND "
                    "attribute_not_exists(evaluation_claim_token) AND "
                    "ttl_expires_at <= :evaluation_claim_time"
                ),
                ExpressionAttributeValues={
                    ":identifier": {"S": environment.identifier},
                    ":registration_fingerprint": {
                        "S": immutable_registration_fingerprint(environment)
                    },
                    ":evaluation_claim_token": {"S": claim.claim_token},
                    ":evaluation_claim_time": {"S": canonical_registration_timestamp(claim_time)},
                },
            )
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code == "ConditionalCheckFailedException":
                return None
            raise

        return claim

    def deregister_confirmed(self, confirmation: EC2DestructionConfirmation) -> None:
        if not isinstance(confirmation, EC2DestructionConfirmation):
            raise ValueError("confirmation must be an EC2DestructionConfirmation")

        if confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED:
            return

        environment = confirmation.environment
        self._dynamodb_client.transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": self._table_name,
                        "Key": {"identifier": {"S": environment.identifier}},
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
                *[
                    {
                        "Delete": {
                            "TableName": self._table_name,
                            "Key": {
                                "identifier": {
                                    "S": target_ownership_identifier(target_arn)
                                }
                            },
                            "ConditionExpression": (
                                "owning_environment_identifier = "
                                ":owning_environment_identifier AND "
                                "owning_registration_fingerprint = "
                                ":owning_registration_fingerprint"
                            ),
                            "ExpressionAttributeValues": {
                                ":owning_environment_identifier": {
                                    "S": environment.identifier
                                },
                                ":owning_registration_fingerprint": {
                                    "S": immutable_registration_fingerprint(environment)
                                },
                            },
                        }
                    }
                    for target_arn in sorted(environment.resource_target_arns)
                ],
            ],
        )


def immutable_registration_fingerprint(environment: Environment) -> str:
    canonical_environment = {
        "created_at": canonical_registration_timestamp(environment.created_at),
        "identifier": environment.identifier,
        "owner": environment.owner,
        "resource_target_arns": sorted(environment.resource_target_arns),
        "ttl_expires_at": canonical_registration_timestamp(environment.ttl_expires_at),
    }
    canonical_json = json.dumps(
        canonical_environment,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _item_for_environment(environment: Environment) -> dict[str, Any]:
    return {
        "record_kind": {"S": ACTIVE_ENVIRONMENT_REGISTRATION_RECORD_KIND},
        "identifier": {"S": environment.identifier},
        "owner": {"S": environment.owner},
        "created_at": {"S": canonical_registration_timestamp(environment.created_at)},
        "ttl_expires_at": {"S": canonical_registration_timestamp(environment.ttl_expires_at)},
        "resource_target_arns": {
            "SS": sorted(environment.resource_target_arns),
        },
        "registration_fingerprint": {
            "S": immutable_registration_fingerprint(environment),
        },
    }


def _ownership_item_for_target(
    environment: Environment,
    target_arn: str,
) -> dict[str, Any]:
    return {
        "identifier": {"S": target_ownership_identifier(target_arn)},
        "target_arn": {"S": target_arn},
        "owning_environment_identifier": {"S": environment.identifier},
        "owning_registration_fingerprint": {
            "S": immutable_registration_fingerprint(environment),
        },
    }


def target_ownership_identifier(target_arn: str) -> str:
    return f"{TARGET_OWNERSHIP_KEY_PREFIX}{target_arn}"


def canonical_registration_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
