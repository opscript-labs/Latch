from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionCompatibility,
    OperationalAssertionEstablishment,
    OperationalAssertionProjection,
    OperationalConflictRecognition,
    OperationalConflictRecognitionOutcome,
    OperationalDimension,
    OperationalDimensionAssociation,
)
from latch.domain.environment import Environment
from latch.domain.evidence import (
    Evidence,
    EvidenceInstant,
    EvidenceTemporalContext,
    EvidenceTimeless,
    SourceProvenance,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
CONTEXT_EVALUATED_AT = datetime(2026, 7, 23, 11, 0, tzinfo=UTC)


def make_context(evaluated_at: datetime = CONTEXT_EVALUATED_AT) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns={
                "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
            },
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=evaluated_at,
    )


def make_dimension_association(
    classification: EvidencePropositionClassification,
    temporal_context: EvidenceTemporalContext,
    context: AdmissionEvaluationContext | None = None,
    proposition: str = "operational proposition was observed",
) -> OperationalDimensionAssociation:
    if context is None:
        context = make_context()

    source_system = (
        "aws.cloudtrail.event"
        if classification is EvidencePropositionClassification.OPERATIONAL_ACTIVITY
        else "aws.cloudwatch.metrics"
    )
    evidence = Evidence(
        proposition=proposition,
        referent=context.environment.identifier,
        source_provenance=SourceProvenance(
            source_system=source_system,
            source_occurrence=f"{source_system}:{proposition}",
        ),
        temporal_context=temporal_context,
    )
    establishment = OperationalAssertionEstablishment(
        projection=OperationalAssertionProjection(
            association=EvidencePropositionClassificationAssociation(
                evidence=evidence,
                classification=classification,
            ),
            context=context,
        )
    )
    return OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    )


def make_compatibility(
    first_classification: EvidencePropositionClassification,
    second_classification: EvidencePropositionClassification,
    first_temporal_context: EvidenceTemporalContext,
    second_temporal_context: EvidenceTemporalContext,
) -> OperationalAssertionCompatibility:
    return OperationalAssertionCompatibility(
        first=make_dimension_association(
            first_classification,
            first_temporal_context,
            proposition="first proposition was observed",
        ),
        second=make_dimension_association(
            second_classification,
            second_temporal_context,
            proposition="second proposition was observed",
        ),
    )


def test_operational_conflict_recognition_has_exact_closed_vocabulary() -> None:
    assert list(OperationalConflictRecognitionOutcome) == [
        OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_RECOGNIZED,
        OperationalConflictRecognitionOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED,
        OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED,
    ]


def test_incompatible_maps_to_operational_conflict_recognized() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )

    recognition = OperationalConflictRecognition(compatibility=compatibility)

    assert (
        recognition.outcome is OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_RECOGNIZED
    )


def test_compatible_maps_to_no_operational_conflict_recognized() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )

    recognition = OperationalConflictRecognition(compatibility=compatibility)

    assert (
        recognition.outcome
        is OperationalConflictRecognitionOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED
    )


def test_unresolved_maps_to_operational_conflict_status_unresolved() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceTimeless(),
        EvidenceInstant(EVALUATED_AT),
    )

    recognition = OperationalConflictRecognition(compatibility=compatibility)

    assert (
        recognition.outcome
        is OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED
    )


def test_operational_conflict_recognition_equality_and_hashing_are_input_bound() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )

    recognition = OperationalConflictRecognition(compatibility=compatibility)
    same_recognition = OperationalConflictRecognition(compatibility=compatibility)

    assert recognition == same_recognition
    assert hash(recognition) == hash(same_recognition)


def test_changed_compatibility_input_produces_distinct_recognition() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )
    other_compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT + timedelta(seconds=1)),
    )

    assert OperationalConflictRecognition(compatibility=compatibility) != (
        OperationalConflictRecognition(compatibility=other_compatibility)
    )


def test_operational_conflict_recognition_outcome_cannot_be_caller_supplied() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )

    with pytest.raises(TypeError):
        OperationalConflictRecognition(
            compatibility=compatibility,
            outcome=OperationalConflictRecognitionOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED,
        )


def test_operational_conflict_recognition_is_immutable() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )
    recognition = OperationalConflictRecognition(compatibility=compatibility)

    with pytest.raises(FrozenInstanceError):
        recognition.outcome = (
            OperationalConflictRecognitionOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED
        )


def test_operational_conflict_recognition_does_not_mutate_inputs() -> None:
    compatibility = make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )
    associations = compatibility.associations
    temporal_relationship = compatibility.temporal_relationship

    OperationalConflictRecognition(compatibility=compatibility)

    assert compatibility == make_compatibility(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
    )
    assert compatibility.associations == associations
    assert compatibility.temporal_relationship == temporal_relationship
