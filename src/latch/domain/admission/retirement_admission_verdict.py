from dataclasses import dataclass, field

from latch.domain.admission.owner_approval_participation import (
    OwnerApprovalParticipationOutcome,
)
from latch.domain.admission.retirement_lock_participation import (
    RetirementLockParticipation,
)
from latch.domain.admission.verdict import AdmissionVerdict


@dataclass(frozen=True, slots=True)
class RetirementAdmissionVerdict:
    lock_participation: RetirementLockParticipation
    verdict: AdmissionVerdict = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.lock_participation, RetirementLockParticipation):
            raise ValueError("lock_participation must be a RetirementLockParticipation")

        object.__setattr__(self, "verdict", self._derive_verdict())

    def _derive_verdict(self) -> AdmissionVerdict:
        if (
            self.lock_participation.outcome
            is OwnerApprovalParticipationOutcome.PERMIT_FURTHER_ADMISSION
        ):
            return AdmissionVerdict.SAFE

        if (
            self.lock_participation.outcome
            is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION
        ):
            return AdmissionVerdict.UNSAFE

        return AdmissionVerdict.INSUFFICIENT
