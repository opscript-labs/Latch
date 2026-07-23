from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from latch.domain.admission import RetirementAdmissionVerdict
from latch.domain.environment import Environment, RetirementEvaluationClaim


class RetirementEvaluator(Protocol):
    def evaluate(
        self,
        claim: RetirementEvaluationClaim,
    ) -> RetirementAdmissionVerdict | None:
        ...


class EnvironmentTransport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str
    created_at: datetime
    ttl_expires_at: datetime
    owner: str
    resource_target_arns: list[str] = Field(min_length=1)


class RetirementRequestTransport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    environment: EnvironmentTransport
    claim_time: datetime


class RetirementAdmissionAdapter:
    def __init__(self, evaluator: RetirementEvaluator) -> None:
        self._evaluator = evaluator

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary")

        if payload.get("version") != "1":
            raise ValueError("Unsupported or missing version")

        try:
            request = RetirementRequestTransport.model_validate(payload)
        except ValidationError as error:
            raise ValueError(f"Malformed request payload: {error}") from error

        try:
            environment = Environment(
                identifier=request.environment.identifier,
                created_at=request.environment.created_at,
                ttl_expires_at=request.environment.ttl_expires_at,
                owner=request.environment.owner,
                resource_target_arns=request.environment.resource_target_arns,
            )
            claim = RetirementEvaluationClaim(environment, request.claim_time)
        except ValueError as error:
            raise ValueError(f"Invalid domain request parameters: {error}") from error

        verdict_obj = self._evaluator.evaluate(claim)

        if verdict_obj is None:
            return {
                "claim_token": claim.claim_token,
            }

        return {
            "verdict": verdict_obj.verdict.value,
            "claim_token": claim.claim_token,
        }
