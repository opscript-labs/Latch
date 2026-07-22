from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    AdmissionVerdict,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionEstablishment,
    OperationalAssertionProjection,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalDimensionAssociationSet,
    OperationalRetirementReadiness,
    OwnerApprovalParticipation,
    OwnerRetirementApproval,
    RetirementAdmissionVerdict,
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
        resource_target_arns={"arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api"},
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


def make_lock_participation(
    *,
    with_approval: bool,
    with_lock: bool = False,
    context: AdmissionEvaluationContext | None = None,
    associations: list[OperationalDimensionAssociation] | None = None,
) -> RetirementLockParticipation:
    owner_participation = make_owner_participation(
        with_approval=with_approval,
        context=context,
        associations=associations,
    )
    lock = (
        RetirementLock(
            owner_participation.prerequisite_status.readiness
            .association_set.context.environment
        )
        if with_lock
        else None
    )
    return RetirementLockParticipation(owner_participation, lock)


def test_permit_further_admission_maps_to_safe() -> None:
    verdict = RetirementAdmissionVerdict(
        make_lock_participation(with_approval=True)
    )

    assert verdict.verdict is AdmissionVerdict.SAFE


def test_block_further_admission_maps_to_unsafe() -> None:
    verdict = RetirementAdmissionVerdict(
        make_lock_participation(with_approval=False)
    )

    assert verdict.verdict is AdmissionVerdict.UNSAFE


def test_unresolved_further_admission_maps_to_insufficient() -> None:
    context = make_context()
    verdict = RetirementAdmissionVerdict(
        make_lock_participation(
            with_approval=True,
            context=context,
            associations=[
                make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
            ],
        )
    )

    assert verdict.verdict is AdmissionVerdict.INSUFFICIENT


def test_supplied_lock_maps_to_unsafe() -> None:
    verdict = RetirementAdmissionVerdict(
        make_lock_participation(with_approval=True, with_lock=True)
    )

    assert verdict.verdict is AdmissionVerdict.UNSAFE


def test_existing_admission_verdict_members_are_used_only() -> None:
    assert list(AdmissionVerdict) == [
        AdmissionVerdict.SAFE,
        AdmissionVerdict.UNSAFE,
        AdmissionVerdict.INSUFFICIENT,
    ]


def test_identity_and_hashing_depend_only_on_lock_participation() -> None:
    lock_participation = make_lock_participation(with_approval=True)

    verdict = RetirementAdmissionVerdict(lock_participation)
    same_verdict = RetirementAdmissionVerdict(lock_participation)

    assert verdict == same_verdict
    assert hash(verdict) == hash(same_verdict)


def test_equivalent_participation_artifacts_produce_equal_verdict_artifacts() -> None:
    assert RetirementAdmissionVerdict(make_lock_participation(with_approval=True)) == (
        RetirementAdmissionVerdict(make_lock_participation(with_approval=True))
    )


def test_changed_participation_produces_distinct_identity() -> None:
    first = make_lock_participation(with_approval=True)
    second = make_lock_participation(
        with_approval=True,
        context=make_context(evaluated_at=TTL_EXPIRES_AT + timedelta(seconds=1)),
    )

    assert RetirementAdmissionVerdict(first) != RetirementAdmissionVerdict(second)


def test_verdict_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        RetirementAdmissionVerdict(
            lock_participation=make_lock_participation(with_approval=True),
            verdict=AdmissionVerdict.SAFE,
        )


def test_retirement_admission_verdict_is_immutable() -> None:
    verdict = RetirementAdmissionVerdict(
        make_lock_participation(with_approval=True)
    )

    with pytest.raises(FrozenInstanceError):
        verdict.verdict = AdmissionVerdict.UNSAFE


def test_retirement_admission_verdict_does_not_mutate_upstream_artifacts() -> None:
    lock_participation = make_lock_participation(with_approval=True, with_lock=True)
    owner_participation = lock_participation.owner_approval_participation
    prerequisite_status = owner_participation.prerequisite_status
    readiness = prerequisite_status.readiness
    association_set = readiness.association_set
    context = association_set.context
    environment = context.environment

    verdict = RetirementAdmissionVerdict(lock_participation)

    assert verdict.lock_participation == lock_participation
    assert lock_participation.owner_approval_participation == owner_participation
    assert owner_participation.prerequisite_status == prerequisite_status
    assert prerequisite_status.readiness == readiness
    assert readiness.association_set == association_set
    assert association_set.context == context
    assert context.environment == environment


def test_retirement_admission_verdict_is_exported_from_admission_domain() -> None:
    assert RetirementAdmissionVerdict.__module__.startswith("latch.domain.admission")
