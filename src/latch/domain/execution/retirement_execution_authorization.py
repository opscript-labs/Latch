from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission import AdmissionVerdict, RetirementAdmissionVerdict


class RetirementExecutionAuthorizationOutcome(Enum):
    RETIREMENT_EXECUTION_AUTHORIZED = "RETIREMENT_EXECUTION_AUTHORIZED"
    RETIREMENT_EXECUTION_REFUSED_UNSAFE = "RETIREMENT_EXECUTION_REFUSED_UNSAFE"
    RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT = "RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class RetirementExecutionAuthorization:
    verdict: RetirementAdmissionVerdict
    outcome: RetirementExecutionAuthorizationOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, RetirementAdmissionVerdict):
            raise ValueError("verdict must be a RetirementAdmissionVerdict")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> RetirementExecutionAuthorizationOutcome:
        if self.verdict.verdict is AdmissionVerdict.SAFE:
            return RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED

        if self.verdict.verdict is AdmissionVerdict.UNSAFE:
            return RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_REFUSED_UNSAFE

        return RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT
