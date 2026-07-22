from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.operational_compatibility import (
    OperationalAssertionCompatibility,
    OperationalCompatibilityOutcome,
)


class OperationalConflictRecognitionOutcome(Enum):
    OPERATIONAL_CONFLICT_RECOGNIZED = "OPERATIONAL_CONFLICT_RECOGNIZED"
    NO_OPERATIONAL_CONFLICT_RECOGNIZED = "NO_OPERATIONAL_CONFLICT_RECOGNIZED"
    OPERATIONAL_CONFLICT_STATUS_UNRESOLVED = "OPERATIONAL_CONFLICT_STATUS_UNRESOLVED"


@dataclass(frozen=True, slots=True)
class OperationalConflictRecognition:
    compatibility: OperationalAssertionCompatibility
    outcome: OperationalConflictRecognitionOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.compatibility, OperationalAssertionCompatibility):
            raise ValueError("compatibility must be an OperationalAssertionCompatibility")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> OperationalConflictRecognitionOutcome:
        if self.compatibility.outcome is OperationalCompatibilityOutcome.INCOMPATIBLE:
            return OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_RECOGNIZED

        if self.compatibility.outcome is OperationalCompatibilityOutcome.COMPATIBLE:
            return OperationalConflictRecognitionOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED

        return OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED
