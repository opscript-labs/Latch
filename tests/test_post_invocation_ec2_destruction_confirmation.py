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
    RegisteredTargetOperationalEvidenceCoverage,
    RetirementAdmissionVerdict,
    RetirementLockParticipation,
    RetirementPrerequisiteStatus,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import Evidence, EvidenceInstant, SourceProvenance
from latch.domain.execution import (
    EC2DestructionConfirmation,
    EC2DestructionConfirmationOutcome,
    EC2InstanceLifecycleState,
    EC2TerminationInvocation,
    EC2TerminationInvocationOutcome,
    EC2TerminationInvocationResult,
    RetirementExecutionAuthorization,
)
from latch.infrastructure.post_invocation_ec2_destruction_confirmation import (
    PostInvocationEC2DestructionConfirmation,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
CLAIM_TIME = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"


def make_environment(
    *,
    identifier: str = "env-123",
) -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns={TARGET},
    )


def make_claim(
    *,
    environment: Environment | None = None,
    claim_time: datetime = CLAIM_TIME,
) -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(environment or make_environment(), claim_time)


def make_context(claim: RetirementEvaluationClaim) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=claim.environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=claim.claim_time,
    )


def make_association(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
) -> OperationalDimensionAssociation:
    evidence = Evidence(
        proposition=f"{dimension.value} for {TARGET}",
        referent=TARGET,
        source_provenance=SourceProvenance(
            source_system="aws.cloudwatch.metrics",
            source_occurrence=f"aws.cloudwatch.metrics:{dimension.value}:{TARGET}",
        ),
        temporal_context=EvidenceInstant(context.evaluated_at),
    )
    classification = EvidencePropositionClassificationAssociation(
        evidence,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
    )
    return OperationalDimensionAssociation(
        OperationalAssertionEstablishment(OperationalAssertionProjection(classification, context)),
        dimension,
    )


def make_authorization(
    claim: RetirementEvaluationClaim,
) -> RetirementExecutionAuthorization:
    context = make_context(claim)
    association_set = OperationalDimensionAssociationSet(
        context,
        [
            make_association(context, OperationalDimension.CPU_ACTIVITY),
            make_association(context, OperationalDimension.NETWORK_ACTIVITY),
        ],
    )
    readiness = OperationalRetirementReadiness(
        RegisteredTargetOperationalEvidenceCoverage(claim, association_set)
    )
    prerequisite_status = RetirementPrerequisiteStatus(readiness)
    owner_participation = OwnerApprovalParticipation(
        prerequisite_status,
        OwnerRetirementApproval(context, "team-platform"),
    )
    verdict = RetirementAdmissionVerdict(RetirementLockParticipation(owner_participation))
    return RetirementExecutionAuthorization(verdict)


def make_invocation(
    claim: RetirementEvaluationClaim,
    *,
    accepted: bool = True,
) -> EC2TerminationInvocation:
    return EC2TerminationInvocation(
        make_authorization(claim),
        [EC2TerminationInvocationResult(TARGET, accepted)],
    )


def make_confirmation(
    environment: Environment,
    *,
    confirmed: bool = True,
) -> EC2DestructionConfirmation:
    lifecycle_state = "terminated" if confirmed else "stopping"
    return EC2DestructionConfirmation(
        environment,
        [EC2InstanceLifecycleState(TARGET, lifecycle_state)],
    )


class ConfirmationAdapterStub:
    def __init__(
        self,
        confirmation: EC2DestructionConfirmation | None = None,
        failure: BaseException | None = None,
    ) -> None:
        self.confirmation = confirmation
        self.failure = failure
        self.calls: list[Environment] = []

    def confirm(self, environment: Environment) -> EC2DestructionConfirmation:
        self.calls.append(environment)
        if self.failure is not None:
            raise self.failure

        if self.confirmation is None:
            raise AssertionError("confirmation was not configured")

        return self.confirmation


