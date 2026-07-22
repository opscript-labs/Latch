from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

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
    OperationalConflictRecognitionCoverage,
    OperationalConflictRecognitionOutcome,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalDimensionAssociationSet,
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


def make_context() -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
        resource_target_arns={"arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api"},
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=CONTEXT_EVALUATED_AT,
    )


def make_association(
    classification: EvidencePropositionClassification,
    temporal_context: EvidenceTemporalContext,
    dimension: OperationalDimension,
    context: AdmissionEvaluationContext,
    proposition: str,
) -> OperationalDimensionAssociation:
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
    proposition: str,
    dimension: OperationalDimension,
    context: AdmissionEvaluationContext,
    temporal_context: EvidenceTemporalContext | None = None,
) -> OperationalDimensionAssociation:
    if temporal_context is None:
        temporal_context = EvidenceInstant(EVALUATED_AT)

    return make_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        temporal_context,
        dimension,
        context,
        proposition,
    )


def make_inactivity(
    proposition: str,
    dimension: OperationalDimension,
    context: AdmissionEvaluationContext,
    temporal_context: EvidenceTemporalContext | None = None,
) -> OperationalDimensionAssociation:
    if temporal_context is None:
        temporal_context = EvidenceInstant(EVALUATED_AT)

    return make_association(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        temporal_context,
        dimension,
        context,
        proposition,
    )


def expected_recognition(
    first: OperationalDimensionAssociation,
    second: OperationalDimensionAssociation,
) -> OperationalConflictRecognition:
    return OperationalConflictRecognition(
        compatibility=OperationalAssertionCompatibility(first=first, second=second)
    )


def test_empty_association_set_produces_empty_coverage() -> None:
    coverage = OperationalConflictRecognitionCoverage(
        association_set=OperationalDimensionAssociationSet(context=make_context())
    )

    assert coverage.recognitions == frozenset()


def test_single_association_set_produces_empty_coverage() -> None:
    context = make_context()
    association = make_activity("cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    coverage = OperationalConflictRecognitionCoverage(
        association_set=OperationalDimensionAssociationSet(context, [association])
    )

    assert coverage.recognitions == frozenset()


def test_every_required_same_dimension_pair_produces_one_recognition() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    association_set = OperationalDimensionAssociationSet(context, [first, second])

    coverage = OperationalConflictRecognitionCoverage(association_set=association_set)

    assert coverage.recognitions == frozenset({expected_recognition(first, second)})


def test_multiple_same_dimension_associations_produce_complete_pair_coverage() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_activity("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    third = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    association_set = OperationalDimensionAssociationSet(context, [first, second, third])

    coverage = OperationalConflictRecognitionCoverage(association_set=association_set)

    assert coverage.recognitions == frozenset(
        {
            expected_recognition(first, second),
            expected_recognition(first, third),
            expected_recognition(second, third),
        }
    )


def test_mixed_dimensions_exclude_cross_dimension_results() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    network = make_activity(
        "network activity",
        OperationalDimension.NETWORK_ACTIVITY,
        context,
    )
    association_set = OperationalDimensionAssociationSet(context, [first, second, network])

    coverage = OperationalConflictRecognitionCoverage(association_set=association_set)

    assert coverage.recognitions == frozenset({expected_recognition(first, second)})


def test_reverse_order_equivalent_pairs_do_not_duplicate_results() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    association_set = OperationalDimensionAssociationSet(context, [second, first])

    coverage = OperationalConflictRecognitionCoverage(association_set=association_set)

    assert coverage.recognitions == frozenset({expected_recognition(first, second)})


def test_derived_recognitions_match_existing_chain_behavior() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    association_set = OperationalDimensionAssociationSet(context, [first, second])

    coverage = OperationalConflictRecognitionCoverage(association_set=association_set)
    recognition = next(iter(coverage.recognitions))
    expected = expected_recognition(first, second)

    assert recognition == expected
    assert recognition.compatibility == expected.compatibility
    assert recognition.outcome == expected.outcome


def test_each_approved_recognition_outcome_can_occur_in_coverage() -> None:
    context = make_context()
    activity = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    inactivity = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    compatible = make_activity("second cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    unresolved = make_inactivity(
        "timeless cpu inactivity",
        OperationalDimension.CPU_ACTIVITY,
        context,
        temporal_context=EvidenceTimeless(),
    )
    association_set = OperationalDimensionAssociationSet(
        context,
        [activity, inactivity, compatible, unresolved],
    )

    coverage = OperationalConflictRecognitionCoverage(association_set=association_set)

    assert {recognition.outcome for recognition in coverage.recognitions} == {
        OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_RECOGNIZED,
        OperationalConflictRecognitionOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED,
        OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED,
    }


def test_identity_and_hashing_depend_only_on_association_set() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    association_set = OperationalDimensionAssociationSet(context, [first, second])

    coverage = OperationalConflictRecognitionCoverage(association_set=association_set)
    same_coverage = OperationalConflictRecognitionCoverage(association_set=association_set)

    assert coverage == same_coverage
    assert hash(coverage) == hash(same_coverage)


def test_equivalent_association_sets_produce_equal_coverage() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)

    assert OperationalConflictRecognitionCoverage(
        OperationalDimensionAssociationSet(context, [first, second])
    ) == OperationalConflictRecognitionCoverage(
        OperationalDimensionAssociationSet(context, [second, first])
    )


def test_changed_association_set_produces_distinct_coverage() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)

    assert OperationalConflictRecognitionCoverage(
        OperationalDimensionAssociationSet(context, [first])
    ) != OperationalConflictRecognitionCoverage(
        OperationalDimensionAssociationSet(context, [first, second])
    )


def test_recognition_results_cannot_be_caller_supplied() -> None:
    context = make_context()
    association_set = OperationalDimensionAssociationSet(context)

    with pytest.raises(TypeError):
        OperationalConflictRecognitionCoverage(
            association_set=association_set,
            recognitions=frozenset(),
        )


def test_operational_conflict_recognition_coverage_is_immutable() -> None:
    coverage = OperationalConflictRecognitionCoverage(
        association_set=OperationalDimensionAssociationSet(context=make_context())
    )

    with pytest.raises(FrozenInstanceError):
        coverage.recognitions = frozenset()


def test_operational_conflict_recognition_coverage_does_not_mutate_inputs() -> None:
    context = make_context()
    first = make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    second = make_inactivity("first cpu inactivity", OperationalDimension.CPU_ACTIVITY, context)
    association_set = OperationalDimensionAssociationSet(context, [first, second])
    associations = association_set.associations

    OperationalConflictRecognitionCoverage(association_set=association_set)

    assert association_set == OperationalDimensionAssociationSet(context, [first, second])
    assert association_set.associations == associations
    assert first == make_activity("first cpu activity", OperationalDimension.CPU_ACTIVITY, context)
    assert second == make_inactivity(
        "first cpu inactivity",
        OperationalDimension.CPU_ACTIVITY,
        context,
    )
