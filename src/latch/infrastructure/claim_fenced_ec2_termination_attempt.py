from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    RetirementAdmissionVerdict,
)
from latch.domain.environment import RetirementEvaluationClaim
from latch.domain.execution import (
    EC2TerminationInvocation,
    RetirementExecutionAuthorization,
    RetirementExecutionAuthorizationOutcome,
)
from latch.infrastructure.dynamodb_active_claim_validator import (
    ActiveClaimValidationResult,
    DynamoDBActiveClaimValidator,
)
from latch.infrastructure.ec2_termination_adapter import EC2TerminationAdapter


class ClaimFencedEC2TerminationAttempt:
    def __init__(
        self,
        active_claim_validator: DynamoDBActiveClaimValidator,
        termination_adapter: EC2TerminationAdapter,
    ) -> None:
        self._active_claim_validator = active_claim_validator
        self._termination_adapter = termination_adapter

    def attempt(
        self,
        claim: RetirementEvaluationClaim,
        verdict: RetirementAdmissionVerdict,
    ) -> RetirementExecutionAuthorization | EC2TerminationInvocation | None:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if not isinstance(verdict, RetirementAdmissionVerdict):
            raise ValueError("verdict must be a RetirementAdmissionVerdict")

        context = _context_from_verdict(verdict)
        if (
            context.environment != claim.environment
            or context.evaluated_at != claim.claim_time
            or context.requested_retirement is not AdmissionRequest.RETIREMENT
        ):
            raise ValueError("verdict must trace to the claim context")

        authorization = RetirementExecutionAuthorization(verdict)
        if (
            authorization.outcome
            is not RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED
        ):
            return authorization

        if (
            self._active_claim_validator.validate(claim)
            is ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM
        ):
            return None

        return self._termination_adapter.terminate(authorization)


def _context_from_verdict(
    verdict: RetirementAdmissionVerdict,
) -> AdmissionEvaluationContext:
    return verdict.lock_participation.owner_approval_participation.prerequisite_status.readiness.association_set.context
