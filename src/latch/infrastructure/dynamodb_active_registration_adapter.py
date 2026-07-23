import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from latch.domain.admission import (
    AdmissionRequest,
    OwnerRetirementApproval,
    RetirementLock,
)
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
                            "Key": {"identifier": {"S": target_ownership_identifier(target_arn)}},
                            "ConditionExpression": (
                                "owning_environment_identifier = "
                                ":owning_environment_identifier AND "
                                "owning_registration_fingerprint = "
                                ":owning_registration_fingerprint"
                            ),
                            "ExpressionAttributeValues": {
                                ":owning_environment_identifier": {"S": environment.identifier},
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

    def issue_owner_retirement_approval(
        self,
        claim: RetirementEvaluationClaim,
        approval: OwnerRetirementApproval,
    ) -> OwnerRetirementApproval:
        _validate_approval_inputs(claim, approval)
        environment = claim.environment
        expression_values = _approval_expression_values(claim, approval)

        self._dynamodb_client.update_item(
            TableName=self._table_name,
            Key={"identifier": {"S": environment.identifier}},
            UpdateExpression=(
                "SET approval_claim_token = :approval_claim_token, "
                "approval_claim_time = :approval_claim_time, "
                "approved_action = :approved_action, "
                "approved_by = :approved_by"
            ),
            ConditionExpression=(
                "registration_fingerprint = :registration_fingerprint AND "
                "evaluation_claim_token = :evaluation_claim_token AND "
                "evaluation_claim_time = :evaluation_claim_time AND "
                "owner = :approved_by AND "
                "("
                "(attribute_not_exists(approval_claim_token) AND "
                "attribute_not_exists(approval_claim_time) AND "
                "attribute_not_exists(approved_action) AND "
                "attribute_not_exists(approved_by)) OR "
                "(approval_claim_token = :approval_claim_token AND "
                "approval_claim_time = :approval_claim_time AND "
                "approved_action = :approved_action AND "
                "approved_by = :approved_by)"
                ")"
            ),
            ExpressionAttributeValues=expression_values,
        )

        return OwnerRetirementApproval(
            context=approval.context,
            approved_by=approval.approved_by,
        )

    def retrieve_owner_retirement_approval(
        self,
        claim: RetirementEvaluationClaim,
        context: Any,
    ) -> OwnerRetirementApproval | None:
        _validate_claim_context(claim, context)
        response = self._dynamodb_client.get_item(
            TableName=self._table_name,
            Key={"identifier": {"S": claim.environment.identifier}},
        )
        item = response.get("Item")
        if not isinstance(item, dict):
            raise ValueError("active registration is missing")

        _validate_registration_item_for_claim(item, claim)

        approval_fields = {
            name
            for name in (
                "approval_claim_token",
                "approval_claim_time",
                "approved_action",
                "approved_by",
            )
            if name in item
        }
        if not approval_fields:
            return None

        if approval_fields != {
            "approval_claim_token",
            "approval_claim_time",
            "approved_action",
            "approved_by",
        }:
            raise ValueError("stored approval state is partial")

        approval_claim_token = _required_item_string(item, "approval_claim_token")
        approval_claim_time = _required_item_string(item, "approval_claim_time")
        approved_action = _required_item_string(item, "approved_action")
        approved_by = _required_item_string(item, "approved_by")

        if (
            approval_claim_token != claim.claim_token
            or approval_claim_time != canonical_registration_timestamp(claim.claim_time)
            or approved_action != AdmissionRequest.RETIREMENT.value
            or approved_by != claim.environment.owner
        ):
            raise ValueError("stored approval state does not match claim and context")

        return OwnerRetirementApproval(context=context, approved_by=approved_by)

    def issue_retirement_lock(self, environment: Environment) -> RetirementLock:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        self._dynamodb_client.update_item(
            TableName=self._table_name,
            Key={"identifier": {"S": environment.identifier}},
            UpdateExpression="SET retirement_lock_state = :retirement_lock_state",
            ConditionExpression=(
                "identifier = :identifier AND "
                "registration_fingerprint = :registration_fingerprint AND "
                "("
                "attribute_not_exists(retirement_lock_state) OR "
                "retirement_lock_state = :retirement_lock_state"
                ")"
            ),
            ExpressionAttributeValues={
                ":identifier": {"S": environment.identifier},
                ":registration_fingerprint": {"S": immutable_registration_fingerprint(environment)},
                ":retirement_lock_state": {"S": "locked"},
            },
        )

        return RetirementLock(environment)

    def retrieve_retirement_lock(self, environment: Environment) -> RetirementLock | None:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        response = self._dynamodb_client.get_item(
            TableName=self._table_name,
            Key={"identifier": {"S": environment.identifier}},
        )
        item = response.get("Item")
        if not isinstance(item, dict):
            raise ValueError("active registration is missing")

        _validate_registration_item_for_environment(item, environment)

        if "retirement_lock_state" not in item:
            return None

        if _required_item_string(item, "retirement_lock_state") != "locked":
            raise ValueError("stored retirement lock state is malformed")

        return RetirementLock(environment)


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


def _validate_approval_inputs(
    claim: RetirementEvaluationClaim,
    approval: OwnerRetirementApproval,
) -> None:
    if not isinstance(approval, OwnerRetirementApproval):
        raise ValueError("approval must be an OwnerRetirementApproval")

    _validate_claim_context(claim, approval.context)

    if approval.approved_by != claim.environment.owner:
        raise ValueError("approved_by must match the environment owner")


def _validate_claim_context(claim: RetirementEvaluationClaim, context: Any) -> None:
    if not isinstance(claim, RetirementEvaluationClaim):
        raise ValueError("claim must be a RetirementEvaluationClaim")

    if context.environment != claim.environment:
        raise ValueError("context Environment must match claim")

    if context.requested_retirement is not AdmissionRequest.RETIREMENT:
        raise ValueError("context requested_retirement must be retirement")

    if context.evaluated_at != claim.claim_time:
        raise ValueError("context evaluated_at must match claim_time")


def _approval_expression_values(
    claim: RetirementEvaluationClaim,
    approval: OwnerRetirementApproval,
) -> dict[str, Any]:
    return {
        ":registration_fingerprint": {"S": immutable_registration_fingerprint(claim.environment)},
        ":evaluation_claim_token": {"S": claim.claim_token},
        ":evaluation_claim_time": {"S": canonical_registration_timestamp(claim.claim_time)},
        ":approval_claim_token": {"S": claim.claim_token},
        ":approval_claim_time": {"S": canonical_registration_timestamp(claim.claim_time)},
        ":approved_action": {"S": approval.context.requested_retirement.value},
        ":approved_by": {"S": approval.approved_by},
    }


def _validate_registration_item_for_claim(
    item: dict[str, Any],
    claim: RetirementEvaluationClaim,
) -> None:
    if _required_item_string(item, "identifier") != claim.environment.identifier:
        raise ValueError("active registration identifier does not match claim")

    if _required_item_string(item, "registration_fingerprint") != (
        immutable_registration_fingerprint(claim.environment)
    ):
        raise ValueError("active registration fingerprint does not match claim")

    if _required_item_string(item, "evaluation_claim_token") != claim.claim_token:
        raise ValueError("active registration claim token does not match claim")

    if _required_item_string(item, "evaluation_claim_time") != (
        canonical_registration_timestamp(claim.claim_time)
    ):
        raise ValueError("active registration claim time does not match claim")

    if _required_item_string(item, "owner") != claim.environment.owner:
        raise ValueError("active registration owner does not match claim")


def _validate_registration_item_for_environment(
    item: dict[str, Any],
    environment: Environment,
) -> None:
    if _required_item_string(item, "identifier") != environment.identifier:
        raise ValueError("active registration identifier does not match environment")

    if _required_item_string(item, "registration_fingerprint") != (
        immutable_registration_fingerprint(environment)
    ):
        raise ValueError("active registration fingerprint does not match environment")

    if _required_item_string(item, "owner") != environment.owner:
        raise ValueError("active registration owner does not match environment")


def _required_item_string(item: dict[str, Any], name: str) -> str:
    try:
        value = item[name]["S"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"active registration {name} must be present") from error

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"active registration {name} must be a non-empty string")

    return value


def canonical_registration_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
