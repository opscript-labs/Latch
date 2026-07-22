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
    return OperationalDimensionAssociation(
        establishment=establishment,
        dimension=dimension,
    )


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


def make_satisfied_status(
    evaluated_at: datetime = TTL_EXPIRES_AT,
) -> RetirementPrerequisiteStatus:
    context = make_context(evaluated_at=evaluated_at)
    return make_prerequisite_status(
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


def make_not_satisfied_status() -> RetirementPrerequisiteStatus:
    context = make_context()
    return make_prerequisite_status(
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


def make_unresolved_status() -> RetirementPrerequisiteStatus:
    context = make_context()
    return make_prerequisite_status(
        context,
        [make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")],
    )


def make_approval(status: RetirementPrerequisiteStatus) -> OwnerRetirementApproval:
    return OwnerRetirementApproval(
        context=status.readiness.association_set.context,
        approved_by="team-platform",
    )


def test_owner_approval_participation_has_exact_closed_vocabulary() -> None:
    assert list(OwnerApprovalParticipationOutcome) == [
        OwnerApprovalParticipationOutcome.PERMIT_FURTHER_ADMISSION,
        OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION,
        OwnerApprovalParticipationOutcome.FURTHER_ADMISSION_UNRESOLVED,
    ]


def test_satisfied_prerequisites_with_approval_permit_further_admission() -> None:
    status = make_satisfied_status()
    participation = OwnerApprovalParticipation(
        prerequisite_status=status,
        approval=make_approval(status),
    )

    assert (
        participation.outcome
        is OwnerApprovalParticipationOutcome.PERMIT_FURTHER_ADMISSION
    )


def test_satisfied_prerequisites_without_approval_block_further_admission() -> None:
    participation = OwnerApprovalParticipation(
        prerequisite_status=make_satisfied_status()
    )

    assert (
        participation.outcome
        is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION
    )


def test_not_satisfied_prerequisites_block_with_approval() -> None:
    status = make_not_satisfied_status()
    participation = OwnerApprovalParticipation(
        prerequisite_status=status,
        approval=make_approval(status),
    )

    assert (
        participation.outcome
        is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION
    )


def test_not_satisfied_prerequisites_block_without_approval() -> None:
    participation = OwnerApprovalParticipation(
        prerequisite_status=make_not_satisfied_status()
    )

    assert (
        participation.outcome
        is OwnerApprovalParticipationOutcome.BLOCK_FURTHER_ADMISSION
    )


def test_unresolved_prerequisites_remain_unresolved_with_approval() -> None:
    status = make_unresolved_status()
    participation = OwnerApprovalParticipation(
        prerequisite_status=status,
        approval=make_approval(status),
    )

    assert (
        participation.outcome
        is OwnerApprovalParticipationOutcome.FURTHER_ADMISSION_UNRESOLVED
    )


def test_unresolved_prerequisites_remain_unresolved_without_approval() -> None:
    participation = OwnerApprovalParticipation(
        prerequisite_status=make_unresolved_status()
    )

    assert (
        participation.outcome
        is OwnerApprovalParticipationOutcome.FURTHER_ADMISSION_UNRESOLVED
    )


def test_present_approval_for_different_context_is_rejected() -> None:
    status = make_satisfied_status()
    other_context = make_context(environment_identifier="env-456")
    approval = OwnerRetirementApproval(
        context=other_context,
        approved_by="team-platform",
    )

    with pytest.raises(ValueError, match="same context"):
        OwnerApprovalParticipation(
            prerequisite_status=status,
            approval=approval,
        )


def test_identity_and_hashing_depend_only_on_status_and_optional_approval() -> None:
    status = make_satisfied_status()
    approval = make_approval(status)

    participation = OwnerApprovalParticipation(status, approval)
    same_participation = OwnerApprovalParticipation(status, approval)

    assert participation == same_participation
    assert hash(participation) == hash(same_participation)


def test_equivalent_inputs_produce_equal_results() -> None:
    first_status = make_satisfied_status()
    second_status = make_satisfied_status()

    assert OwnerApprovalParticipation(
        first_status,
        make_approval(first_status),
    ) == OwnerApprovalParticipation(
        second_status,
        make_approval(second_status),
    )


def test_changed_prerequisite_status_produces_distinct_identity() -> None:
    assert OwnerApprovalParticipation(make_satisfied_status()) != (
        OwnerApprovalParticipation(
            make_satisfied_status(TTL_EXPIRES_AT + timedelta(seconds=1))
        )
    )


def test_changed_approval_presence_produces_distinct_identity() -> None:
    status = make_satisfied_status()

    assert OwnerApprovalParticipation(status) != OwnerApprovalParticipation(
        status,
        make_approval(status),
    )


def test_outcome_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        OwnerApprovalParticipation(
            prerequisite_status=make_satisfied_status(),
            outcome=OwnerApprovalParticipationOutcome.PERMIT_FURTHER_ADMISSION,
        )


def test_owner_approval_participation_is_immutable() -> None:
    participation = OwnerApprovalParticipation(make_satisfied_status())

    with pytest.raises(FrozenInstanceError):
        participation.outcome = (
            OwnerApprovalParticipationOutcome.PERMIT_FURTHER_ADMISSION
        )


def test_owner_approval_participation_does_not_mutate_inputs() -> None:
    status = make_satisfied_status()
    approval = make_approval(status)
    readiness = status.readiness
    association_set = readiness.association_set
    context = association_set.context
    environment = context.environment

    participation = OwnerApprovalParticipation(status, approval)

    assert participation.prerequisite_status == status
    assert participation.approval == approval
    assert status.readiness == readiness
    assert readiness.association_set == association_set
    assert association_set.context == context
    assert context.environment == environment
