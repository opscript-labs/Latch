from dataclasses import dataclass, field

from latch.domain.admission.operational_compatibility import OperationalAssertionCompatibility
from latch.domain.admission.operational_conflict import OperationalConflictRecognition
from latch.domain.admission.operational_dimension_association_set import (
    OperationalDimensionAssociationSet,
)


@dataclass(frozen=True, slots=True)
class OperationalConflictRecognitionCoverage:
    association_set: OperationalDimensionAssociationSet
    recognitions: frozenset[OperationalConflictRecognition] = field(
        init=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.association_set, OperationalDimensionAssociationSet):
            raise ValueError("association_set must be an OperationalDimensionAssociationSet")

        object.__setattr__(self, "recognitions", self._derive_recognitions())

    def _derive_recognitions(self) -> frozenset[OperationalConflictRecognition]:
        recognitions = set()
        for pair in self.association_set.required_comparison_pairs:
            first, second = tuple(pair)
            recognitions.add(
                OperationalConflictRecognition(
                    compatibility=OperationalAssertionCompatibility(first=first, second=second)
                )
            )

        return frozenset(recognitions)
