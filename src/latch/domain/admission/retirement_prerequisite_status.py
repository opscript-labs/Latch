from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.operational_retirement_readiness import (
    OperationalRetirementReadiness,
    OperationalRetirementReadinessOutcome,
)
from latch.domain.admission.retirement_timing_eligibility import (
    RetirementTimingEligibility,
    RetirementTimingEligibilityOutcome,
)


class RetirementPrerequisiteStatusOutcome(Enum):
    RETIREMENT_PREREQUISITES_SATISFIED = "RETIREMENT_PREREQUISITES_SATISFIED"
    RETIREMENT_PREREQUISITES_NOT_SATISFIED = "RETIREMENT_PREREQUISITES_NOT_SATISFIED"
    RETIREMENT_PREREQUISITES_UNRESOLVED = "RETIREMENT_PREREQUISITES_UNRESOLVED"


@dataclass(frozen=True, slots=True)
class RetirementPrerequisiteStatus:
    readiness: OperationalRetirementReadiness
    timing_eligibility: RetirementTimingEligibility = field(init=False, compare=False)
    outcome: RetirementPrerequisiteStatusOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.readiness, OperationalRetirementReadiness):
            raise ValueError("readiness must be an OperationalRetirementReadiness")

        timing_eligibility = RetirementTimingEligibility(self.readiness.association_set.context)

        object.__setattr__(self, "timing_eligibility", timing_eligibility)
        object.__setattr__(self, "outcome", self._derive_outcome(timing_eligibility))

    def _derive_outcome(
        self,
        timing_eligibility: RetirementTimingEligibility,
    ) -> RetirementPrerequisiteStatusOutcome:
        if (
            timing_eligibility.outcome
            is RetirementTimingEligibilityOutcome.RETIREMENT_TIME_NOT_ELIGIBLE
            or self.readiness.outcome is OperationalRetirementReadinessOutcome.NOT_READY
        ):
            return RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_NOT_SATISFIED

        if self.readiness.outcome is OperationalRetirementReadinessOutcome.READY:
            return RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_SATISFIED

        return RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_UNRESOLVED
