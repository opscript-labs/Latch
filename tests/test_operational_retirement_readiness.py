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
    OperationalConflictStatusOutcome,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalDimensionAssociationSet,
    OperationalRetirementReadiness,
    OperationalRetirementReadinessOutcome,
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
EVIDENCE_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 11, 0, tzinfo=UTC)


def make_context(environment_identifier: str = "env-123") -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier=environment_identifier,
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )


def make_association(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    classification: EvidencePropositionClassification,
    proposition: str,
    temporal_context: EvidenceTemporalContext | None = None,
) -> OperationalDimensionAssociation:
    if temporal_context is None:
        temporal_context = EvidenceInstant(EVIDENCE_AT)

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
        dimension=dimension,
    )


def make_activity(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    proposition: str,
    temporal_context: EvidenceTemporalContext | None = None,
) -> OperationalDimensionAssociation:
    return make_association(
        context,
        dimension,
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        proposition,
        temporal_context,
    )


def make_inactivity(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    proposition: str,
    temporal_context: EvidenceTemporalContext | None = None,
) -> OperationalDimensionAssociation:
    return make_association(
        context,
        dimension,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        proposition,
        temporal_context,
    )


def make_association_set(
    context: AdmissionEvaluationContext,
    associations: list[OperationalDimensionAssociation],
) -> OperationalDimensionAssociationSet:
    return OperationalDimensionAssociationSet(context, associations)


def test_operational_retirement_readiness_has_exact_closed_vocabulary() -> None:
    assert list(OperationalRetirementReadinessOutcome) == [
        OperationalRetirementReadinessOutcome.READY,
        OperationalRetirementReadinessOutcome.NOT_READY,
        OperationalRetirementReadinessOutcome.UNRESOLVED,
    ]


def test_cpu_and_network_inactivity_without_deployment_activity_is_ready() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.READY


def test_cpu_activity_is_not_ready() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_activity(context, OperationalDimension.CPU_ACTIVITY, "cpu active"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.NOT_READY


def test_network_activity_is_not_ready() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_activity(context, OperationalDimension.NETWORK_ACTIVITY, "network active"),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.NOT_READY


def test_deployment_activity_is_not_ready() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
            make_activity(
                context,
                OperationalDimension.DEPLOYMENT_ACTIVITY,
                "deployment active",
            ),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.NOT_READY


def test_missing_cpu_association_is_unresolved() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            )
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.UNRESOLVED


def test_missing_network_association_is_unresolved() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.UNRESOLVED


def test_aggregate_recognized_conflict_is_not_ready() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_activity(context, OperationalDimension.CPU_ACTIVITY, "cpu active"),
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.NOT_READY


def test_aggregate_unresolved_conflict_with_activity_is_not_ready() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_activity(
                context,
                OperationalDimension.CPU_ACTIVITY,
                "timeless cpu active",
                EvidenceTimeless(),
            ),
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert (
        readiness.conflict_status.outcome
        is OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED
    )
    assert readiness.outcome is OperationalRetirementReadinessOutcome.NOT_READY


def test_disqualifying_conditions_take_precedence_over_unresolved_conditions() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [make_activity(context, OperationalDimension.CPU_ACTIVITY, "cpu active")],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.NOT_READY


def test_deployment_absence_does_not_make_readiness_unresolved() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.READY


def test_identity_and_hashing_depend_only_on_association_set() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
        ],
    )

    readiness = OperationalRetirementReadiness(association_set)
    same_readiness = OperationalRetirementReadiness(association_set)

    assert readiness == same_readiness
    assert hash(readiness) == hash(same_readiness)


def test_equivalent_association_sets_produce_equal_readiness() -> None:
    context = make_context()
    cpu = make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
    network = make_inactivity(
        context,
        OperationalDimension.NETWORK_ACTIVITY,
        "network inactive",
    )

    assert OperationalRetirementReadiness(make_association_set(context, [cpu, network])) == (
        OperationalRetirementReadiness(make_association_set(context, [network, cpu]))
    )


def test_changed_association_set_produces_distinct_readiness() -> None:
    context = make_context()
    cpu = make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
    network = make_inactivity(
        context,
        OperationalDimension.NETWORK_ACTIVITY,
        "network inactive",
    )

    assert OperationalRetirementReadiness(make_association_set(context, [cpu])) != (
        OperationalRetirementReadiness(make_association_set(context, [cpu, network]))
    )


def test_derived_fields_and_outcome_cannot_be_caller_supplied() -> None:
    context = make_context()
    association_set = make_association_set(context, [])

    with pytest.raises(TypeError):
        OperationalRetirementReadiness(
            association_set=association_set,
            outcome=OperationalRetirementReadinessOutcome.READY,
        )

    with pytest.raises(TypeError):
        OperationalRetirementReadiness(
            association_set=association_set,
            coverage=object(),
        )

    with pytest.raises(TypeError):
        OperationalRetirementReadiness(
            association_set=association_set,
            conflict_status=object(),
        )


def test_operational_retirement_readiness_is_immutable() -> None:
    readiness = OperationalRetirementReadiness(
        make_association_set(make_context(), [])
    )

    with pytest.raises(FrozenInstanceError):
        readiness.outcome = OperationalRetirementReadinessOutcome.READY


def test_operational_retirement_readiness_does_not_mutate_upstream_artifacts() -> None:
    context = make_context()
    cpu = make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
    network = make_inactivity(
        context,
        OperationalDimension.NETWORK_ACTIVITY,
        "network inactive",
    )
    association_set = make_association_set(context, [cpu, network])
    associations = association_set.associations
    required_pairs = association_set.required_comparison_pairs

    OperationalRetirementReadiness(association_set)

    assert association_set.associations == associations
    assert association_set.required_comparison_pairs == required_pairs
    assert cpu in association_set.associations
    assert network in association_set.associations