def make_coordinator(
    adapter: ConfirmationAdapterStub,
) -> PostInvocationEC2DestructionConfirmation:
    return PostInvocationEC2DestructionConfirmation(adapter)


def test_accepted_invocation_with_valid_trace_calls_adapter_once() -> None:
    claim = make_claim()
    confirmation = make_confirmation(claim.environment)
    adapter = ConfirmationAdapterStub(confirmation)

    result = make_coordinator(adapter).confirm(claim, make_invocation(claim))

    assert result is confirmation
    assert result.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED
    assert adapter.calls == [claim.environment]


def test_non_accepted_invocation_with_valid_trace_calls_adapter_once() -> None:
    claim = make_claim()
    confirmation = make_confirmation(claim.environment)
    adapter = ConfirmationAdapterStub(confirmation)

    result = make_coordinator(adapter).confirm(
        claim,
        make_invocation(claim, accepted=False),
    )

    assert result is confirmation
    assert (
        make_invocation(claim, accepted=False).outcome
        is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    )
    assert adapter.calls == [claim.environment]


def test_confirmed_and_not_confirmed_results_return_unchanged() -> None:
    claim = make_claim()
    confirmed = make_confirmation(claim.environment, confirmed=True)
    not_confirmed = make_confirmation(claim.environment, confirmed=False)

    assert (
        make_coordinator(ConfirmationAdapterStub(confirmed)).confirm(
            claim,
            make_invocation(claim),
        )
        is confirmed
    )
    assert (
        make_coordinator(ConfirmationAdapterStub(not_confirmed)).confirm(
            claim,
            make_invocation(claim),
        )
        is not_confirmed
    )
    assert confirmed.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_CONFIRMED
    assert not_confirmed.outcome is EC2DestructionConfirmationOutcome.DESTRUCTION_NOT_CONFIRMED


def test_environment_trace_mismatch_returns_no_confirmation_without_adapter_call() -> None:
    claim = make_claim()
    other_claim = make_claim(environment=make_environment(identifier="env-456"))
    adapter = ConfirmationAdapterStub(make_confirmation(other_claim.environment))

    result = make_coordinator(adapter).confirm(claim, make_invocation(other_claim))

    assert result is None
    assert adapter.calls == []


def test_evaluation_time_trace_mismatch_returns_no_confirmation_without_adapter_call() -> None:
    claim = make_claim()
    other_claim = make_claim(claim_time=CLAIM_TIME + timedelta(seconds=1))
    adapter = ConfirmationAdapterStub(make_confirmation(other_claim.environment))

    result = make_coordinator(adapter).confirm(claim, make_invocation(other_claim))

    assert result is None
    assert adapter.calls == []


def test_action_trace_mismatch_returns_no_confirmation_without_adapter_call() -> None:
    claim = make_claim()
    invocation = make_invocation(claim)
    context = invocation.authorization.verdict.lock_participation.owner_approval_participation.prerequisite_status.readiness.association_set.context
    object.__setattr__(context, "requested_retirement", "release")
    adapter = ConfirmationAdapterStub(make_confirmation(claim.environment))

    result = make_coordinator(adapter).confirm(claim, invocation)

    assert result is None
    assert adapter.calls == []


def test_confirmation_adapter_failure_propagates_unchanged() -> None:
    claim = make_claim()
    error = RuntimeError("confirmation request failed")

    with pytest.raises(RuntimeError) as raised:
        make_coordinator(ConfirmationAdapterStub(failure=error)).confirm(
            claim,
            make_invocation(claim),
        )

    assert raised.value is error


def test_inputs_remain_unchanged() -> None:
    claim = make_claim()
    invocation = make_invocation(claim)
    authorization = invocation.authorization
    environment = claim.environment

    make_coordinator(ConfirmationAdapterStub(make_confirmation(claim.environment))).confirm(
        claim, invocation
    )

    assert claim.environment == environment
    assert invocation.authorization == authorization
    assert (
        invocation.authorization.verdict.lock_participation.owner_approval_participation.prerequisite_status.readiness.association_set.context.environment
        == environment
    )
