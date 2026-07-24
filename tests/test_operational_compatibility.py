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
    OperationalCompatibilityOutcome,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalTemporalRelationshipOutcome,
)
from latch.domain.environment import Environment
from latch.domain.evidence import (
    Evidence,
    EvidenceInstant,
    EvidenceInterval,
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
    dimension: OperationalDimension = OperationalDimension.CPU_ACTIVITY,
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
    return OperationalDimensionAssociation(establishment=establishment, dimension=dimension)


def make_activity(
    temporal_context: EvidenceTemporalContext,
    **kwargs: object,
) -> OperationalDimensionAssociation:
    return make_dimension_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        temporal_context,
        **kwargs,
    )


def make_inactivity(
    temporal_context: EvidenceTemporalContext,
    **kwargs: object,
) -> OperationalDimensionAssociation:
    return make_dimension_association(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        temporal_context,
        **kwargs,
    )


def test_operational_compatibility_outcome_has_exact_closed_vocabulary() -> None:
    assert list(OperationalCompatibilityOutcome) == [
        OperationalCompatibilityOutcome.COMPATIBLE,
        OperationalCompatibilityOutcome.INCOMPATIBLE,
        OperationalCompatibilityOutcome.UNRESOLVED,
    ]


@pytest.mark.parametrize(
    ("first_factory", "second_factory", "expected"),
    [
        (make_activity, make_activity, OperationalCompatibilityOutcome.COMPATIBLE),
        (make_inactivity, make_inactivity, OperationalCompatibilityOutcome.COMPATIBLE),
        (make_activity, make_inactivity, OperationalCompatibilityOutcome.INCOMPATIBLE),
    ],
)
def test_overlapping_matrix_cells(
    first_factory: object,
    second_factory: object,
    expected: OperationalCompatibilityOutcome,
) -> None:
    first = first_factory(
        EvidenceInstant(EVALUATED_AT),
        proposition="first proposition was observed",
    )
    second = second_factory(
        EvidenceInstant(EVALUATED_AT),
        proposition="second proposition was observed",
    )

    compatibility = OperationalAssertionCompatibility(first=first, second=second)

    assert compatibility.outcome is expected


@pytest.mark.parametrize(
    ("first_factory", "second_factory", "expected"),
    [
        (make_activity, make_activity, OperationalCompatibilityOutcome.COMPATIBLE),
        (make_inactivity, make_inactivity, OperationalCompatibilityOutcome.COMPATIBLE),
        (make_activity, make_inactivity, OperationalCompatibilityOutcome.COMPATIBLE),
    ],
)
def test_before_after_matrix_cells(
    first_factory: object,
    second_factory: object,
    expected: OperationalCompatibilityOutcome,
) -> None:
    first = first_factory(EvidenceInstant(EVALUATED_AT))
    second = second_factory(EvidenceInstant(EVALUATED_AT + timedelta(seconds=1)))

    compatibility = OperationalAssertionCompatibility(first=first, second=second)

    assert (
        compatibility.temporal_relationship.outcome
        is OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_BEFORE_SECOND
    )
    assert compatibility.outcome is expected


@pytest.mark.parametrize(
    ("first_factory", "second_factory", "expected"),
    [
        (make_activity, make_activity, OperationalCompatibilityOutcome.COMPATIBLE),
        (make_inactivity, make_inactivity, OperationalCompatibilityOutcome.COMPATIBLE),
        (make_activity, make_inactivity, OperationalCompatibilityOutcome.UNRESOLVED),
    ],
)
def test_timeless_matrix_cells(
    first_factory: object,
    second_factory: object,
    expected: OperationalCompatibilityOutcome,
) -> None:
    first = first_factory(EvidenceTimeless())
    second = second_factory(EvidenceInstant(EVALUATED_AT))

    compatibility = OperationalAssertionCompatibility(first=first, second=second)

    assert (
        compatibility.temporal_relationship.outcome
        is OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED
    )
    assert compatibility.outcome is expected


