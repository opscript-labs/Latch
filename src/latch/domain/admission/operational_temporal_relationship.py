from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from latch.domain.admission.operational_dimension import OperationalDimensionAssociation
from latch.domain.evidence import (
    EvidenceInstant,
    EvidenceInterval,
    EvidenceTemporalContext,
    EvidenceTimeless,
)


class OperationalTemporalRelationshipOutcome(Enum):
    OVERLAPPING = "OVERLAPPING"
    FIRST_WHOLELY_BEFORE_SECOND = "FIRST_WHOLELY_BEFORE_SECOND"
    FIRST_WHOLELY_AFTER_SECOND = "FIRST_WHOLELY_AFTER_SECOND"
    TIMELESS_INVOLVED = "TIMELESS_INVOLVED"


@dataclass(frozen=True, slots=True)
class OperationalTemporalRelationship:
    first: OperationalDimensionAssociation
    second: OperationalDimensionAssociation
    outcome: OperationalTemporalRelationshipOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.first, OperationalDimensionAssociation):
            raise ValueError("first must be an OperationalDimensionAssociation")

        if not isinstance(self.second, OperationalDimensionAssociation):
            raise ValueError("second must be an OperationalDimensionAssociation")

        if self.first.dimension is not self.second.dimension:
            raise ValueError("dimension associations must have the same dimension")

        if (
            self.first.establishment.projection.context
            != self.second.establishment.projection.context
        ):
            raise ValueError("dimension associations must belong to the same context")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> OperationalTemporalRelationshipOutcome:
        return compare_temporal_contexts(
            self.first.establishment.projection.association.evidence.temporal_context,
            self.second.establishment.projection.association.evidence.temporal_context,
        )


def compare_temporal_contexts(
    first: EvidenceTemporalContext,
    second: EvidenceTemporalContext,
) -> OperationalTemporalRelationshipOutcome:
    if isinstance(first, EvidenceTimeless) or isinstance(second, EvidenceTimeless):
        return OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED

    first_start, first_end = temporal_bounds(first)
    second_start, second_end = temporal_bounds(second)

    if first_end < second_start:
        return OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_BEFORE_SECOND

    if first_start > second_end:
        return OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_AFTER_SECOND

    return OperationalTemporalRelationshipOutcome.OVERLAPPING


def temporal_bounds(
    temporal_context: EvidenceInstant | EvidenceInterval,
) -> tuple[datetime, datetime]:
    if isinstance(temporal_context, EvidenceInstant):
        return temporal_context.instant, temporal_context.instant

    return temporal_context.start, temporal_context.end
