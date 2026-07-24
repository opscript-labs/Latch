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
    OperationalEstablishmentOutcome,
    SourceStandingOutcome,
    determine_source_standing,
)
from latch.domain.environment import Environment
from latch.domain.evidence import Evidence, EvidenceInstant, SourceProvenance

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def make_context(identifier: str = "env-123") -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier=identifier,
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
    source_system: str,
    referent: str = "env-123",
) -> Evidence:
    return Evidence(
        proposition="operational proposition was observed",
        referent=referent,
        source_provenance=SourceProvenance(
            source_system=source_system,
            source_occurrence="source occurrence at 2026-07-23T10:00:00Z",
        ),
        temporal_context=EvidenceInstant(EVALUATED_AT),
    )


def make_projection(
    source_system: str,
    classification: EvidencePropositionClassification,
    referent: str = "env-123",
) -> OperationalAssertionProjection:
    return OperationalAssertionProjection(
        association=EvidencePropositionClassificationAssociation(
            evidence=make_evidence(source_system=source_system, referent=referent),
            classification=classification,
        ),
        context=make_context(),
    )


def test_source_standing_outcome_has_exact_closed_vocabulary() -> None:
    assert list(SourceStandingOutcome) == [
        SourceStandingOutcome.STANDING,
        SourceStandingOutcome.NO_STANDING,
    ]


def test_operational_establishment_outcome_has_exact_closed_vocabulary() -> None:
    assert list(OperationalEstablishmentOutcome) == [
        OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_ACTIVITY,
        OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY,
        OperationalEstablishmentOutcome.ESTABLISHES_NOTHING,
    ]


@pytest.mark.parametrize(
    ("source_system", "classification"),
    [
        (
            "aws.cloudwatch.metrics",
            EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        ),
        (
            "aws.cloudtrail.event",
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        ),
    ],
)
def test_approved_source_standing_pairs_return_standing(
    source_system: str,
    classification: EvidencePropositionClassification,
) -> None:
    assert (
        determine_source_standing(source_system, classification) is SourceStandingOutcome.STANDING
    )


@pytest.mark.parametrize(
    ("source_system", "classification"),
    [
        (
            "aws.cloudwatch.metrics",
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        ),
        (
            "aws.cloudtrail.event",
            EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        ),
        (
            "aws.config.resource",
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        ),
        (
            "aws.cloudwatch.metrics",
            EvidencePropositionClassification.UNCLASSIFIED,
        ),
    ],
)
def test_unrecognized_source_standing_pairs_return_no_standing(
    source_system: str,
    classification: EvidencePropositionClassification,
) -> None:
    assert (
        determine_source_standing(source_system, classification)
        is SourceStandingOutcome.NO_STANDING
    )


def test_relevant_activity_assertion_with_standing_establishes_activity() -> None:
    establishment = OperationalAssertionEstablishment(
        projection=make_projection(
            source_system="aws.cloudtrail.event",
            classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        )
    )

    assert establishment.outcome is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_ACTIVITY


def test_relevant_inactivity_assertion_with_standing_establishes_inactivity() -> None:
    establishment = OperationalAssertionEstablishment(
        projection=make_projection(
            source_system="aws.cloudwatch.metrics",
            classification=EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        )
    )

    assert (
        establishment.outcome is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY
    )


def test_irrelevant_assertion_establishes_nothing() -> None:
    establishment = OperationalAssertionEstablishment(
        projection=make_projection(
            source_system="aws.cloudtrail.event",
            classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            referent="env-456",
        )
    )

    assert establishment.outcome is OperationalEstablishmentOutcome.ESTABLISHES_NOTHING


def test_unclassified_assertion_establishes_nothing() -> None:
    establishment = OperationalAssertionEstablishment(
        projection=make_projection(
            source_system="aws.cloudtrail.event",
            classification=EvidencePropositionClassification.UNCLASSIFIED,
        )
    )

    assert establishment.outcome is OperationalEstablishmentOutcome.ESTABLISHES_NOTHING


def test_recognized_source_system_with_wrong_classification_establishes_nothing() -> None:
    establishment = OperationalAssertionEstablishment(
        projection=make_projection(
            source_system="aws.cloudwatch.metrics",
            classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        )
    )

    assert establishment.outcome is OperationalEstablishmentOutcome.ESTABLISHES_NOTHING


def test_operational_assertion_establishment_is_immutable() -> None:
    establishment = OperationalAssertionEstablishment(
        projection=make_projection(
            source_system="aws.cloudtrail.event",
            classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        )
    )

    with pytest.raises(FrozenInstanceError):
        establishment.outcome = OperationalEstablishmentOutcome.ESTABLISHES_NOTHING


def test_operational_assertion_establishment_does_not_mutate_inputs() -> None:
    projection = make_projection(
        source_system="aws.cloudtrail.event",
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )
    evidence = projection.association.evidence
    association = projection.association
    context = projection.context

    OperationalAssertionEstablishment(projection=projection)

    assert evidence == make_evidence("aws.cloudtrail.event")
    assert association == EvidencePropositionClassificationAssociation(
        evidence=make_evidence("aws.cloudtrail.event"),
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )
    assert context == make_context()
    assert projection == make_projection(
        source_system="aws.cloudtrail.event",
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )
