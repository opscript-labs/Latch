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
    OwnerRetirementApproval,
    RetirementAdmissionVerdict,
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
from latch.domain.execution import (
    RetirementExecutionAuthorization,
    RetirementExecutionAuthorizationOutcome,
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


def make_verdict(
    *,
    with_approval: bool,
    context: AdmissionEvaluationContext | None = None,
    associations: list[OperationalDimensionAssociation] | None = None,
) -> RetirementAdmissionVerdict:
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

    prerequisite_status = make_prerequisite_status(context, associations)
    approval = (
        OwnerRetirementApproval(context, "team-platform") if with_approval else None
    )
    owner_participation = OwnerApprovalParticipation(prerequisite_status, approval)
    return RetirementAdmissionVerdict(RetirementLockParticipation(owner_participation))


def test_retirement_execution_authorization_has_exact_closed_vocabulary() -> None:
    assert list(RetirementExecutionAuthorizationOutcome) == [
        RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED,
        RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_REFUSED_UNSAFE,
        (
            RetirementExecutionAuthorizationOutcome
            .RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT
        ),
    ]


def test_safe_verdict_authorizes_retirement_execution() -> None:
    authorization = RetirementExecutionAuthorization(make_verdict(with_approval=True))

    assert (
        authorization.outcome
        is RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED
    )


def test_unsafe_verdict_refuses_retirement_execution_as_unsafe() -> None:
    authorization = RetirementExecutionAuthorization(make_verdict(with_approval=False))

    assert (
        authorization.outcome
        is RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_REFUSED_UNSAFE
    )


def test_insufficient_verdict_refuses_retirement_execution_as_insufficient() -> None:
    context = make_context()
    authorization = RetirementExecutionAuthorization(
        make_verdict(
            with_approval=True,
            context=context,
            associations=[
                make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")
            ],
        )
    )

    assert (
        authorization.outcome
        is (
            RetirementExecutionAuthorizationOutcome
            .RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT
        )
    )


def test_identity_and_hashing_depend_only_on_retirement_admission_verdict() -> None:
    verdict = make_verdict(with_approval=True)

    authorization = RetirementExecutionAuthorization(verdict)
    same_authorization = RetirementExecutionAuthorization(verdict)

    assert authorization == same_authorization
    assert hash(authorization) == hash(same_authorization)


def test_equivalent_verdict_artifacts_produce_equal_authorizations() -> None:
    assert RetirementExecutionAuthorization(make_verdict(with_approval=True)) == (
        RetirementExecutionAuthorization(make_verdict(with_approval=True))
    )


def test_changed_verdict_artifact_produces_distinct_identity() -> None:
    first = make_verdict(with_approval=True)
    second = make_verdict(
        with_approval=True,
        context=make_context(evaluated_at=TTL_EXPIRES_AT + timedelta(seconds=1)),
    )

    assert RetirementExecutionAuthorization(first) != (
        RetirementExecutionAuthorization(second)
    )


def test_outcome_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        RetirementExecutionAuthorization(
            verdict=make_verdict(with_approval=True),
            outcome=(
                RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED
            ),
        )


def test_retirement_execution_authorization_is_immutable() -> None:
    authorization = RetirementExecutionAuthorization(make_verdict(with_approval=True))

    with pytest.raises(FrozenInstanceError):
        authorization.outcome = (
            RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_REFUSED_UNSAFE
        )


def test_retirement_execution_authorization_does_not_mutate_upstream_artifacts() -> None:
    verdict = make_verdict(with_approval=True)
    lock_participation = verdict.lock_participation
    owner_participation = lock_participation.owner_approval_participation
    prerequisite_status = owner_participation.prerequisite_status
    readiness = prerequisite_status.readiness
    association_set = readiness.association_set
    context = association_set.context
    environment = context.environment

    authorization = RetirementExecutionAuthorization(verdict)

    assert authorization.verdict == verdict
    assert verdict.lock_participation == lock_participation
    assert lock_participation.owner_approval_participation == owner_participation
    assert owner_participation.prerequisite_status == prerequisite_status
    assert prerequisite_status.readiness == readiness
    assert readiness.association_set == association_set
    assert association_set.context == context
    assert context.environment == environment


def test_retirement_execution_authorization_is_exported_from_execution_domain() -> None:
    assert RetirementExecutionAuthorization.__module__.startswith("latch.domain.execution")
