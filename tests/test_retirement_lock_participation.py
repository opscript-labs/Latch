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
    OperationalDimensionAssociationSet,
    OperationalRetirementReadiness,
    OwnerApprovalParticipation,
    OwnerApprovalParticipationOutcome,
    OwnerRetirementApproval,
    RetirementLock,
    RetirementLockParticipation,
    RetirementPrerequisiteStatus,
)
from latch.domain.environment import Environment
from latch.domain.evidence import (
    Evidence,
    EvidenceInstant,
    EvidenceTemporalContext,
    SourceProvenance,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVIDENCE_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def make_context(
    *,
    environment_identifier: str = "env-123",
    evaluated_at: datetime = TTL_EXPIRES_AT,
) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier=environment_identifier,
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
        resource_target_arns={"arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"},
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=evaluated_at,
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
    return OperationalDimensionAssociation(establishment, dimension)


def make_activity(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    proposition: str,
) -> OperationalDimensionAssociation:
    return make_association(
        context,
        dimension,
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        proposition,
    )


def make_inactivity(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    proposition: str,
) -> OperationalDimensionAssociation:
    return make_association(
        context,
        dimension,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        proposition,
    )


def make_prerequisite_status(
    context: AdmissionEvaluationContext,
    associations: list[OperationalDimensionAssociation],
) -> RetirementPrerequisiteStatus:
    readiness = OperationalRetirementReadiness(
        OperationalDimensionAssociationSet(context, associations)
    )
    return RetirementPrerequisiteStatus(readiness)


def make_owner_participation(
    *,
    with_approval: bool,
    context: AdmissionEvaluationContext | None = None,
    associations: list[OperationalDimensionAssociation] | None = None,
) -> OwnerApprovalParticipation:
    if context is None:
        context = make_context()

    if associations is None:
        associations = [
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive"),
            make_inactivity(
                context,
                OperationalDimension.NETWORK_ACTIVITY,
                "network inactive",
            ),
        ]

    status = make_prerequisite_status(context, associations)
    approval = (
        OwnerRetirementApproval(context, "team-platform") if with_approval else None
    )
    return OwnerApprovalParticipation(status, approval)


def test_valid_lock_participation_with_matching_environment() -> None:
    owner_participation = make_owner_participation(with_approval=True)
    lock = RetirementLock(
        owner_participation.prerequisite_status.readiness.association_set.context.environment
    )

    participation = RetirementLockParticipation(owner_participation, lock)

    assert participation.owner_approval_participation == owner_participation
    assert participation.lock == lock


def test_mismatched_lock_environment_is_rejected() -> None:
    owner_participation = make_owner_participation(with_approval=True)
    mismatched_lock = RetirementLock(
        Environment(
            identifier="env-456",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
        resource_target_arns={"arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"},
        )
    )

    with pytest.raises(ValueError, match="same environment"):
        RetirementLockParticipation(owner_participation, mismatched_lock)


def test_lock_present_blocks_permitted_owner_participation() -> None:
    owner_participation = make_owner_participation(with_approval=True)
    lock = RetirementLock(
        owner_participation.prerequisite_status.readiness.association_set.context.environment
    )

    participation = RetirementLockParticipation(owner_participation, lock)

    assert participation.outcome is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION


def test_lock_present_blocks_blocked_owner_participation() -> None:
    owner_participation = make_owner_participation(with_approval=False)
    lock = RetirementLock(
        owner_participation.prerequisite_status.readiness.association_set.context.environment
    )

    participation = RetirementLockParticipation(owner_participation, lock)

    assert participation.outcome is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION


def test_lock_present_blocks_unresolved_owner_participation() -> None:
    context = make_context()
    owner_participation = make_owner_participation(
        with_approval=True,
        context=context,
        associations=[
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
        ],
    )
    lock = RetirementLock(context.environment)

    participation = RetirementLockParticipation(owner_participation, lock)

    assert participation.outcome is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION


def test_lock_absent_preserves_permit_outcome() -> None:
    participation = RetirementLockParticipation(
        make_owner_participation(with_approval=True)
    )

    assert participation.outcome is OwnerApprovalParticipationOutcome.PERMIT_FURTHER_ADMISSION


def test_lock_absent_preserves_unresolved_outcome() -> None:
    context = make_context()
    owner_participation = make_owner_participation(
        with_approval=True,
        context=context,
        associations=[
            make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
        ],
    )

    participation = RetirementLockParticipation(owner_participation)

    assert (
        participation.outcome
        is OwnerApprovalParticipationOutcome.FURTHER_ADMISSION_UNRESOLVED
    )


def test_lock_absent_preserves_block_outcome() -> None:
    participation = RetirementLockParticipation(
        make_owner_participation(with_approval=False)
    )

    assert participation.outcome is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION


def test_identity_and_hashing_use_owner_participation_and_optional_lock() -> None:
    owner_participation = make_owner_participation(with_approval=True)
    lock = RetirementLock(
        owner_participation.prerequisite_status.readiness.association_set.context.environment
    )

    participation = RetirementLockParticipation(owner_participation, lock)
    same_participation = RetirementLockParticipation(owner_participation, lock)

    assert participation == same_participation
    assert hash(participation) == hash(same_participation)


def test_equivalent_inputs_produce_equal_participation() -> None:
    first = make_owner_participation(with_approval=True)
    second = make_owner_participation(with_approval=True)

    assert RetirementLockParticipation(
        first,
        RetirementLock(first.prerequisite_status.readiness.association_set.context.environment),
    ) == RetirementLockParticipation(
        second,
        RetirementLock(
            second.prerequisite_status.readiness.association_set.context.environment
        ),
    )


def test_changed_owner_participation_produces_distinct_identity() -> None:
    first = make_owner_participation(with_approval=True)
    context = make_context(evaluated_at=TTL_EXPIRES_AT + timedelta(seconds=1))
    second = make_owner_participation(with_approval=True, context=context)

    assert RetirementLockParticipation(first) != RetirementLockParticipation(second)


def test_changed_lock_presence_produces_distinct_identity() -> None:
    owner_participation = make_owner_participation(with_approval=True)
    lock = RetirementLock(
        owner_participation.prerequisite_status.readiness.association_set.context.environment
    )

    assert RetirementLockParticipation(owner_participation) != (
        RetirementLockParticipation(owner_participation, lock)
    )


def test_outcome_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        RetirementLockParticipation(
            owner_approval_participation=make_owner_participation(with_approval=True),
            outcome=OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION,
        )


def test_retirement_lock_participation_is_immutable() -> None:
    participation = RetirementLockParticipation(
        make_owner_participation(with_approval=True)
    )

    with pytest.raises(FrozenInstanceError):
        participation.outcome = (
            OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION
        )


def test_retirement_lock_participation_does_not_mutate_upstream_artifacts() -> None:
    owner_participation = make_owner_participation(with_approval=True)
    lock = RetirementLock(
        owner_participation.prerequisite_status.readiness.association_set.context.environment
    )
    prerequisite_status = owner_participation.prerequisite_status
    readiness = prerequisite_status.readiness
    association_set = readiness.association_set
    context = association_set.context
    environment = context.environment

    participation = RetirementLockParticipation(owner_participation, lock)

    assert participation.owner_approval_participation == owner_participation
    assert participation.lock == lock
    assert owner_participation.prerequisite_status == prerequisite_status
    assert prerequisite_status.readiness == readiness
    assert readiness.association_set == association_set
    assert association_set.context == context
    assert context.environment == environment
