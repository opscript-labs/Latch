from latch.domain.admission import (
    AdmissionRequest,
    OwnerApprovalParticipation,
    RetirementAdmissionVerdict,
    RetirementLockParticipation,
    RetirementPrerequisiteStatus,
)
from latch.domain.environment import RetirementEvaluationClaim
from latch.infrastructure.claim_scoped_operational_evidence_collection import (
    ClaimScopedOperationalEvidenceCollection,
)
from latch.infrastructure.dynamodb_active_claim_validator import (
    ActiveClaimValidationResult,
    DynamoDBActiveClaimValidator,
)
from latch.infrastructure.dynamodb_active_registration_adapter import (
    DynamoDBActiveRegistrationAdapter,
)


class RetirementAdmissionCoordinator:
    def __init__(
        self,
        active_claim_validator: DynamoDBActiveClaimValidator,
        evidence_collection: ClaimScopedOperationalEvidenceCollection,
        active_registration_adapter: DynamoDBActiveRegistrationAdapter,
    ) -> None:
        self._active_claim_validator = active_claim_validator
        self._evidence_collection = evidence_collection
        self._active_registration_adapter = active_registration_adapter

    def evaluate(
        self,
        claim: RetirementEvaluationClaim,
    ) -> RetirementAdmissionVerdict | None:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if (
            self._active_claim_validator.validate(claim)
            is ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM
        ):
            return None

        readiness = self._evidence_collection.collect(claim)
        context = readiness.association_set.context
        if (
            context.environment != claim.environment
            or context.requested_retirement is not AdmissionRequest.RETIREMENT
            or context.evaluated_at != claim.claim_time
        ):
            raise ValueError("readiness must trace to the claim context")

        prerequisite_status = RetirementPrerequisiteStatus(readiness)
        approval = self._active_registration_adapter.retrieve_owner_retirement_approval(
            claim,
            context,
        )
        owner_participation = OwnerApprovalParticipation(
            prerequisite_status,
            approval,
        )
        lock = self._active_registration_adapter.retrieve_retirement_lock(context.environment)
        lock_participation = RetirementLockParticipation(owner_participation, lock)
        return RetirementAdmissionVerdict(lock_participation)
