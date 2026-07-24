from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from latch.domain.admission import (
    RetirementAdmissionRequest,
    RetirementAdmissionRequested,
    RetirementAdmissionVerdict,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim


class RetirementEvaluator(Protocol):
    def evaluate(
        self,
        claim: RetirementEvaluationClaim,
        claimant_identity: str,
    ) -> RetirementAdmissionVerdict | None: ...


class EnvironmentTransport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str
    created_at: datetime
    ttl_expires_at: datetime
    owner: str
    resource_target_arns: list[str] = Field(min_length=1)


class CanonicalRequestTransport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_identity: EnvironmentTransport
    retirement_claim_identity: str
    claimant_identity: str


class CanonicalEventTransport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_event_type: str
    version: str
    claim_time: datetime
    request: CanonicalRequestTransport


class RetirementAdmissionAdapter:
    def __init__(self, evaluator: RetirementEvaluator) -> None:
        self._evaluator = evaluator

    def handle(
        self,
        payload: dict[str, Any],
        producer_authority: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary")

        # 1. Producer authority validation (from deployment/invocation boundary)
        if producer_authority != "RetirementAdmissionRequestProducer":
            raise ValueError("Unauthorized producer attribution")

        # 2. Unrelated ingress / Product event type check
        if payload.get("product_event_type") != "RETIREMENT_ADMISSION_REQUESTED":
            raise ValueError("Unrelated or unsupported product event type")

        # 3. Version validation check
        if payload.get("version") != "1":
            raise ValueError("Unsupported or missing version")

        # 4. Canonical validation & parsing (producer is NOT in the model)
        try:
            event_transport = CanonicalEventTransport.model_validate(payload)
        except ValidationError as error:
            raise ValueError(f"Malformed or incomplete ingress request: {error}") from error

        # 5. Ingress / Domain objects construction & validation
        req_trans = event_transport.request
        env_trans = req_trans.environment_identity

        try:
            environment = Environment(
                identifier=env_trans.identifier,
                created_at=env_trans.created_at,
                ttl_expires_at=env_trans.ttl_expires_at,
                owner=env_trans.owner,
                resource_target_arns=env_trans.resource_target_arns,
            )

            # Retrieve claim_time from transport metadata
            claim_time = payload.get("claim_time")
            if not claim_time:
                raise ValueError("Missing claim_time transport metadata")

            if isinstance(claim_time, str):
                try:
                    claim_time_dt = datetime.fromisoformat(claim_time.replace("Z", "+00:00"))
                except Exception as e:
                    raise ValueError(f"Invalid claim_time format: {e}") from e
            elif isinstance(claim_time, datetime):
                claim_time_dt = claim_time
            else:
                raise ValueError("Invalid claim_time type")

            # Structural consistency validation
            domain_req = RetirementAdmissionRequest(
                environment_identity=environment,
                retirement_claim_identity=req_trans.retirement_claim_identity,
                claimant_identity=req_trans.claimant_identity,
            )

            # Construct canonical event object
            _ = RetirementAdmissionRequested(request=domain_req)

            # Construct evaluation claim
            claim = RetirementEvaluationClaim(environment, claim_time_dt)
            object.__setattr__(claim, "claim_token", domain_req.retirement_claim_identity)

        except ValueError as error:
            raise ValueError(f"Invalid request parameters or validation failed: {error}") from error

        # 6. Invoke evaluator (passing the claimant_identity for authoritative validation)
        verdict_obj = self._evaluator.evaluate(
            claim,
            claimant_identity=domain_req.claimant_identity,
        )

        if verdict_obj is None:
            return {
                "claim_token": claim.claim_token,
            }

        return {
            "verdict": verdict_obj.verdict.value,
            "claim_token": claim.claim_token,
        }
