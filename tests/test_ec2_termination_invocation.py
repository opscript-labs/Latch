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
    EC2TerminationInvocation,
    EC2TerminationInvocationOutcome,
    EC2TerminationInvocationResult,
    RetirementExecutionAuthorization,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVIDENCE_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"
OUTSIDE_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-11111111111111111"


def make_context(
    *,
    environment_identifier: str = "env-123",
    evaluated_at: datetime = TTL_EXPIRES_AT,
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier=environment_identifier,
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns=resource_target_arns,
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


def make_authorization(
    *,
    with_approval: bool = True,
    context: AdmissionEvaluationContext | None = None,
) -> RetirementExecutionAuthorization:
    if context is None:
        context = make_context()

    readiness = OperationalRetirementReadiness(
        OperationalDimensionAssociationSet(
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
    )
    prerequisite_status = RetirementPrerequisiteStatus(readiness)
    approval = (
        OwnerRetirementApproval(context, "team-platform") if with_approval else None
    )
    owner_participation = OwnerApprovalParticipation(prerequisite_status, approval)
    verdict = RetirementAdmissionVerdict(RetirementLockParticipation(owner_participation))
    return RetirementExecutionAuthorization(verdict)


def result(target_arn: str, accepted: bool) -> EC2TerminationInvocationResult:
    return EC2TerminationInvocationResult(target_arn=target_arn, accepted=accepted)


def test_ec2_termination_invocation_has_exact_closed_vocabulary() -> None:
    assert list(EC2TerminationInvocationOutcome) == [
        EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_ACCEPTED,
        EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED,
    ]


def test_all_targets_accepted_returns_request_accepted() -> None:
    invocation = EC2TerminationInvocation(
        authorization=make_authorization(),
        results=[result(FIRST_TARGET, True)],
    )

    assert (
        invocation.outcome
        is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_ACCEPTED
    )


def test_missing_target_returns_request_not_accepted() -> None:
    authorization = make_authorization(
        context=make_context(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    )
    invocation = EC2TerminationInvocation(
        authorization=authorization,
        results=[result(FIRST_TARGET, True)],
    )

    assert (
        invocation.outcome
        is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )


def test_one_rejected_target_returns_request_not_accepted() -> None:
    invocation = EC2TerminationInvocation(
        authorization=make_authorization(),
        results=[result(FIRST_TARGET, False)],
    )

    assert (
        invocation.outcome
        is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )


def test_partial_acceptance_returns_request_not_accepted() -> None:
    authorization = make_authorization(
        context=make_context(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    )
    invocation = EC2TerminationInvocation(
        authorization=authorization,
        results=[result(FIRST_TARGET, True), result(SECOND_TARGET, False)],
    )

    assert (
        invocation.outcome
        is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )


def test_unknown_returned_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="registered"):
        EC2TerminationInvocation(
            authorization=make_authorization(),
            results=[result(OUTSIDE_TARGET, True)],
        )


def test_duplicate_returned_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="one result per target"):
        EC2TerminationInvocation(
            authorization=make_authorization(),
            results=[result(FIRST_TARGET, True), result(FIRST_TARGET, True)],
        )


def test_refused_execution_authorization_is_rejected() -> None:
    with pytest.raises(ValueError, match="authorize"):
        EC2TerminationInvocation(
            authorization=make_authorization(with_approval=False),
            results=[],
        )


def test_unordered_results_have_equal_identity_and_hashing() -> None:
    authorization = make_authorization(
        context=make_context(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    )

    first = EC2TerminationInvocation(
        authorization=authorization,
        results=[result(FIRST_TARGET, True), result(SECOND_TARGET, True)],
    )
    second = EC2TerminationInvocation(
        authorization=authorization,
        results=[result(SECOND_TARGET, True), result(FIRST_TARGET, True)],
    )

    assert first == second
    assert hash(first) == hash(second)


def test_changed_authorization_changes_identity() -> None:
    first = make_authorization()
    second = make_authorization(
        context=make_context(evaluated_at=TTL_EXPIRES_AT + timedelta(seconds=1))
    )

    assert EC2TerminationInvocation(first, [result(FIRST_TARGET, True)]) != (
        EC2TerminationInvocation(second, [result(FIRST_TARGET, True)])
    )


def test_changed_result_set_changes_identity() -> None:
    authorization = make_authorization()

    assert EC2TerminationInvocation(authorization, [result(FIRST_TARGET, True)]) != (
        EC2TerminationInvocation(authorization, [result(FIRST_TARGET, False)])
    )


def test_derived_outcome_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        EC2TerminationInvocation(
            authorization=make_authorization(),
            results=[result(FIRST_TARGET, True)],
            outcome=EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_ACCEPTED,
        )


def test_invocation_and_result_are_immutable() -> None:
    invocation_result = result(FIRST_TARGET, True)
    invocation = EC2TerminationInvocation(
        authorization=make_authorization(),
        results=[invocation_result],
    )

    with pytest.raises(FrozenInstanceError):
        invocation.outcome = (
            EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
        )

    with pytest.raises(FrozenInstanceError):
        invocation_result.accepted = False


def test_invocation_does_not_mutate_upstream_artifacts() -> None:
    authorization = make_authorization()
    verdict = authorization.verdict
    environment = (
        verdict.lock_participation.owner_approval_participation.prerequisite_status
        .readiness.association_set.context.environment
    )
    targets = environment.resource_target_arns

    invocation = EC2TerminationInvocation(
        authorization=authorization,
        results=[result(FIRST_TARGET, True)],
    )

    assert invocation.authorization == authorization
    assert authorization.verdict == verdict
    assert environment.resource_target_arns == targets
