from latch.domain.admission.context import AdmissionEvaluationContext
from latch.domain.admission.evidence_classification import (
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
)
from latch.domain.evidence import EvidenceInstant, EvidenceInterval, EvidenceTimeless


def is_evidence_relevant_to_context(
    association: EvidencePropositionClassificationAssociation,
    context: AdmissionEvaluationContext,
) -> bool:
    if association.classification not in {
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
    }:
        return False

    if not _referent_corresponds_to_environment(association, context):
        return False

    temporal_context = association.evidence.temporal_context
    if isinstance(temporal_context, EvidenceInstant):
        return temporal_context.instant <= context.evaluated_at

    if isinstance(temporal_context, EvidenceInterval):
        return temporal_context.start <= context.evaluated_at

    if isinstance(temporal_context, EvidenceTimeless):
        return True

    raise TypeError("unsupported Evidence temporal context")


def _referent_corresponds_to_environment(
    association: EvidencePropositionClassificationAssociation,
    context: AdmissionEvaluationContext,
) -> bool:
    evidence_referent = association.evidence.referent
    return (
        evidence_referent == context.environment.identifier
        or evidence_referent in context.environment.resource_target_arns
    )
