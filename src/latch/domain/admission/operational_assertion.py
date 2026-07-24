from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.context import AdmissionEvaluationContext
from latch.domain.admission.evidence_classification import (
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
)
from latch.domain.admission.relevance import is_evidence_relevant_to_context


class OperationalAssertionOutcome(Enum):
    ASSERTS_OPERATIONAL_ACTIVITY = "ASSERTS_OPERATIONAL_ACTIVITY"
    ASSERTS_OPERATIONAL_INACTIVITY = "ASSERTS_OPERATIONAL_INACTIVITY"
    NO_OPERATIONAL_ASSERTION = "NO_OPERATIONAL_ASSERTION"


@dataclass(frozen=True, slots=True)
class OperationalAssertionProjection:
    association: EvidencePropositionClassificationAssociation
    context: AdmissionEvaluationContext
    outcome: OperationalAssertionOutcome = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.association, EvidencePropositionClassificationAssociation):
            raise ValueError("association must be an EvidencePropositionClassificationAssociation")

        if not isinstance(self.context, AdmissionEvaluationContext):
            raise ValueError("context must be an AdmissionEvaluationContext")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> OperationalAssertionOutcome:
        if not is_evidence_relevant_to_context(self.association, self.context):
            return OperationalAssertionOutcome.NO_OPERATIONAL_ASSERTION

        if (
            self.association.classification
            is EvidencePropositionClassification.OPERATIONAL_ACTIVITY
        ):
            return OperationalAssertionOutcome.ASSERTS_OPERATIONAL_ACTIVITY

        if (
            self.association.classification
            is EvidencePropositionClassification.OPERATIONAL_INACTIVITY
        ):
            return OperationalAssertionOutcome.ASSERTS_OPERATIONAL_INACTIVITY

        return OperationalAssertionOutcome.NO_OPERATIONAL_ASSERTION
