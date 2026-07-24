from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionEstablishment,
    OperationalAssertionProjection,
    OperationalDimension,
    OperationalDimensionAssociation,
)
from latch.domain.environment import Environment
from latch.domain.evidence import Evidence, EvidenceInstant, SourceProvenance

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def make_context() -> AdmissionEvaluationContext:
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
        evaluated_at=EVALUATED_AT,
    )


def make_evidence(
    proposition: str = "operational activity was observed",
    source_system: str = "aws.cloudtrail.event",
) -> Evidence:
    return Evidence(
        proposition=proposition,
        referent="env-123",
        source_provenance=SourceProvenance(
            source_system=source_system,
            source_occurrence=f"{source_system}:{proposition}",
        ),
        temporal_context=EvidenceInstant(EVALUATED_AT),
    )


def make_establishment(
    classification: EvidencePropositionClassification = (
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY
    ),
    evidence: Evidence | None = None,
) -> OperationalAssertionEstablishment:
    if evidence is None:
        evidence = make_evidence()

    return OperationalAssertionEstablishment(
        projection=OperationalAssertionProjection(
            association=EvidencePropositionClassificationAssociation(
                evidence=evidence,
                classification=classification,
            ),
            context=make_context(),
        )
    )


def make_establishes_nothing() -> OperationalAssertionEstablishment:
    return make_establishment(
        classification=EvidencePropositionClassification.UNCLASSIFIED,
        evidence=make_evidence(),
    )


def test_operational_dimension_has_exact_closed_vocabulary() -> None:
    assert list(OperationalDimension) == [
        OperationalDimension.CPU_ACTIVITY,
        OperationalDimension.NETWORK_ACTIVITY,
        OperationalDimension.DEPLOYMENT_ACTIVITY,
    ]


def test_operational_dimension_association_constructs() -> None:
    establishment = make_establishment()

    association = OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    )

    assert association.establishment == establishment
    assert association.dimension is OperationalDimension.CPU_ACTIVITY


def test_operational_dimension_association_equality() -> None:
    establishment = make_establishment()

    assert OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    ) == OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    )


def test_operational_dimension_association_differs_by_establishment() -> None:
    first_establishment = make_establishment(evidence=make_evidence("cpu activity was observed"))
    second_establishment = make_establishment(
        evidence=make_evidence("network activity was observed")
    )

    assert OperationalDimensionAssociation(
        establishment=first_establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    ) != OperationalDimensionAssociation(
        establishment=second_establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    )


def test_operational_dimension_association_differs_by_dimension() -> None:
    establishment = make_establishment()

    assert OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    ) != OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.NETWORK_ACTIVITY,
    )


def test_multiple_dimensions_are_separate_associations() -> None:
    establishment = make_establishment()

    associations = frozenset(
        {
            OperationalDimensionAssociation(
                establishment=establishment,
                dimension=OperationalDimension.CPU_ACTIVITY,
            ),
            OperationalDimensionAssociation(
                establishment=establishment,
                dimension=OperationalDimension.NETWORK_ACTIVITY,
            ),
        }
    )

    assert len(associations) == 2


def test_established_outcome_with_no_association_remains_valid_and_unchanged() -> None:
    establishment = make_establishment()

    assert establishment == make_establishment()


def test_operational_dimension_association_rejects_establishes_nothing() -> None:
    with pytest.raises(ValueError, match="ESTABLISHES_NOTHING"):
        OperationalDimensionAssociation(
            establishment=make_establishes_nothing(),
            dimension=OperationalDimension.CPU_ACTIVITY,
        )


def test_operational_dimension_association_is_immutable() -> None:
    association = OperationalDimensionAssociation(
        establishment=make_establishment(),
        dimension=OperationalDimension.CPU_ACTIVITY,
    )

    with pytest.raises(FrozenInstanceError):
        association.dimension = OperationalDimension.NETWORK_ACTIVITY


def test_operational_dimension_association_does_not_mutate_inputs() -> None:
    establishment = make_establishment()
    projection = establishment.projection
    classification_association = projection.association
    evidence = classification_association.evidence
    context = projection.context

    OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    )

    assert evidence == classification_association.evidence
    assert classification_association == projection.association
    assert context == projection.context
    assert projection == establishment.projection
    assert establishment == make_establishment()
