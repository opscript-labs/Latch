from dataclasses import dataclass
from enum import Enum

from latch.domain.admission.source_standing import (
    OperationalAssertionEstablishment,
    OperationalEstablishmentOutcome,
)


class OperationalDimension(Enum):
    CPU_ACTIVITY = "CPU_ACTIVITY"
    NETWORK_ACTIVITY = "NETWORK_ACTIVITY"
    DEPLOYMENT_ACTIVITY = "DEPLOYMENT_ACTIVITY"


@dataclass(frozen=True, slots=True)
class OperationalDimensionAssociation:
    establishment: OperationalAssertionEstablishment
    dimension: OperationalDimension

    def __post_init__(self) -> None:
        if not isinstance(self.establishment, OperationalAssertionEstablishment):
            raise ValueError("establishment must be an OperationalAssertionEstablishment")

        if self.establishment.outcome is OperationalEstablishmentOutcome.ESTABLISHES_NOTHING:
            raise ValueError("ESTABLISHES_NOTHING cannot be associated with a dimension")

        if not isinstance(self.dimension, OperationalDimension):
            raise ValueError("dimension must be an OperationalDimension")
