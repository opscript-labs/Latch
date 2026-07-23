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
    RegisteredTargetOperationalEvidenceCoverage,
    RegisteredTargetOperationalEvidenceCoverageOutcome,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
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
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


def make_environment(
    environment_identifier: str = "env-123",
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
) -> Environment:
    return Environment(
        identifier=environment_identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=resource_target_arns,
    )


def make_claim(
    environment: Environment | None = None,
    claim_time: datetime = EVALUATED_AT,
) -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(environment or make_environment(), claim_time)


def make_context(
    environment_identifier: str = "env-123",
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
    evaluated_at: datetime = EVALUATED_AT,
    environment: Environment | None = None,
) -> AdmissionEvaluationContext:
    if environment is None:
        environment = make_environment(environment_identifier, resource_target_arns)

    return AdmissionEvaluationContext(
        environment=environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=evaluated_at,
    )


def make_association(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    classification: EvidencePropositionClassification,
    proposition: str,
    temporal_context: EvidenceTemporalContext | None = None,
    referent: str | None = None,
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
        referent=referent or next(iter(context.environment.resource_target_arns)),
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
    referent: str | None = None,
) -> OperationalDimensionAssociation:
    return make_association(
        context,
        dimension,
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        proposition,
        temporal_context,
        referent,
    )


def make_inactivity(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    proposition: str,
    temporal_context: EvidenceTemporalContext | None = None,
    referent: str | None = None,
) -> OperationalDimensionAssociation:
    return make_association(
        context,
        dimension,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        proposition,
        temporal_context,
        referent,
    )


def make_association_set(
    context: AdmissionEvaluationContext,
    associations: list[OperationalDimensionAssociation],
) -> OperationalDimensionAssociationSet:
    return OperationalDimensionAssociationSet(context, associations)


def make_coverage(
    claim: RetirementEvaluationClaim,
    association_set: OperationalDimensionAssociationSet,
) -> RegisteredTargetOperationalEvidenceCoverage:
    return RegisteredTargetOperationalEvidenceCoverage(claim, association_set)


def make_readiness(
    claim: RetirementEvaluationClaim,
    association_set: OperationalDimensionAssociationSet,
) -> OperationalRetirementReadiness:
    return OperationalRetirementReadiness(make_coverage(claim, association_set))


def make_readiness_for_set(
    association_set: OperationalDimensionAssociationSet,
) -> OperationalRetirementReadiness:
    claim = make_claim(
        association_set.context.environment,
        association_set.context.evaluated_at,
    )
    return make_readiness(claim, association_set)


def test_operational_retirement_readiness_has_exact_closed_vocabulary() -> None:
    assert list(OperationalRetirementReadinessOutcome) == [
        OperationalRetirementReadinessOutcome.READY,
        OperationalRetirementReadinessOutcome.NOT_READY,
        OperationalRetirementReadinessOutcome.UNRESOLVED,
    ]


def test_registered_target_operational_evidence_coverage_has_exact_closed_vocabulary() -> None:
    assert list(RegisteredTargetOperationalEvidenceCoverageOutcome) == [
        RegisteredTargetOperationalEvidenceCoverageOutcome.COMPLETE,
        RegisteredTargetOperationalEvidenceCoverageOutcome.INCOMPLETE,
    ]


def test_complete_cpu_and_network_inactivity_coverage_across_all_targets_is_complete() -> None:
    environment = make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    claim = make_claim(environment)
    context = make_context(environment=environment)
    association_set = make_association_set(
        context,
        [
            make_inactivity(
                context,
                OperationalDimension.CPU_ACTIVITY,
                "first cpu inactive",
                referent=FIRST_TARGET,
            ),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "first network inactive",
                referent=FIRST_TARGET,
            ),
            make_inactivity(
                context,
                OperationalDimension.CPU_ACTIVITY,
                "second cpu inactive",
                referent=SECOND_TARGET,
            ),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "second network inactive",
                referent=SECOND_TARGET,
            ),
        ],
    )

    coverage = make_coverage(claim, association_set)
    readiness = OperationalRetirementReadiness(coverage)

    assert coverage.outcome is RegisteredTargetOperationalEvidenceCoverageOutcome.COMPLETE
    assert readiness.outcome is OperationalRetirementReadinessOutcome.READY


@pytest.mark.parametrize(
    "associations",
    [
        [
            (OperationalDimension.NETWORK_ACTIVITY, FIRST_TARGET, "first network inactive"),
        ],
        [
            (OperationalDimension.CPU_ACTIVITY, FIRST_TARGET, "first cpu inactive"),
        ],
        [
            (OperationalDimension.CPU_ACTIVITY, FIRST_TARGET, "first cpu inactive"),
            (OperationalDimension.NETWORK_ACTIVITY, FIRST_TARGET, "first network inactive"),
            (OperationalDimension.CPU_ACTIVITY, SECOND_TARGET, "second cpu inactive"),
        ],
    ],
)
def test_missing_cpu_or_network_inactivity_coverage_is_incomplete_and_unresolved(
    associations: list[tuple[OperationalDimension, str, str]],
) -> None:
    environment = make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    claim = make_claim(environment)
    context = make_context(environment=environment)
    association_set = make_association_set(
        context,
        [
            make_inactivity(context, dimension, proposition, referent=referent)
            for dimension, referent, proposition in associations
        ],
    )

    coverage = make_coverage(claim, association_set)
    readiness = OperationalRetirementReadiness(coverage)

    assert coverage.outcome is RegisteredTargetOperationalEvidenceCoverageOutcome.INCOMPLETE
    assert readiness.outcome is OperationalRetirementReadinessOutcome.UNRESOLVED


