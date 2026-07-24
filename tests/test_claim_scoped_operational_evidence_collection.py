from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

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
    OperationalRetirementReadiness,
    OperationalRetirementReadinessOutcome,
    RegisteredTargetOperationalEvidenceCoverageOutcome,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import Evidence, EvidenceInterval, SourceProvenance
from latch.infrastructure.claim_scoped_operational_evidence_collection import (
    ClaimScopedOperationalEvidenceCollection,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
CLAIM_TIME = datetime(2026, 7, 23, 10, 2, 17, tzinfo=UTC)
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


def make_claim(
    resource_target_arns: frozenset[str] = frozenset({SECOND_TARGET, FIRST_TARGET}),
) -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns=resource_target_arns,
        ),
        CLAIM_TIME,
    )


def make_association(
    context: AdmissionEvaluationContext,
    target_arn: str,
    dimension: OperationalDimension,
) -> OperationalDimensionAssociation:
    association = EvidencePropositionClassificationAssociation(
        evidence=Evidence(
            proposition=f"{dimension.value} inactivity for {target_arn}",
            referent=target_arn,
            source_provenance=SourceProvenance(
                source_system="aws.cloudwatch.metrics",
                source_occurrence=f"{dimension.value}:{target_arn}",
            ),
            temporal_context=EvidenceInterval(
                CLAIM_TIME - timedelta(minutes=30),
                CLAIM_TIME,
            ),
        ),
        classification=EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
    )
    return OperationalDimensionAssociation(
        OperationalAssertionEstablishment(OperationalAssertionProjection(association, context)),
        dimension,
    )


class ProgressionStub:
    def __init__(
        self,
        dimension: OperationalDimension,
        affirmative_targets: frozenset[str],
        failure_by_target: dict[str, BaseException] | None = None,
    ) -> None:
        self.dimension = dimension
        self.affirmative_targets = affirmative_targets
        self.failure_by_target = failure_by_target or {}
        self.calls: list[tuple[RetirementEvaluationClaim, str, AdmissionEvaluationContext]] = []

    def progress(
        self,
        claim: RetirementEvaluationClaim,
        target_arn: str,
        context: AdmissionEvaluationContext,
    ) -> OperationalDimensionAssociation | None:
        self.calls.append((claim, target_arn, context))
        if target_arn in self.failure_by_target:
            raise self.failure_by_target[target_arn]

        if target_arn not in self.affirmative_targets:
            return None

        return make_association(context, target_arn, self.dimension)


def collect_with_stubs(
    claim: RetirementEvaluationClaim,
    cpu_progression: ProgressionStub,
    network_progression: ProgressionStub,
) -> OperationalRetirementReadiness:
    return ClaimScopedOperationalEvidenceCollection(
        cpu_progression=cpu_progression,
        network_progression=network_progression,
    ).collect(claim)


def test_all_cpu_and_network_affirmative_across_all_targets_produces_ready_readiness() -> None:
    claim = make_claim()
    cpu = ProgressionStub(OperationalDimension.CPU_ACTIVITY, claim.environment.resource_target_arns)
    network = ProgressionStub(
        OperationalDimension.NETWORK_ACTIVITY,
        claim.environment.resource_target_arns,
    )

    readiness = collect_with_stubs(claim, cpu, network)

    assert readiness.outcome is OperationalRetirementReadinessOutcome.READY
    assert (
        readiness.target_coverage.outcome
        is RegisteredTargetOperationalEvidenceCoverageOutcome.COMPLETE
    )
    assert len(readiness.association_set.associations) == 4


def test_exactly_one_context_is_used_for_every_retained_association() -> None:
    claim = make_claim()
    cpu = ProgressionStub(OperationalDimension.CPU_ACTIVITY, claim.environment.resource_target_arns)
    network = ProgressionStub(
        OperationalDimension.NETWORK_ACTIVITY,
        claim.environment.resource_target_arns,
    )

    readiness = collect_with_stubs(claim, cpu, network)

    contexts = [call[2] for call in [*cpu.calls, *network.calls]]
    assert len({id(context) for context in contexts}) == 1
    shared_context = contexts[0]
    assert shared_context.environment == claim.environment
    assert shared_context.requested_retirement is AdmissionRequest.RETIREMENT
    assert shared_context.evaluated_at == claim.claim_time
    assert readiness.association_set.context is shared_context
    assert all(
        association.establishment.projection.context is shared_context
        for association in readiness.association_set.associations
    )


