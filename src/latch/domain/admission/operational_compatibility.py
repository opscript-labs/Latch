from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.operational_dimension import OperationalDimensionAssociation
from latch.domain.admission.operational_temporal_relationship import (
    OperationalTemporalRelationship,
    OperationalTemporalRelationshipOutcome,
)
from latch.domain.admission.source_standing import OperationalEstablishmentOutcome


class OperationalCompatibilityOutcome(Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class OperationalAssertionCompatibility:
    associations: frozenset[OperationalDimensionAssociation]
    temporal_relationship: OperationalTemporalRelationship = field(init=False, compare=False)
    outcome: OperationalCompatibilityOutcome = field(init=False, compare=False)

    def __init__(
        self,
        first: OperationalDimensionAssociation,
        second: OperationalDimensionAssociation,
    ) -> None:
        if not isinstance(first, OperationalDimensionAssociation):
            raise ValueError("first must be an OperationalDimensionAssociation")

        if not isinstance(second, OperationalDimensionAssociation):
            raise ValueError("second must be an OperationalDimensionAssociation")

        associations = frozenset({first, second})
        if len(associations) != 2:
            raise ValueError("compatibility requires two distinct associations")

        temporal_relationship = OperationalTemporalRelationship(first=first, second=second)

        object.__setattr__(self, "associations", associations)
        object.__setattr__(self, "temporal_relationship", temporal_relationship)
        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> OperationalCompatibilityOutcome:
        outcomes = {association.establishment.outcome for association in self.associations}

        if outcomes == {OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_ACTIVITY}:
            return OperationalCompatibilityOutcome.COMPATIBLE

        if outcomes == {OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY}:
            return OperationalCompatibilityOutcome.COMPATIBLE

        if self.temporal_relationship.outcome is OperationalTemporalRelationshipOutcome.OVERLAPPING:
            return OperationalCompatibilityOutcome.INCOMPATIBLE

        if (
            self.temporal_relationship.outcome
            is OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED
        ):
            return OperationalCompatibilityOutcome.UNRESOLVED

        return OperationalCompatibilityOutcome.COMPATIBLE
