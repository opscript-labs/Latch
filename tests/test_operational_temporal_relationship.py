from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

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
    OperationalTemporalRelationship,
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
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=evaluated_at,
    )


def make_dimension_association(
    temporal_context: EvidenceTemporalContext,
    dimension: OperationalDimension = OperationalDimension.CPU_ACTIVITY,
    context: AdmissionEvaluationContext | None = None,
    proposition: str = "operational activity was observed",
) -> OperationalDimensionAssociation:
    if context is None:
        context = make_context()

    evidence = Evidence(
        proposition=proposition,
        referent=context.environment.identifier,
        source_provenance=SourceProvenance(
            source_system="aws.cloudtrail.event",
            source_occurrence=f"cloudtrail event:{proposition}",
        ),
        temporal_context=temporal_context,
    )
    establishment = OperationalAssertionEstablishment(
        projection=OperationalAssertionProjection(
            association=EvidencePropositionClassificationAssociation(
                evidence=evidence,
                classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            ),
            context=context,
        )
    )
    return OperationalDimensionAssociation(establishment=establishment, dimension=dimension)


def test_operational_temporal_relationship_has_exact_closed_vocabulary() -> None:
    assert list(OperationalTemporalRelationshipOutcome) == [
        OperationalTemporalRelationshipOutcome.OVERLAPPING,
        OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_BEFORE_SECOND,
        OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_AFTER_SECOND,
        OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED,
    ]


def test_same_instants_overlap() -> None:
    first = make_dimension_association(EvidenceInstant(EVALUATED_AT))
    second = make_dimension_association(EvidenceInstant(EVALUATED_AT))

    relationship = OperationalTemporalRelationship(first=first, second=second)

    assert relationship.outcome is OperationalTemporalRelationshipOutcome.OVERLAPPING


def test_earlier_and_later_instants_are_directed_and_reverse() -> None:
    first = make_dimension_association(EvidenceInstant(EVALUATED_AT))
    second = make_dimension_association(EvidenceInstant(EVALUATED_AT + timedelta(seconds=1)))

    relationship = OperationalTemporalRelationship(first=first, second=second)
    reversed_relationship = OperationalTemporalRelationship(first=second, second=first)

    assert (
        relationship.outcome
        is OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_BEFORE_SECOND
    )
    assert (
        reversed_relationship.outcome
        is OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_AFTER_SECOND
    )


def test_instant_inside_closed_interval_overlaps() -> None:
    instant = make_dimension_association(EvidenceInstant(EVALUATED_AT))
    interval = make_dimension_association(
        EvidenceInterval(
            start=EVALUATED_AT - timedelta(seconds=1),
            end=EVALUATED_AT + timedelta(seconds=1),
        )
    )

    relationship = OperationalTemporalRelationship(first=instant, second=interval)

    assert relationship.outcome is OperationalTemporalRelationshipOutcome.OVERLAPPING


def test_instant_before_closed_interval_is_before() -> None:
    instant = make_dimension_association(EvidenceInstant(EVALUATED_AT))
    interval = make_dimension_association(
        EvidenceInterval(
            start=EVALUATED_AT + timedelta(seconds=1),
            end=EVALUATED_AT + timedelta(seconds=2),
        )
    )

    relationship = OperationalTemporalRelationship(first=instant, second=interval)

    assert (
        relationship.outcome
        is OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_BEFORE_SECOND
    )


def test_instant_after_closed_interval_is_after() -> None:
    instant = make_dimension_association(EvidenceInstant(EVALUATED_AT + timedelta(seconds=2)))
    interval = make_dimension_association(
        EvidenceInterval(
            start=EVALUATED_AT,
            end=EVALUATED_AT + timedelta(seconds=1),
        )
    )

    relationship = OperationalTemporalRelationship(first=instant, second=interval)

    assert (
        relationship.outcome
        is OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_AFTER_SECOND
    )


def test_overlapping_intervals_overlap() -> None:
    first = make_dimension_association(
        EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT + timedelta(seconds=2))
    )
    second = make_dimension_association(
        EvidenceInterval(
            start=EVALUATED_AT + timedelta(seconds=1),
            end=EVALUATED_AT + timedelta(seconds=3),
        )
    )

    relationship = OperationalTemporalRelationship(first=first, second=second)

    assert relationship.outcome is OperationalTemporalRelationshipOutcome.OVERLAPPING


def test_intervals_meeting_at_closed_boundary_overlap() -> None:
    first = make_dimension_association(
        EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT + timedelta(seconds=1))
    )
    second = make_dimension_association(
        EvidenceInterval(
            start=EVALUATED_AT + timedelta(seconds=1),
            end=EVALUATED_AT + timedelta(seconds=2),
        )
    )

    relationship = OperationalTemporalRelationship(first=first, second=second)

    assert relationship.outcome is OperationalTemporalRelationshipOutcome.OVERLAPPING


def test_disjoint_intervals_are_directed_and_reverse() -> None:
    first = make_dimension_association(
        EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT + timedelta(seconds=1))
    )
    second = make_dimension_association(
        EvidenceInterval(
            start=EVALUATED_AT + timedelta(seconds=2),
            end=EVALUATED_AT + timedelta(seconds=3),
        )
    )

    relationship = OperationalTemporalRelationship(first=first, second=second)
    reversed_relationship = OperationalTemporalRelationship(first=second, second=first)

    assert (
        relationship.outcome
        is OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_BEFORE_SECOND
    )
    assert (
        reversed_relationship.outcome
        is OperationalTemporalRelationshipOutcome.FIRST_WHOLELY_AFTER_SECOND
    )


@pytest.mark.parametrize(
    "other_temporal_context",
    [
        EvidenceInstant(EVALUATED_AT),
        EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT),
        EvidenceTimeless(),
    ],
)
def test_timeless_pairings_are_timeless_involved(
    other_temporal_context: EvidenceTemporalContext,
) -> None:
    timeless = make_dimension_association(EvidenceTimeless())
    other = make_dimension_association(other_temporal_context)

    relationship = OperationalTemporalRelationship(first=timeless, second=other)
    reversed_relationship = OperationalTemporalRelationship(first=other, second=timeless)

    assert relationship.outcome is OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED
    assert (
        reversed_relationship.outcome
        is OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED
    )


def test_operational_temporal_relationship_rejects_different_dimensions() -> None:
    first = make_dimension_association(
        EvidenceInstant(EVALUATED_AT),
        dimension=OperationalDimension.CPU_ACTIVITY,
    )
    second = make_dimension_association(
        EvidenceInstant(EVALUATED_AT),
        dimension=OperationalDimension.NETWORK_ACTIVITY,
    )

    with pytest.raises(ValueError, match="dimension"):
        OperationalTemporalRelationship(first=first, second=second)


def test_operational_temporal_relationship_rejects_different_contexts() -> None:
    first = make_dimension_association(EvidenceInstant(EVALUATED_AT), context=make_context())
    second = make_dimension_association(
        EvidenceInstant(EVALUATED_AT),
        context=make_context(EVALUATED_AT + timedelta(seconds=1)),
    )

    with pytest.raises(ValueError, match="context"):
        OperationalTemporalRelationship(first=first, second=second)


def test_operational_temporal_relationship_is_immutable() -> None:
    first = make_dimension_association(EvidenceInstant(EVALUATED_AT))
    second = make_dimension_association(EvidenceInstant(EVALUATED_AT))
    relationship = OperationalTemporalRelationship(first=first, second=second)

    with pytest.raises(FrozenInstanceError):
        relationship.outcome = OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED


def test_operational_temporal_relationship_identity_is_ordered_and_input_bound() -> None:
    first = make_dimension_association(
        EvidenceInstant(EVALUATED_AT),
        proposition="first activity was observed",
    )
    second = make_dimension_association(
        EvidenceInstant(EVALUATED_AT + timedelta(seconds=1)),
        proposition="second activity was observed",
    )

    relationship = OperationalTemporalRelationship(first=first, second=second)
    same_relationship = OperationalTemporalRelationship(first=first, second=second)
    reversed_relationship = OperationalTemporalRelationship(first=second, second=first)

    assert relationship == same_relationship
    assert hash(relationship) == hash(same_relationship)
    assert relationship != reversed_relationship


def test_operational_temporal_relationship_outcome_is_derived_not_caller_supplied() -> None:
    first = make_dimension_association(EvidenceInstant(EVALUATED_AT))
    second = make_dimension_association(EvidenceInstant(EVALUATED_AT))

    with pytest.raises(TypeError):
        OperationalTemporalRelationship(
            first=first,
            second=second,
            outcome=OperationalTemporalRelationshipOutcome.TIMELESS_INVOLVED,
        )


def test_operational_temporal_relationship_does_not_mutate_inputs() -> None:
    first = make_dimension_association(
        EvidenceInstant(EVALUATED_AT),
        proposition="first activity was observed",
    )
    second = make_dimension_association(
        EvidenceInstant(EVALUATED_AT + timedelta(seconds=1)),
        proposition="second activity was observed",
    )

    OperationalTemporalRelationship(first=first, second=second)

    assert first == make_dimension_association(
        EvidenceInstant(EVALUATED_AT),
        proposition="first activity was observed",
    )
    assert second == make_dimension_association(
        EvidenceInstant(EVALUATED_AT + timedelta(seconds=1)),
        proposition="second activity was observed",
    )
