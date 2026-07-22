from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from latch.domain.environment import Environment

TERMINATED_STATE = "terminated"


class EC2DestructionConfirmationOutcome(Enum):
    DESTRUCTION_CONFIRMED = "DESTRUCTION_CONFIRMED"
    DESTRUCTION_NOT_CONFIRMED = "DESTRUCTION_NOT_CONFIRMED"


@dataclass(frozen=True, slots=True)
class EC2InstanceLifecycleState:
    target_arn: str
    lifecycle_state: str

    def __post_init__(self) -> None:
        if not self.target_arn.strip():
            raise ValueError("target_arn must be non-empty")

        if not self.lifecycle_state.strip():
            raise ValueError("lifecycle_state must be non-empty")


@dataclass(frozen=True, slots=True)
class EC2DestructionConfirmation:
    environment: Environment
    reported_states: frozenset[EC2InstanceLifecycleState]
    outcome: EC2DestructionConfirmationOutcome = field(init=False, compare=False)

    def __init__(
        self,
        environment: Environment,
        reported_states: Iterable[EC2InstanceLifecycleState],
    ) -> None:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        reported_state_values = tuple(reported_states)
        seen_target_arns: set[str] = set()
        for reported_state in reported_state_values:
            if not isinstance(reported_state, EC2InstanceLifecycleState):
                raise ValueError("reported_states must contain EC2InstanceLifecycleState values")

            if reported_state.target_arn not in environment.resource_target_arns:
                raise ValueError("reported target ARN must be registered on the Environment")

            if reported_state.target_arn in seen_target_arns:
                raise ValueError("reported_states must contain at most one state per target ARN")

            seen_target_arns.add(reported_state.target_arn)

        normalized_states = frozenset(reported_state_values)

        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "reported_states", normalized_states)
        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> EC2DestructionConfirmationOutcome:
        states_by_target = {
            reported_state.target_arn: reported_state.lifecycle_state
            for reported_state in self.reported_states
        }

        for target_arn in self.environment.resource_target_arns:
            if states_by_target.get(target_arn) != TERMINATED_STATE:
                return EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED

        return EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED
