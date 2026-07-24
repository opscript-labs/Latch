from dataclasses import dataclass, field

from latch.domain.admission.owner_approval_participation import (
    OwnerApprovalParticipation,
    OwnerApprovalParticipationOutcome,
)
from latch.domain.admission.retirement_lock import RetirementLock
from latch.domain.environment import Environment


@dataclass(frozen=True, slots=True)
class RetirementLockParticipation:
    owner_approval_participation: OwnerApprovalParticipation
    lock: RetirementLock | None = None
    outcome: OwnerApprovalParticipationOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.owner_approval_participation, OwnerApprovalParticipation):
            raise ValueError("owner_approval_participation must be an OwnerApprovalParticipation")

        if self.lock is not None:
            if not isinstance(self.lock, RetirementLock):
                raise ValueError("lock must be a RetirementLock")

            if self.lock.environment != self._environment:
                raise ValueError("lock must concern the same environment")

        object.__setattr__(self, "outcome", self._derive_outcome())

    @property
    def _environment(self) -> Environment:
        return self.owner_approval_participation.prerequisite_status.readiness.association_set.context.environment

    def _derive_outcome(self) -> OwnerApprovalParticipationOutcome:
        if self.lock is not None:
            return OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION

        return self.owner_approval_participation.outcome