def test_association_for_target_a_cannot_cover_target_b() -> None:
    environment = make_environment(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    claim = make_claim(environment)
    context = make_context(environment=environment)
    association_set = make_association_set(
        context,
        [
            make_inactivity(
                context,
                OperationalDimension.CPU_ACTIVITY,
                "first cpu inactive",
                referent=FIRST_TARGET,
            ),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "first network inactive",
                referent=FIRST_TARGET,
            ),
        ],
    )

    coverage = make_coverage(claim, association_set)

    assert coverage.outcome is RegisteredTargetOperationalEvidenceCoverageOutcome.INCOMPLETE


def test_multiple_qualifying_supports_for_one_target_dimension_do_not_add_requirements() -> None:
    environment = make_environment()
    claim = make_claim(environment)
    context = make_context(environment=environment)
    first_cpu = make_inactivity(
        context,
        OperationalDimension.CPU_ACTIVITY,
        "first cpu inactive",
        referent=FIRST_TARGET,
    )
    second_cpu = make_inactivity(
        context,
        OperationalDimension.CPU_ACTIVITY,
        "second cpu inactive",
        referent=FIRST_TARGET,
    )
    network = make_inactivity(
        context,
        OperationalDimension.NETWORK_ACTIVITY,
        "network inactive",
        referent=FIRST_TARGET,
    )
    association_set = make_association_set(context, [first_cpu, second_cpu, network])

    coverage = make_coverage(claim, association_set)

    assert coverage.outcome is RegisteredTargetOperationalEvidenceCoverageOutcome.COMPLETE
    assert coverage.association_set.associations == frozenset({first_cpu, second_cpu, network})


def test_claim_and_context_environment_mismatch_is_rejected() -> None:
    claim = make_claim(make_environment("env-123"))
    context = make_context(environment=make_environment("env-456"))
    association_set = make_association_set(context, [])

    with pytest.raises(ValueError, match="Environment"):
        make_coverage(claim, association_set)


def test_claim_time_and_context_evaluated_at_mismatch_is_rejected() -> None:
    environment = make_environment()
    claim = make_claim(environment, EVALUATED_AT)
    context = make_context(
        environment=environment,
        evaluated_at=datetime(2026, 7, 23, 11, 1, tzinfo=UTC),
    )
    association_set = make_association_set(context, [])

    with pytest.raises(ValueError, match="evaluated_at"):
        make_coverage(claim, association_set)


def test_partial_supplied_association_sets_are_valid_but_incomplete() -> None:
    environment = make_environment()
    claim = make_claim(environment)
    context = make_context(environment=environment)
    association_set = make_association_set(
        context,
        [
            make_inactivity(
                context,
                OperationalDimension.CPU_ACTIVITY,
                "cpu inactive",
                referent=FIRST_TARGET,
            )
        ],
    )

    coverage = make_coverage(claim, association_set)

    assert coverage.outcome is RegisteredTargetOperationalEvidenceCoverageOutcome.INCOMPLETE


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

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.UNRESOLVED


def test_missing_network_association_is_unresolved() -> None:
    context = make_context()
    association_set = make_association_set(
        context,
        [make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")],
    )

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

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

    readiness = make_readiness_for_set(association_set)

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

    claim = make_claim(context.environment, context.evaluated_at)
    readiness = make_readiness(claim, association_set)
    same_readiness = make_readiness(claim, association_set)

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

    claim = make_claim(context.environment, context.evaluated_at)

    assert make_readiness(claim, make_association_set(context, [cpu, network])) == (
        make_readiness(claim, make_association_set(context, [network, cpu]))
    )


def test_changed_association_set_produces_distinct_readiness() -> None:
    context = make_context()
    cpu = make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
    network = make_inactivity(
        context,
        OperationalDimension.NETWORK_ACTIVITY,
        "network inactive",
    )

    claim = make_claim(context.environment, context.evaluated_at)

    assert make_readiness(claim, make_association_set(context, [cpu])) != (
        make_readiness(claim, make_association_set(context, [cpu, network]))
    )


def test_derived_fields_and_outcome_cannot_be_caller_supplied() -> None:
    context = make_context()
    association_set = make_association_set(context, [])

    with pytest.raises(TypeError):
        OperationalRetirementReadiness(
            target_coverage=make_coverage(make_claim(context.environment), association_set),
            outcome=OperationalRetirementReadinessOutcome.READY,
        )

    with pytest.raises(TypeError):
        OperationalRetirementReadiness(
            target_coverage=make_coverage(make_claim(context.environment), association_set),
            association_set=object(),
        )

    with pytest.raises(TypeError):
        OperationalRetirementReadiness(
            target_coverage=make_coverage(make_claim(context.environment), association_set),
            conflict_status=object(),
        )


def test_operational_retirement_readiness_is_immutable() -> None:
    readiness = make_readiness_for_set(make_association_set(make_context(), []))

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

    make_readiness_for_set(association_set)

    assert association_set.associations == associations
    assert association_set.required_comparison_pairs == required_pairs
    assert cpu in association_set.associations
    assert network in association_set.associations
