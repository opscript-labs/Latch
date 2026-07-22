"""Execution domain package."""

from latch.domain.execution.ec2_destruction_confirmation import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
    EC2InstanceLifecycleState,
)
from latch.domain.execution.retirement_execution_authorization import (
    RetirementExecutionAuthorization,
    RetirementExecutionAuthorizationOutcome,
)

__all__ = [
    "EC2DestructionConfirmation",
    "EC2DestructionConfirmationOutcome",
    "EC2InstanceLifecycleState",
    "RetirementExecutionAuthorization",
    "RetirementExecutionAuthorizationOutcome",
]
