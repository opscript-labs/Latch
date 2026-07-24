from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.operational_conflict import OperationalConflictRecognitionOutcome
from latch.domain.admission.operational_conflict_recognition_coverage import (
    OperationalConflictRecognitionCoverage,
)


class OperationalConflictStatusOutcome(Enum):
    OPERATIONAL_CONFLICT_PRESENT = "OPERATIONAL_CONFLICT_PRESENT"
    OPERATIONAL_CONFLICT_STATUS_UNRESOLVED = "OPERATIONAL_CONFLICT_STATUS_UNRESOLVED"
    NO_OPERATIONAL_CONFLICT_RECOGNIZED = "NO_OPERATIONAL_CONFLICT_RECOGNIZED"


@dataclass(frozen=True, slots=True)
class OperationalConflictStatus:
    coverage: OperationalConflictRecognitionCoverage
    outcome: OperationalConflictStatusOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.coverage, OperationalConflictRecognitionCoverage):
            raise ValueError("coverage must be an OperationalConflictRecognitionCoverage")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> OperationalConflictStatusOutcome:
        recognition_outcomes = {recognition.outcome for recognition in self.coverage.recognitions}

        if (
            OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_RECOGNIZED
            in recognition_outcomes
        ):
            return OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_PRESENT

        if (
            OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED
            in recognition_outcomes
        ):
            return OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED

        return OperationalConflictStatusOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED
