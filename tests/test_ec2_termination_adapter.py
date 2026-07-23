from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import EndpointConnectionError

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
    RegisteredTargetOperationalEvidenceCoverage,
    RetirementAdmissionVerdict,
    RetirementLockParticipation,
    RetirementPrerequisiteStatus,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import (
    Evidence,
    EvidenceInstant,
    EvidenceTemporalContext,
    SourceProvenance,
)
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2TerminationInvocation,
    EC2TerminationInvocationOutcome,
    EC2TerminationInvocationResult,
    RetirementExecutionAuthorization,
)
from latch.infrastructure.ec2_termination_adapter import EC2TerminationAdapter

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVIDENCE_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


def make_context(
    *,
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns=resource_target_arns,
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=TTL_EXPIRES_AT,
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
    return OperationalDimensionAssociation(establishment, dimension)


def make_inactivity(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    proposition: str,
    referent: str | None = None,
) -> OperationalDimensionAssociation:
    return make_association(
        context,
        dimension,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        proposition,
        referent=referent,
    )


def make_authorization(
    *,
    with_approval: bool = True,
    context: AdmissionEvaluationContext | None = None,
) -> RetirementExecutionAuthorization:
    if context is None:
        context = make_context()

    association_set = OperationalDimensionAssociationSet(
        context,
        [
            association
            for target_arn in context.environment.resource_target_arns
            for association in (
                make_inactivity(
                    context,
                    OperationalDimension.CPU_ACTIVITY,
                    f"cpu inactive for {target_arn}",
                    referent=target_arn,
                ),
                make_inactivity(
                    context,
                    OperationalDimension.NETWORK_ACTIVITY,
                    f"network inactive for {target_arn}",
                    referent=target_arn,
                ),
            )
        ],
    )
    claim = RetirementEvaluationClaim(context.environment, context.evaluated_at)
    readiness = OperationalRetirementReadiness(
        RegisteredTargetOperationalEvidenceCoverage(claim, association_set)
    )
    prerequisite_status = RetirementPrerequisiteStatus(readiness)
    approval = OwnerRetirementApproval(context, "team-platform") if with_approval else None
    owner_participation = OwnerApprovalParticipation(prerequisite_status, approval)
    verdict = RetirementAdmissionVerdict(RetirementLockParticipation(owner_participation))
    return RetirementExecutionAuthorization(verdict)


def make_client(response: dict[str, object] | None = None) -> Mock:
    client = Mock()
    client.terminate_instances.return_value = (
        {"TerminatingInstances": [{"InstanceId": "i-0123456789abcdef0"}]}
        if response is None
        else response
    )
    return client


def test_authorized_request_creates_one_ec2_client_in_registered_region() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        EC2TerminationAdapter().terminate(make_authorization())

    session.client.assert_called_once_with("ec2", region_name="us-east-1")


def test_request_contains_exactly_registered_instance_ids() -> None:
    client = make_client(
        {
            "TerminatingInstances": [
                {"InstanceId": "i-0123456789abcdef0"},
                {"InstanceId": "i-0fedcba9876543210"},
            ]
        }
    )
    authorization = make_authorization(
        context=make_context(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        EC2TerminationAdapter().terminate(authorization)

    requested_ids = client.terminate_instances.call_args.kwargs["InstanceIds"]
    assert set(requested_ids) == {"i-0123456789abcdef0", "i-0fedcba9876543210"}


def test_refused_authorization_creates_no_client_and_makes_no_aws_call() -> None:
    with (
        patch(
            "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session"
        ) as factory,
        pytest.raises(ValueError, match="authorize"),
    ):
        EC2TerminationAdapter().terminate(make_authorization(with_approval=False))

    factory.assert_not_called()


def test_complete_expected_response_returns_accepted_invocation() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        invocation = EC2TerminationAdapter().terminate(make_authorization())

    assert isinstance(invocation, EC2TerminationInvocation)
    assert invocation.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_ACCEPTED


def test_missing_response_entry_returns_not_accepted_invocation() -> None:
    client = make_client({"TerminatingInstances": [{"InstanceId": "i-0123456789abcdef0"}]})
    authorization = make_authorization(
        context=make_context(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        invocation = EC2TerminationAdapter().terminate(authorization)

    assert (
        invocation.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )
    assert {result.accepted for result in invocation.results} == {False}


def test_duplicate_response_entry_returns_not_accepted_invocation() -> None:
    client = make_client(
        {
            "TerminatingInstances": [
                {"InstanceId": "i-0123456789abcdef0"},
                {"InstanceId": "i-0123456789abcdef0"},
            ]
        }
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        invocation = EC2TerminationAdapter().terminate(make_authorization())

    assert (
        invocation.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )


def test_unexpected_response_entry_returns_not_accepted_invocation() -> None:
    client = make_client(
        {
            "TerminatingInstances": [
                {"InstanceId": "i-0123456789abcdef0"},
                {"InstanceId": "i-11111111111111111"},
            ]
        }
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        invocation = EC2TerminationAdapter().terminate(make_authorization())

    assert (
        invocation.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )


def test_malformed_response_entry_returns_not_accepted_invocation() -> None:
    client = make_client({"TerminatingInstances": [{"InstanceId": 123}]})
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        invocation = EC2TerminationAdapter().terminate(make_authorization())

    assert (
        invocation.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )


def test_request_level_sdk_failure_returns_not_accepted_for_every_registered_target() -> None:
    client = Mock()
    client.terminate_instances.side_effect = EndpointConnectionError(
        endpoint_url="https://ec2.us-east-1.amazonaws.com"
    )
    authorization = make_authorization(
        context=make_context(resource_target_arns=frozenset({FIRST_TARGET, SECOND_TARGET}))
    )
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        invocation = EC2TerminationAdapter().terminate(authorization)

    assert (
        invocation.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )
    assert invocation.results == frozenset(
        {
            EC2TerminationInvocationResult(FIRST_TARGET, False),
            EC2TerminationInvocationResult(SECOND_TARGET, False),
        }
    )


def test_adapter_never_returns_destruction_confirmation() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        invocation = EC2TerminationAdapter().terminate(make_authorization())

    assert isinstance(invocation, EC2TerminationInvocation)
    assert not isinstance(invocation, EC2DestructionConfirmation)


def test_no_static_credentials_are_passed_to_client() -> None:
    client = make_client()
    session = Mock()
    session.client.return_value = client

    with patch(
        "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
        return_value=session,
    ):
        EC2TerminationAdapter().terminate(make_authorization())

    assert set(session.client.call_args.kwargs) == {"region_name"}


def test_provider_failure_creates_no_ec2_client_and_no_request() -> None:
    with (
        patch(
            "latch.infrastructure.ec2_termination_adapter.create_ecs_task_role_session",
            side_effect=RuntimeError("credentials unavailable"),
        ),
        pytest.raises(RuntimeError, match="credentials unavailable"),
    ):
        EC2TerminationAdapter().terminate(make_authorization())
