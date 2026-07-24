from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
)
from latch.domain.environment import RetirementEvaluationClaim
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2TerminationInvocation,
)
from latch.infrastructure.ec2_destruction_confirmation_adapter import (
    EC2DestructionConfirmationAdapter,
)


class PostInvocationEC2DestructionConfirmation:
    def __init__(
        self,
        confirmation_adapter: EC2DestructionConfirmationAdapter,
    ) -> None:
        self._confirmation_adapter = confirmation_adapter

    def confirm(
        self,
        claim: RetirementEvaluationClaim,
        invocation: EC2TerminationInvocation,
    ) -> EC2DestructionConfirmation | None:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if not isinstance(invocation, EC2TerminationInvocation):
            raise ValueError("invocation must be an EC2TerminationInvocation")

        context = _context_from_invocation(invocation)
        if (
            context.environment != claim.environment
            or context.evaluated_at != claim.claim_time
            or context.requested_retirement is not AdmissionRequest.RETIREMENT
        ):
            return None

        return self._confirmation_adapter.confirm(context.environment)


def _context_from_invocation(
    invocation: EC2TerminationInvocation,
) -> AdmissionEvaluationContext:
    return invocation.authorization.verdict.lock_participation.owner_approval_participation.prerequisite_status.readiness.association_set.context
