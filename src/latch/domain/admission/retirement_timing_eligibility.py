from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.context import AdmissionEvaluationContext


class RetirementTimingEligibilityOutcome(Enum):
    RETIREMENT_TIME_NOT_ELIGIBLE = "RETIREMENT_TIME_NOT_ELIGIBLE"
    RETIREMENT_TIME_ELIGIBLE = "RETIREMENT_TIME_ELIGIBLE"


@dataclass(frozen=True, slots=True)
class RetirementTimingEligibility:
    context: AdmissionEvaluationContext
    outcome: RetirementTimingEligibilityOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, AdmissionEvaluationContext):
            raise ValueError("context must be an AdmissionEvaluationContext")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> RetirementTimingEligibilityOutcome:
        if self.context.environment.is_ttl_expired(self.context.evaluated_at):
            return RetirementTimingEligibilityOutcome.RETIREMENT_TIME_ELIGIBLE

        return RetirementTimingEligibilityOutcome.RETIREMENT_TIME_NOT_ELIGIBLE