def test_target_traversal_is_lexicographic_and_identity_is_order_independent() -> None:
    claim = make_claim()
    reversed_claim = make_claim(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    cpu = ProgressionStub(OperationalDimension.CPU_ACTIVITY, claim.environment.resource_target_arns)
    network = ProgressionStub(
        OperationalDimension.NETWORK_ACTIVITY,
        claim.environment.resource_target_arns,
    )
    reversed_cpu = ProgressionStub(
        OperationalDimension.CPU_ACTIVITY,
        reversed_claim.environment.resource_target_arns,
    )
    reversed_network = ProgressionStub(
        OperationalDimension.NETWORK_ACTIVITY,
        reversed_claim.environment.resource_target_arns,
    )

    readiness = collect_with_stubs(claim, cpu, network)
    reversed_readiness = collect_with_stubs(reversed_claim, reversed_cpu, reversed_network)

    assert [call[1] for call in cpu.calls] == [FIRST_TARGET, SECOND_TARGET]
    assert [call[1] for call in network.calls] == [FIRST_TARGET, SECOND_TARGET]
    assert readiness.association_set == reversed_readiness.association_set


def test_non_affirmative_cpu_continues_network_and_remaining_targets() -> None:
    claim = make_claim()
    cpu = ProgressionStub(
        OperationalDimension.CPU_ACTIVITY,
        frozenset({SECOND_TARGET}),
    )
    network = ProgressionStub(
        OperationalDimension.NETWORK_ACTIVITY,
        claim.environment.resource_target_arns,
    )

    readiness = collect_with_stubs(claim, cpu, network)

    assert [call[1] for call in cpu.calls] == [FIRST_TARGET, SECOND_TARGET]
    assert [call[1] for call in network.calls] == [FIRST_TARGET, SECOND_TARGET]
    assert readiness.outcome is OperationalRetirementReadinessOutcome.UNRESOLVED


def test_non_affirmative_network_continues_remaining_targets() -> None:
    claim = make_claim()
    cpu = ProgressionStub(OperationalDimension.CPU_ACTIVITY, claim.environment.resource_target_arns)
    network = ProgressionStub(
        OperationalDimension.NETWORK_ACTIVITY,
        frozenset({SECOND_TARGET}),
    )

    readiness = collect_with_stubs(claim, cpu, network)

    assert [call[1] for call in network.calls] == [FIRST_TARGET, SECOND_TARGET]
    assert readiness.outcome is OperationalRetirementReadinessOutcome.UNRESOLVED


def test_request_level_failure_stops_immediately_and_propagates_unchanged() -> None:
    claim = make_claim()
    error = RuntimeError("provider failed")
    cpu = ProgressionStub(
        OperationalDimension.CPU_ACTIVITY,
        frozenset(),
        failure_by_target={SECOND_TARGET: error},
    )
    network = ProgressionStub(
        OperationalDimension.NETWORK_ACTIVITY,
        claim.environment.resource_target_arns,
    )

    with pytest.raises(RuntimeError) as raised:
        collect_with_stubs(claim, cpu, network)

    assert raised.value is error
    assert [call[1] for call in cpu.calls] == [FIRST_TARGET, SECOND_TARGET]
    assert [call[1] for call in network.calls] == [FIRST_TARGET]


def test_complete_and_incomplete_coverage_drive_existing_readiness_outcomes() -> None:
    claim = make_claim()
    complete = collect_with_stubs(
        claim,
        ProgressionStub(OperationalDimension.CPU_ACTIVITY, claim.environment.resource_target_arns),
        ProgressionStub(
            OperationalDimension.NETWORK_ACTIVITY,
            claim.environment.resource_target_arns,
        ),
    )
    incomplete = collect_with_stubs(
        claim,
        ProgressionStub(OperationalDimension.CPU_ACTIVITY, claim.environment.resource_target_arns),
        ProgressionStub(OperationalDimension.NETWORK_ACTIVITY, frozenset()),
    )

    assert complete.outcome is OperationalRetirementReadinessOutcome.READY
    assert incomplete.outcome is OperationalRetirementReadinessOutcome.UNRESOLVED


def test_collection_does_not_mutate_upstream_artifacts() -> None:
    claim = make_claim()
    environment = claim.environment
    targets = environment.resource_target_arns
    cpu = ProgressionStub(OperationalDimension.CPU_ACTIVITY, targets)
    network = ProgressionStub(OperationalDimension.NETWORK_ACTIVITY, targets)

    readiness = collect_with_stubs(claim, cpu, network)

    assert claim.environment == environment
    assert environment.resource_target_arns == targets
    with pytest.raises(FrozenInstanceError):
        readiness.outcome = OperationalRetirementReadinessOutcome.NOT_READY
    with pytest.raises(FrozenInstanceError):
        readiness.target_coverage.association_set = Mock()
