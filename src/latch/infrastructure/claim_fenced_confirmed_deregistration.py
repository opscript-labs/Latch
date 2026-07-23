from latch.domain.environment import RetirementEvaluationClaim
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
)
from latch.infrastructure.dynamodb_active_claim_validator import (
    ActiveClaimValidationResult,
    DynamoDBActiveClaimValidator,
)
from latch.infrastructure.dynamodb_active_registration_adapter import (
    DynamoDBActiveRegistrationAdapter,
)


class ClaimFencedConfirmedDeregistration:
    def __init__(
        self,
        active_claim_validator: DynamoDBActiveClaimValidator,
        active_registration_adapter: DynamoDBActiveRegistrationAdapter,
    ) -> None:
        self._active_claim_validator = active_claim_validator
        self._active_registration_adapter = active_registration_adapter

    def deregister(
        self,
        claim: RetirementEvaluationClaim,
        confirmation: EC2DestructionConfirmation,
    ) -> None:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if not isinstance(confirmation, EC2DestructionConfirmation):
            raise ValueError("confirmation must be an EC2DestructionConfirmation")

        if confirmation.environment != claim.environment:
            return

        if confirmation.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED:
            return

        if (
            self._active_claim_validator.validate(claim)
            is ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM
        ):
            return

        self._active_registration_adapter.deregister_confirmed(claim, confirmation)
