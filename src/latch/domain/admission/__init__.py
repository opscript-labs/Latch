"""Admission domain package."""

from latch.domain.admission.context import AdmissionEvaluationContext, AdmissionRequest
from latch.domain.admission.evidence_classification import (
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
)
from latch.domain.admission.relevance import is_evidence_relevant_to_context
from latch.domain.admission.verdict import AdmissionVerdict

__all__ = [
    "AdmissionEvaluationContext",
    "AdmissionRequest",
    "AdmissionVerdict",
    "EvidencePropositionClassification",
    "EvidencePropositionClassificationAssociation",
    "is_evidence_relevant_to_context",
]
