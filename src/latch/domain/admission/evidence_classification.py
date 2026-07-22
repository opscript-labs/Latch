from dataclasses import dataclass
from enum import Enum

from latch.domain.evidence import Evidence


class EvidencePropositionClassification(Enum):
    OPERATIONAL_ACTIVITY = "OPERATIONAL_ACTIVITY"
    OPERATIONAL_INACTIVITY = "OPERATIONAL_INACTIVITY"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class EvidencePropositionClassificationAssociation:
    evidence: Evidence
    classification: EvidencePropositionClassification

    def __post_init__(self) -> None:
        if not isinstance(self.classification, EvidencePropositionClassification):
            raise ValueError("classification must be an EvidencePropositionClassification")
