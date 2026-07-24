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
    OperationalConflictSet,
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
    return OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    )


def make_recognition(
    first_classification: EvidencePropositionClassification,
    second_classification: EvidencePropositionClassification,
    first_temporal_context: EvidenceTemporalContext,
    second_temporal_context: EvidenceTemporalContext,
    context: AdmissionEvaluationContext,
) -> OperationalConflictRecognition:
    compatibility = OperationalAssertionCompatibility(
        first=make_dimension_association(
            first_classification,
            first_temporal_context,
            context,
            "first proposition was observed",
        ),
        second=make_dimension_association(
            second_classification,
            second_temporal_context,
            context,
            "second proposition was observed",
        ),
    )
    return OperationalConflictRecognition(compatibility=compatibility)


def make_conflict_recognition(
    context: AdmissionEvaluationContext,
) -> OperationalConflictRecognition:
    return make_recognition(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
        context,
    )


def make_no_conflict_recognition(
    context: AdmissionEvaluationContext,
) -> OperationalConflictRecognition:
    return make_recognition(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        EvidenceInstant(EVALUATED_AT),
        context,
    )


def make_unresolved_recognition(
    context: AdmissionEvaluationContext,
) -> OperationalConflictRecognition:
    return make_recognition(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceTimeless(),
        EvidenceInstant(EVALUATED_AT),
        context,
    )


def test_operational_conflict_set_allows_empty_set() -> None:
    conflict_set = OperationalConflictSet(context=make_context())

    assert conflict_set.recognitions == frozenset()


@pytest.mark.parametrize(
    "recognition_factory",
    [
        make_conflict_recognition,
        make_no_conflict_recognition,
        make_unresolved_recognition,
    ],
)
def test_each_recognition_outcome_can_be_included(
    recognition_factory: object,
) -> None:
    context = make_context()
    recognition = recognition_factory(context)

    conflict_set = OperationalConflictSet(context, [recognition])

    assert conflict_set.recognitions == frozenset({recognition})


def test_mixed_outcomes_are_preserved() -> None:
    context = make_context()
    conflict = make_conflict_recognition(context)
    no_conflict = make_no_conflict_recognition(context)
    unresolved = make_unresolved_recognition(context)

    conflict_set = OperationalConflictSet(context, [conflict, no_conflict, unresolved])

    assert conflict_set.recognitions == frozenset({conflict, no_conflict, unresolved})
    assert {recognition.outcome for recognition in conflict_set.recognitions} == {
        OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_RECOGNIZED,
        OperationalConflictRecognitionOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED,
        OperationalConflictRecognitionOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED,
    }


def test_duplicates_collapse() -> None:
    context = make_context()
    recognition = make_conflict_recognition(context)

    conflict_set = OperationalConflictSet(context, [recognition, recognition])

    assert conflict_set.recognitions == frozenset({recognition})


def test_reverse_order_equivalent_recognitions_remain_one_member() -> None:
    context = make_context()
    first = make_dimension_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        context,
        "first proposition was observed",
    )
    second = make_dimension_association(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidenceInstant(EVALUATED_AT),
        context,
        "second proposition was observed",
    )
    recognition = OperationalConflictRecognition(
        compatibility=OperationalAssertionCompatibility(first=first, second=second)
    )
    reversed_recognition = OperationalConflictRecognition(
        compatibility=OperationalAssertionCompatibility(first=second, second=first)
    )

    conflict_set = OperationalConflictSet(context, [recognition, reversed_recognition])

    assert recognition == reversed_recognition
    assert conflict_set.recognitions == frozenset({recognition})


def test_mismatched_context_members_are_rejected() -> None:
    context = make_context()
    other_context = make_context(CONTEXT_EVALUATED_AT + timedelta(seconds=1))
    recognition = make_conflict_recognition(other_context)

    with pytest.raises(ValueError, match="context"):
        OperationalConflictSet(context, [recognition])


def test_input_order_does_not_affect_equality_or_hashing() -> None:
    context = make_context()
    conflict = make_conflict_recognition(context)
    no_conflict = make_no_conflict_recognition(context)

    conflict_set = OperationalConflictSet(context, [conflict, no_conflict])
    same_conflict_set = OperationalConflictSet(context, [no_conflict, conflict])

    assert conflict_set == same_conflict_set
    assert hash(conflict_set) == hash(same_conflict_set)


def test_changed_member_set_changes_identity() -> None:
    context = make_context()
    conflict = make_conflict_recognition(context)
    no_conflict = make_no_conflict_recognition(context)

    assert OperationalConflictSet(context, [conflict]) != (
        OperationalConflictSet(context, [conflict, no_conflict])
    )


def test_changed_context_changes_identity() -> None:
    context = make_context()
    other_context = make_context(CONTEXT_EVALUATED_AT + timedelta(seconds=1))

    assert OperationalConflictSet(context) != OperationalConflictSet(other_context)


def test_operational_conflict_set_is_immutable() -> None:
    conflict_set = OperationalConflictSet(context=make_context())

    with pytest.raises(FrozenInstanceError):
        conflict_set.recognitions = frozenset()


def test_operational_conflict_set_does_not_mutate_inputs() -> None:
    context = make_context()
    conflict = make_conflict_recognition(context)
    compatibility = conflict.compatibility
    associations = compatibility.associations

    OperationalConflictSet(context, [conflict])

    assert context == make_context()
    assert conflict == make_conflict_recognition(context)
    assert compatibility == conflict.compatibility
    assert associations == conflict.compatibility.associations
