from enum import Enum
from typing import Any

from latch.domain.environment import RetirementEvaluationClaim
from latch.infrastructure.dynamodb_active_registration_adapter import (
    canonical_registration_timestamp,
    immutable_registration_fingerprint,
)


class ActiveClaimValidationResult(Enum):
    VALID_ACTIVE_CLAIM = "VALID_ACTIVE_CLAIM"
    INVALID_ACTIVE_CLAIM = "INVALID_ACTIVE_CLAIM"


class DynamoDBActiveClaimValidator:
    def __init__(self, dynamodb_client: Any, table_name: str) -> None:
        if not table_name.strip():
            raise ValueError("table_name must be non-empty")

        self._dynamodb_client = dynamodb_client
        self._table_name = table_name

    def validate(
        self,
        claim: RetirementEvaluationClaim,
    ) -> ActiveClaimValidationResult:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        response = self._dynamodb_client.get_item(
            TableName=self._table_name,
            Key={"identifier": {"S": claim.environment.identifier}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not isinstance(item, dict):
            return ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM

        if _item_matches_claim(item, claim):
            return ActiveClaimValidationResult.VALID_ACTIVE_CLAIM

        return ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM

    def get_authoritative_owner(self, identifier: str) -> str | None:
        response = self._dynamodb_client.get_item(
            TableName=self._table_name,
            Key={"identifier": {"S": identifier}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not isinstance(item, dict):
            return None
        return _item_string(item, "owner")


def _item_matches_claim(
    item: dict[str, Any],
    claim: RetirementEvaluationClaim,
) -> bool:
    return (
        _item_string(item, "identifier") == claim.environment.identifier
        and _item_string(item, "registration_fingerprint")
        == immutable_registration_fingerprint(claim.environment)
        and _item_string(item, "evaluation_claim_token") == claim.claim_token
        and _item_string(item, "evaluation_claim_time")
        == canonical_registration_timestamp(claim.claim_time)
    )


def _item_string(item: dict[str, Any], name: str) -> str | None:
    try:
        value = item[name]["S"]
    except (KeyError, TypeError):
        return None

    if not isinstance(value, str) or not value.strip():
        return None

    return value