def test_closed_boundary_overlap_activity_inactivity_is_incompatible() -> None:
    first = make_activity(
        EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT + timedelta(seconds=1))
    )
    second = make_inactivity(
        EvidenceInterval(
            start=EVALUATED_AT + timedelta(seconds=1),
            end=EVALUATED_AT + timedelta(seconds=2),
        )
    )

    compatibility = OperationalAssertionCompatibility(first=first, second=second)

    assert (
        compatibility.temporal_relationship.outcome
        is OperationalTemporalRelationshipOutcome.OVERLAPPING
    )
    assert compatibility.outcome is OperationalCompatibilityOutcome.INCOMPATIBLE


def test_reverse_ordering_preserves_identity_hashing_relationship_and_outcome() -> None:
    first = make_activity(EvidenceInstant(EVALUATED_AT))
    second = make_inactivity(EvidenceInstant(EVALUATED_AT))

    compatibility = OperationalAssertionCompatibility(first=first, second=second)
    reversed_compatibility = OperationalAssertionCompatibility(first=second, second=first)

    assert compatibility == reversed_compatibility
    assert hash(compatibility) == hash(reversed_compatibility)
    assert compatibility.temporal_relationship.outcome == (
        reversed_compatibility.temporal_relationship.outcome
    )
    assert compatibility.outcome == reversed_compatibility.outcome


def test_operational_compatibility_rejects_identical_associations() -> None:
    association = make_activity(EvidenceInstant(EVALUATED_AT))

    with pytest.raises(ValueError, match="distinct"):
        OperationalAssertionCompatibility(first=association, second=association)


def test_operational_compatibility_rejects_different_dimensions() -> None:
    first = make_activity(
        EvidenceInstant(EVALUATED_AT),
        dimension=OperationalDimension.CPU_ACTIVITY,
    )
    second = make_activity(
        EvidenceInstant(EVALUATED_AT),
        dimension=OperationalDimension.NETWORK_ACTIVITY,
    )

    with pytest.raises(ValueError, match="dimension"):
        OperationalAssertionCompatibility(first=first, second=second)


def test_operational_compatibility_rejects_different_contexts() -> None:
    first = make_activity(EvidenceInstant(EVALUATED_AT), context=make_context())
    second = make_activity(
        EvidenceInstant(EVALUATED_AT),
        context=make_context(CONTEXT_EVALUATED_AT + timedelta(seconds=1)),
    )

    with pytest.raises(ValueError, match="context"):
        OperationalAssertionCompatibility(first=first, second=second)


def test_derived_fields_cannot_be_caller_supplied() -> None:
    first = make_activity(EvidenceInstant(EVALUATED_AT))
    second = make_activity(EvidenceInstant(EVALUATED_AT))

    with pytest.raises(TypeError):
        OperationalAssertionCompatibility(
            first=first,
            second=second,
            outcome=OperationalCompatibilityOutcome.INCOMPATIBLE,
        )

    with pytest.raises(TypeError):
        OperationalAssertionCompatibility(
            first=first,
            second=second,
            temporal_relationship=None,
        )


def test_operational_compatibility_is_immutable() -> None:
    first = make_activity(
        EvidenceInstant(EVALUATED_AT),
        proposition="first activity was observed",
    )
    second = make_activity(
        EvidenceInstant(EVALUATED_AT),
        proposition="second activity was observed",
    )
    compatibility = OperationalAssertionCompatibility(first=first, second=second)

    with pytest.raises(FrozenInstanceError):
        compatibility.outcome = OperationalCompatibilityOutcome.INCOMPATIBLE


def test_operational_compatibility_does_not_mutate_inputs() -> None:
    first = make_activity(
        EvidenceInstant(EVALUATED_AT),
        proposition="first activity was observed",
    )
    second = make_inactivity(
        EvidenceInstant(EVALUATED_AT),
        proposition="first inactivity was observed",
    )

    OperationalAssertionCompatibility(first=first, second=second)

    assert first == make_activity(
        EvidenceInstant(EVALUATED_AT),
        proposition="first activity was observed",
    )
    assert second == make_inactivity(
        EvidenceInstant(EVALUATED_AT),
        proposition="first inactivity was observed",
    )
