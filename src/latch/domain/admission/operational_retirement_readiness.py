from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.operational_conflict_recognition_coverage import (
    OperationalConflictRecognitionCoverage,
)
from latch.domain.admission.operational_conflict_status import (
    OperationalConflictStatus,
    OperationalConflictStatusOutcome,
)
from latch.domain.admission.operational_dimension import (
    OperationalDimension,
    OperationalDimensionAssociation,
)
from latch.domain.admission.operational_dimension_association_set import (
    OperationalDimensionAssociationSet,
)
from latch.domain.admission.source_standing import OperationalEstablishmentOutcome


class OperationalRetirementReadinessOutcome(Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class OperationalRetirementReadiness:
    association_set: OperationalDimensionAssociationSet
    coverage: OperationalConflictRecognitionCoverage = field(init=False, compare=False)
    conflict_status: OperationalConflictStatus = field(init=False, compare=False)
    outcome: OperationalRetirementReadinessOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.association_set, OperationalDimensionAssociationSet):
            raise ValueError("association_set must be an OperationalDimensionAssociationSet")

        coverage = OperationalConflictRecognitionCoverage(self.association_set)
        conflict_status = OperationalConflictStatus(coverage)

        object.__setattr__(self, "coverage", coverage)
        object.__setattr__(self, "conflict_status", conflict_status)
        object.__setattr__(self, "outcome", self._derive_outcome(conflict_status))

    def _derive_outcome(
        self,
        conflict_status: OperationalConflictStatus,
    ) -> OperationalRetirementReadinessOutcome:
        if (
            self._dimension_establishes_activity(OperationalDimension.CPU_ACTIVITY)
            or self._dimension_establishes_activity(OperationalDimension.NETWORK_ACTIVITY)
            or self._dimension_establishes_activity(OperationalDimension.DEPLOYMENT_ACTIVITY)
            or conflict_status.outcome
            is OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_PRESENT
        ):
            return OperationalRetirementReadinessOutcome.NOT_READY

        if (
            not self._has_dimension(OperationalDimension.CPU_ACTIVITY)
            or not self._has_dimension(OperationalDimension.NETWORK_ACTIVITY)
            or conflict_status.outcome
            is OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED
        ):
            return OperationalRetirementReadinessOutcome.UNRESOLVED

        return OperationalRetirementReadinessOutcome.READY

    def _has_dimension(self, dimension: OperationalDimension) -> bool:
        return any(
            association.dimension is dimension
            for association in self.association_set.associations
        )

    def _dimension_establishes_activity(self, dimension: OperationalDimension) -> bool:
        return any(
            _establishes_activity_for_dimension(association, dimension)
            for association in self.association_set.associations
        )


def _establishes_activity_for_dimension(
    association: OperationalDimensionAssociation,
    dimension: OperationalDimension,
) -> bool:
    return (
        association.dimension is dimension
        and association.establishment.outcome
        is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_ACTIVITY
    )
