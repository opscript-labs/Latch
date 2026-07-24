from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.context import AdmissionEvaluationContext
from latch.domain.admission.owner_retirement_approval import OwnerRetirementApproval
from latch.domain.admission.retirement_prerequisite_status import (
    RetirementPrerequisiteStatus,
    RetirementPrerequisiteStatusOutcome,
)


class OwnerApprovalParticipationOutcome(Enum):
    PERMIT_FURTHER_ADMISSION = "PERMIT_FURTHER_ADMISSION"
    BLOCK_FURTHER_ADMISSION = "BLOCK_FURTHER_ADMISSION"
    FURTHER_ADMISSION_UNRESOLVED = "FURTHER_ADMISSION_UNRESOLVED"


@dataclass(frozen=True, slots=True)
class OwnerApprovalParticipation:
    prerequisite_status: RetirementPrerequisiteStatus
    approval: OwnerRetirementApproval | None = None
    outcome: OwnerApprovalParticipationOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.prerequisite_status, RetirementPrerequisiteStatus):
            raise ValueError("prerequisite_status must be a RetirementPrerequisiteStatus")

        if self.approval is not None:
            if not isinstance(self.approval, OwnerRetirementApproval):
                raise ValueError("approval must be an OwnerRetirementApproval")

            if self.approval.context != self._context:
                raise ValueError("approval must concern the same context")

        object.__setattr__(self, "outcome", self._derive_outcome())

    @property
    def _context(self) -> AdmissionEvaluationContext:
        return self.prerequisite_status.readiness.association_set.context

    def _derive_outcome(self) -> OwnerApprovalParticipationOutcome:
        if (
            self.prerequisite_status.outcome
            is RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_UNRESOLVED
        ):
            return OwnerApprovalParticipationOutcome.FURTHER_ADMISSION_UNRESOLVED

        if (
            self.prerequisite_status.outcome
            is RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_SATISFIED
            and self.approval is not None
        ):
            return OwnerApprovalParticipationOutcome.PERMIT_FURTHER_ADMISSION

        return OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION
