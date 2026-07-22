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
    OperationalDimensionAssociationSet,
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
        resource_target_arns={"arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api"},
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )


def make_association(
    proposition: str,
    dimension: OperationalDimension,
    context: AdmissionEvaluationContext,
) -> OperationalDimensionAssociation:
    evidence = Evidence(
        proposition=proposition,
        referent=context.environment.identifier,
        source_provenance=SourceProvenance(
            source_system="aws.cloudtrail.event",
            source_occurrence=f"aws.cloudtrail.event:{proposition}",
        ),
        temporal_context=EvidenceInstant(EVALUATED_AT),
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


def test_empty_set_is_valid_and_has_no_required_pairs() -> None:
    association_set = OperationalDimensionAssociationSet(context=make_context())

    assert association_set.associations == frozenset()
    assert association_set.required_comparison_pairs == ()


def test_single_association_has_no_required_pairs() -> None:
    context = make_context()
    association = make_association(
        "cpu activity was observed",
        OperationalDimension.CPU_ACTIVITY,
        context,
    )

    association_set = OperationalDimensionAssociationSet(context, [association])

    assert association_set.associations == frozenset({association})
    assert association_set.required_comparison_pairs == ()


def test_same_dimension_distinct_associations_produce_one_unordered_pair() -> None:
    context = make_context()
    first = make_association("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_association("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)

    association_set = OperationalDimensionAssociationSet(context, [first, second])

    assert association_set.required_comparison_pairs == (frozenset({first, second}),)


def test_multiple_same_dimension_associations_produce_every_distinct_pair_once() -> None:
    context = make_context()
    first = make_association("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_association("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    third = make_association("third cpu activity", OperationalDimension.CPU_ACTIVITY, context)

    association_set = OperationalDimensionAssociationSet(context, [first, second, third])

    assert set(association_set.required_comparison_pairs) == {
        frozenset({first, second}),
        frozenset({first, third}),
        frozenset({second, third}),
    }
    assert len(association_set.required_comparison_pairs) == 3


def test_mixed_dimensions_exclude_cross_dimension_pairs() -> None:
    context = make_context()
    first_cpu = make_association("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second_cpu = make_association("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    network = make_association(
        "network activity",
        OperationalDimension.NETWORK_ACTIVITY,
        context,
    )

    association_set = OperationalDimensionAssociationSet(
        context,
        [first_cpu, second_cpu, network],
    )

    assert association_set.required_comparison_pairs == (frozenset({first_cpu, second_cpu}),)


def test_duplicate_associations_collapse() -> None:
    context = make_context()
    association = make_association(
        "cpu activity was observed",
        OperationalDimension.CPU_ACTIVITY,
        context,
    )

    association_set = OperationalDimensionAssociationSet(context, [association, association])

    assert association_set.associations == frozenset({association})


def test_mismatched_context_associations_are_rejected() -> None:
    context = make_context("env-123")
    other_context = make_context("env-456")
    association = make_association(
        "cpu activity was observed",
        OperationalDimension.CPU_ACTIVITY,
        other_context,
    )

    with pytest.raises(ValueError, match="context"):
        OperationalDimensionAssociationSet(context, [association])


def test_input_order_does_not_affect_identity_hashing_or_pair_coverage() -> None:
    context = make_context()
    first = make_association("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_association("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    third = make_association("third cpu activity", OperationalDimension.CPU_ACTIVITY, context)

    association_set = OperationalDimensionAssociationSet(context, [first, second, third])
    same_association_set = OperationalDimensionAssociationSet(context, [third, first, second])

    assert association_set == same_association_set
    assert hash(association_set) == hash(same_association_set)
    assert association_set.required_comparison_pairs == (
        same_association_set.required_comparison_pairs
    )


def test_required_pair_enumeration_is_deterministic() -> None:
    context = make_context()
    first = make_association("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_association("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    third = make_association("third cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    association_set = OperationalDimensionAssociationSet(context, [third, first, second])

    assert association_set.required_comparison_pairs == association_set.required_comparison_pairs
    same_set = OperationalDimensionAssociationSet(context, [second, third, first])
    assert (
        association_set.required_comparison_pairs
        == same_set.required_comparison_pairs
    )


def test_changed_members_change_identity() -> None:
    context = make_context()
    first = make_association("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_association("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)

    assert OperationalDimensionAssociationSet(context, [first]) != (
        OperationalDimensionAssociationSet(context, [first, second])
    )


def test_changed_context_changes_identity() -> None:
    assert OperationalDimensionAssociationSet(make_context("env-123")) != (
        OperationalDimensionAssociationSet(make_context("env-456"))
    )


def test_operational_dimension_association_set_is_immutable() -> None:
    association_set = OperationalDimensionAssociationSet(context=make_context())

    with pytest.raises(FrozenInstanceError):
        association_set.associations = frozenset()


def test_operational_dimension_association_set_does_not_mutate_inputs() -> None:
    context = make_context()
    association = make_association(
        "cpu activity was observed",
        OperationalDimension.CPU_ACTIVITY,
        context,
    )
    establishment = association.establishment
    projection = establishment.projection
    evidence = projection.association.evidence

    OperationalDimensionAssociationSet(context, [association])

    assert context == make_context()
    assert evidence == projection.association.evidence
    assert projection == establishment.projection
    assert establishment == association.establishment
    assert association == make_association(
        "cpu activity was observed",
        OperationalDimension.CPU_ACTIVITY,
        context,
    )
