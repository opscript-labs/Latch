from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EstablishedOperationalProposition,
    EstablishedOperationalPropositionSet,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionEstablishment,
    OperationalAssertionProjection,
)
from latch.domain.environment import Environment
from latch.domain.evidence import Evidence, EvidenceInstant, SourceProvenance

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def make_context(evaluated_at: datetime = EVALUATED_AT) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
        resource_target_arns={"arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"},
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=evaluated_at,
    )


def make_evidence(
    proposition: str,
    source_system: str,
    context: AdmissionEvaluationContext,
) -> Evidence:
    return Evidence(
        proposition=proposition,
        referent=context.environment.identifier,
        source_provenance=SourceProvenance(
            source_system=source_system,
            source_occurrence=f"{source_system}:{proposition}",
        ),
        temporal_context=EvidenceInstant(context.evaluated_at),
    )


def make_establishment(
    classification: EvidencePropositionClassification,
    context: AdmissionEvaluationContext,
    proposition: str = "operational proposition was observed",
) -> OperationalAssertionEstablishment:
    source_system = (
        "aws.cloudtrail.event"
        if classification is EvidencePropositionClassification.OPERATIONAL_ACTIVITY
        else "aws.cloudwatch.metrics"
    )
    evidence = make_evidence(
        proposition=proposition,
        source_system=source_system,
        context=context,
    )
    return OperationalAssertionEstablishment(
        projection=OperationalAssertionProjection(
            association=EvidencePropositionClassificationAssociation(
                evidence=evidence,
                classification=classification,
            ),
            context=context,
        )
    )


def make_establishes_nothing(
    context: AdmissionEvaluationContext,
) -> OperationalAssertionEstablishment:
    evidence = make_evidence(
        proposition="unclassified proposition was observed",
        source_system="aws.cloudtrail.event",
        context=context,
    )
    return OperationalAssertionEstablishment(
        projection=OperationalAssertionProjection(
            association=EvidencePropositionClassificationAssociation(
                evidence=evidence,
                classification=EvidencePropositionClassification.UNCLASSIFIED,
            ),
            context=context,
        )
    )


def test_established_operational_proposition_has_exact_closed_members() -> None:
    assert list(EstablishedOperationalProposition) == [
        EstablishedOperationalProposition.OPERATIONAL_ACTIVITY,
        EstablishedOperationalProposition.OPERATIONAL_INACTIVITY,
    ]


def test_established_operational_proposition_set_allows_empty_aggregate() -> None:
    aggregate = EstablishedOperationalPropositionSet(context=make_context())

    assert aggregate.supporting_establishments == frozenset()
    assert aggregate.members == frozenset()


def test_established_operational_proposition_set_contains_activity_member() -> None:
    context = make_context()
    support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
    )

    aggregate = EstablishedOperationalPropositionSet(context, [support])

    assert aggregate.members == frozenset(
        {EstablishedOperationalProposition.OPERATIONAL_ACTIVITY}
    )
    assert aggregate.supporting_establishments == frozenset({support})


def test_established_operational_proposition_set_contains_inactivity_member() -> None:
    context = make_context()
    support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        context,
    )

    aggregate = EstablishedOperationalPropositionSet(context, [support])

    assert aggregate.members == frozenset(
        {EstablishedOperationalProposition.OPERATIONAL_INACTIVITY}
    )
    assert aggregate.supporting_establishments == frozenset({support})


def test_duplicate_supports_for_one_proposition_retain_multiple_supports() -> None:
    context = make_context()
    first_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
        proposition="cloudtrail start event was observed",
    )
    second_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
        proposition="cloudtrail update event was observed",
    )

    aggregate = EstablishedOperationalPropositionSet(
        context,
        [first_support, second_support],
    )

    assert aggregate.members == frozenset(
        {EstablishedOperationalProposition.OPERATIONAL_ACTIVITY}
    )
    assert aggregate.supporting_establishments == frozenset({first_support, second_support})


def test_activity_and_inactivity_members_may_coexist() -> None:
    context = make_context()
    activity_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
    )
    inactivity_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        context,
    )

    aggregate = EstablishedOperationalPropositionSet(
        context,
        [activity_support, inactivity_support],
    )

    assert aggregate.members == frozenset(
        {
            EstablishedOperationalProposition.OPERATIONAL_ACTIVITY,
            EstablishedOperationalProposition.OPERATIONAL_INACTIVITY,
        }
    )


def test_established_operational_proposition_set_rejects_establishes_nothing() -> None:
    context = make_context()

    with pytest.raises(ValueError, match="ESTABLISHES_NOTHING"):
        EstablishedOperationalPropositionSet(context, [make_establishes_nothing(context)])


def test_established_operational_proposition_set_rejects_different_context_support() -> None:
    context = make_context()
    other_context = make_context(EVALUATED_AT + timedelta(seconds=1))
    support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        other_context,
    )

    with pytest.raises(ValueError, match="context"):
        EstablishedOperationalPropositionSet(context, [support])


def test_input_order_does_not_affect_equality_or_hashing() -> None:
    context = make_context()
    activity_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
    )
    inactivity_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        context,
    )

    aggregate = EstablishedOperationalPropositionSet(
        context,
        [activity_support, inactivity_support],
    )
    same_aggregate = EstablishedOperationalPropositionSet(
        context,
        [inactivity_support, activity_support],
    )

    assert aggregate == same_aggregate
    assert hash(aggregate) == hash(same_aggregate)


def test_changed_support_set_produces_distinct_aggregate() -> None:
    context = make_context()
    first_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
        proposition="cloudtrail start event was observed",
    )
    second_support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
        proposition="cloudtrail update event was observed",
    )

    assert EstablishedOperationalPropositionSet(context, [first_support]) != (
        EstablishedOperationalPropositionSet(context, [first_support, second_support])
    )


def test_changed_context_produces_distinct_aggregate() -> None:
    context = make_context()
    other_context = make_context(EVALUATED_AT + timedelta(seconds=1))

    assert EstablishedOperationalPropositionSet(context) != (
        EstablishedOperationalPropositionSet(other_context)
    )


def test_established_operational_proposition_set_is_immutable() -> None:
    aggregate = EstablishedOperationalPropositionSet(context=make_context())

    with pytest.raises(FrozenInstanceError):
        aggregate.supporting_establishments = frozenset()


def test_established_operational_proposition_set_does_not_mutate_inputs() -> None:
    context = make_context()
    support = make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
    )
    projection = support.projection
    association = projection.association
    evidence = association.evidence

    EstablishedOperationalPropositionSet(context, [support])

    assert context == make_context()
    assert evidence == association.evidence
    assert association == projection.association
    assert projection == support.projection
    assert support == make_establishment(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        context,
    )
