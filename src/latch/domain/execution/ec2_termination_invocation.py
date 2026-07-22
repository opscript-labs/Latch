from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from latch.domain.execution.retirement_execution_authorization import (
    RetirementExecutionAuthorization,
    RetirementExecutionAuthorizationOutcome,
)


class EC2TerminationInvocationOutcome(Enum):
    EC2_TERMINATION_REQUEST_ACCEPTED = "EC2_TERMINATION_REQUEST_ACCEPTED"
    EC2_TERMINATION_REQUEST_NOT_ACCEPTED = "EC2_TERMINATION_REQUEST_NOT_ACCEPTED"


@dataclass(frozen=True, slots=True)
class EC2TerminationInvocationResult:
    target_arn: str
    accepted: bool

    def __post_init__(self) -> None:
        if not self.target_arn.strip():
            raise ValueError("target_arn must be non-empty")

        if not isinstance(self.accepted, bool):
            raise ValueError("accepted must be a bool")


@dataclass(frozen=True, slots=True)
class EC2TerminationInvocation:
    authorization: RetirementExecutionAuthorization
    results: frozenset[EC2TerminationInvocationResult]
    outcome: EC2TerminationInvocationOutcome = field(init=False, compare=False)

    def __init__(
        self,
        authorization: RetirementExecutionAuthorization,
        results: Iterable[EC2TerminationInvocationResult],
    ) -> None:
        if not isinstance(authorization, RetirementExecutionAuthorization):
            raise ValueError("authorization must be a RetirementExecutionAuthorization")

        if (
            authorization.outcome
            is not RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED
        ):
            raise ValueError("authorization must authorize retirement execution")

        result_values = tuple(results)
        registered_targets = self._registered_targets_from_authorization(authorization)
        seen_targets: set[str] = set()
        for result in result_values:
            if not isinstance(result, EC2TerminationInvocationResult):
                raise ValueError(
                    "results must contain EC2TerminationInvocationResult values"
                )

            if result.target_arn not in registered_targets:
                raise ValueError("returned target ARN must be registered on the Environment")

            if result.target_arn in seen_targets:
                raise ValueError("results must contain at most one result per target ARN")

            seen_targets.add(result.target_arn)

        object.__setattr__(self, "authorization", authorization)
        object.__setattr__(self, "results", frozenset(result_values))
        object.__setattr__(self, "outcome", self._derive_outcome(registered_targets))

    @staticmethod
    def _registered_targets_from_authorization(
        authorization: RetirementExecutionAuthorization,
    ) -> frozenset[str]:
        return (
            authorization.verdict.lock_participation.owner_approval_participation
            .prerequisite_status.readiness.association_set.context.environment
            .resource_target_arns
        )

    def _derive_outcome(
        self,
        registered_targets: frozenset[str],
    ) -> EC2TerminationInvocationOutcome:
        accepted_by_target = {result.target_arn: result.accepted for result in self.results}

        for target_arn in registered_targets:
            if accepted_by_target.get(target_arn) is not True:
                return EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED

        return EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_ACCEPTED
