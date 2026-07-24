from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.evidence_classification import EvidencePropositionClassification
from latch.domain.admission.operational_assertion import (
    OperationalAssertionOutcome,
    OperationalAssertionProjection,
)


class SourceStandingOutcome(Enum):
    STANDING = "STANDING"
    NO_STANDING = "NO_STANDING"


class OperationalEstablishmentOutcome(Enum):
    ESTABLISHES_OPERATIONAL_ACTIVITY = "ESTABLISHES_OPERATIONAL_ACTIVITY"
    ESTABLISHES_OPERATIONAL_INACTIVITY = "ESTABLISHES_OPERATIONAL_INACTIVITY"
    ESTABLISHES_NOTHING = "ESTABLISHES_NOTHING"


APPROVED_STANDING_PAIRS = frozenset(
    {
        (
            "aws.cloudwatch.metrics",
            EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        ),
        (
            "aws.cloudtrail.event",
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        ),
    }
)


def determine_source_standing(
    source_system: str,
    classification: EvidencePropositionClassification,
) -> SourceStandingOutcome:
    if (source_system, classification) in APPROVED_STANDING_PAIRS:
        return SourceStandingOutcome.STANDING

    return SourceStandingOutcome.NO_STANDING


@dataclass(frozen=True, slots=True)
class OperationalAssertionEstablishment:
    projection: OperationalAssertionProjection
    outcome: OperationalEstablishmentOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.projection, OperationalAssertionProjection):
            raise ValueError("projection must be an OperationalAssertionProjection")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> OperationalEstablishmentOutcome:
        standing = determine_source_standing(
            self.projection.association.evidence.source_provenance.source_system,
            self.projection.association.classification,
        )
        if standing is not SourceStandingOutcome.STANDING:
            return OperationalEstablishmentOutcome.ESTABLISHES_NOTHING

        if self.projection.outcome is OperationalAssertionOutcome.ASSERTS_OPERATIONAL_ACTIVITY:
            return OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_ACTIVITY

        if self.projection.outcome is OperationalAssertionOutcome.ASSERTS_OPERATIONAL_INACTIVITY:
            return OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY

        return OperationalEstablishmentOutcome.ESTABLISHES_NOTHING
