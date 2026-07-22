"""Execution domain package."""

from latch.domain.execution.ec2_destruction_confirmation import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
    EC2InstanceLifecycleState,
)
from latch.domain.execution.ec2_termination_invocation import (
    EC2TerminationInvocation,
    EC2TerminationInvocationOutcome,
    EC2TerminationInvocationResult,
)
from latch.domain.execution.retirement_execution_authorization import (
    RetirementExecutionAuthorization,
    RetirementExecutionAuthorizationOutcome,
)

__all__ = [
    "EC2DestructionConfirmation",
    "EC2DestructionConfirmationOutcome",
    "EC2InstanceLifecycleState",
    "EC2TerminationInvocation",
    "EC2TerminationInvocationOutcome",
    "EC2TerminationInvocationResult",
    "RetirementExecutionAuthorization",
    "RetirementExecutionAuthorizationOutcome",
]
