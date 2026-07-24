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
    RegisteredTargetOperationalEvidenceCoverage,
    RetirementAdmissionVerdict,
    RetirementLock,
    RetirementLockParticipation,
    RetirementPrerequisiteStatus,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import Evidence, EvidenceInstant, SourceProvenance
from latch.domain.execution import (
    EC2TerminationInvocation,
    EC2TerminationInvocationOutcome,
    EC2TerminationInvocationResult,
    RetirementExecutionAuthorization,
    RetirementExecutionAuthorizationOutcome,
)
from latch.infrastructure.claim_fenced_ec2_termination_attempt import (
    ClaimFencedEC2TerminationAttempt,
)
from latch.infrastructure.dynamodb_active_claim_validator import ActiveClaimValidationResult

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


def make_context(
    claim: RetirementEvaluationClaim,
    *,
    action: AdmissionRequest = AdmissionRequest.RETIREMENT,
    evaluated_at: datetime | None = None,
) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=claim.environment,
        requested_retirement=action,
        evaluated_at=evaluated_at or claim.claim_time,
    )


def make_association(
    context: AdmissionEvaluationContext,
    dimension: OperationalDimension,
    classification: EvidencePropositionClassification = (
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY
    ),
) -> OperationalDimensionAssociation:
    source_system = (
        "aws.cloudtrail.event"
        if classification is EvidencePropositionClassification.OPERATIONAL_ACTIVITY
        else "aws.cloudwatch.metrics"
    )
    evidence = Evidence(
        proposition=f"{dimension.value} for {TARGET}",
        referent=TARGET,
        source_provenance=SourceProvenance(
            source_system=source_system,
            source_occurrence=f"{source_system}:{dimension.value}:{TARGET}",
        ),
        temporal_context=EvidenceInstant(context.evaluated_at),
    )
    classification_association = EvidencePropositionClassificationAssociation(
        evidence,
        classification,
    )
    return OperationalDimensionAssociation(
        OperationalAssertionEstablishment(
            OperationalAssertionProjection(classification_association, context)
        ),
        dimension,
    )


def make_verdict(
    claim: RetirementEvaluationClaim,
    *,
    with_approval: bool = True,
    with_lock: bool = False,
    associations: list[OperationalDimensionAssociation] | None = None,
    context: AdmissionEvaluationContext | None = None,
) -> RetirementAdmissionVerdict:
    context = context or make_context(claim)
    if associations is None:
        associations = [
            make_association(context, OperationalDimension.CPU_ACTIVITY),
            make_association(context, OperationalDimension.NETWORK_ACTIVITY),
        ]

    association_set = OperationalDimensionAssociationSet(context, associations)
    readiness = OperationalRetirementReadiness(
        RegisteredTargetOperationalEvidenceCoverage(claim, association_set)
    )
    prerequisite_status = RetirementPrerequisiteStatus(readiness)
    approval = OwnerRetirementApproval(context, "team-platform") if with_approval else None
    owner_participation = OwnerApprovalParticipation(prerequisite_status, approval)
    lock = RetirementLock(context.environment) if with_lock else None
    return RetirementAdmissionVerdict(RetirementLockParticipation(owner_participation, lock))


def make_unresolved_verdict(
    claim: RetirementEvaluationClaim,
) -> RetirementAdmissionVerdict:
    context = make_context(claim)
    return make_verdict(
        claim,
        associations=[make_association(context, OperationalDimension.CPU_ACTIVITY)],
        context=context,
    )


class ActiveClaimValidatorStub:
    def __init__(self, result: ActiveClaimValidationResult) -> None:
        self.result = result
        self.calls: list[RetirementEvaluationClaim] = []

    def validate(
        self,
        claim: RetirementEvaluationClaim,
    ) -> ActiveClaimValidationResult:
        self.calls.append(claim)
        return self.result


class TerminationAdapterStub:
    def __init__(
        self,
        *,
        accepted: bool = True,
        failure: BaseException | None = None,
    ) -> None:
        self.accepted = accepted
        self.failure = failure
        self.calls: list[RetirementExecutionAuthorization] = []

    def terminate(
        self,
        authorization: RetirementExecutionAuthorization,
    ) -> EC2TerminationInvocation:
        self.calls.append(authorization)
        if self.failure is not None:
            raise self.failure

        return EC2TerminationInvocation(
            authorization,
            [EC2TerminationInvocationResult(TARGET, self.accepted)],
        )


def make_attempt(
    validator: ActiveClaimValidatorStub,
    adapter: TerminationAdapterStub,
) -> ClaimFencedEC2TerminationAttempt:
    return ClaimFencedEC2TerminationAttempt(
        active_claim_validator=validator,
        termination_adapter=adapter,
    )


def test_valid_safe_trace_valid_claim_invokes_adapter_once_and_returns_invocation() -> None:
    claim = make_claim()
    verdict = make_verdict(claim)
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = TerminationAdapterStub()

    result = make_attempt(validator, adapter).attempt(claim, verdict)

    assert isinstance(result, EC2TerminationInvocation)
    assert result.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_ACCEPTED
    assert validator.calls == [claim]
    assert len(adapter.calls) == 1
    assert (
        adapter.calls[0].outcome
        is RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED
    )
    assert adapter.calls[0].verdict == verdict


def test_valid_safe_trace_invalid_final_claim_returns_no_invocation() -> None:
    claim = make_claim()
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM)
    adapter = TerminationAdapterStub()

    result = make_attempt(validator, adapter).attempt(claim, make_verdict(claim))

    assert result is None
    assert validator.calls == [claim]
    assert adapter.calls == []


def test_unsafe_returns_existing_refusal_without_validator_or_adapter() -> None:
    claim = make_claim()
    verdict = make_verdict(claim, with_lock=True)
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = TerminationAdapterStub()

    result = make_attempt(validator, adapter).attempt(claim, verdict)

    assert isinstance(result, RetirementExecutionAuthorization)
    assert (
        result.outcome
        is RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_REFUSED_UNSAFE
    )
    assert result.verdict.verdict is AdmissionVerdict.UNSAFE
    assert validator.calls == []
    assert adapter.calls == []


def test_insufficient_returns_existing_refusal_without_validator_or_adapter() -> None:
    claim = make_claim()
    verdict = make_unresolved_verdict(claim)
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = TerminationAdapterStub()

    result = make_attempt(validator, adapter).attempt(claim, verdict)

    assert isinstance(result, RetirementExecutionAuthorization)
    assert (
        result.outcome
        is RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT
    )
    assert result.verdict.verdict is AdmissionVerdict.INSUFFICIENT
    assert validator.calls == []
    assert adapter.calls == []


def test_environment_trace_mismatch_rejects_before_authorization_validator_or_adapter() -> None:
    claim = make_claim()
    other_claim = make_claim(environment=make_environment(identifier="env-456"))
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = TerminationAdapterStub()

    with pytest.raises(ValueError, match="trace to the claim context"):
        make_attempt(validator, adapter).attempt(claim, make_verdict(other_claim))

    assert validator.calls == []
    assert adapter.calls == []


def test_evaluation_time_trace_mismatch_rejects_before_validator_or_adapter() -> None:
    claim = make_claim()
    other_claim = make_claim(claim_time=CLAIM_TIME + timedelta(seconds=1))
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = TerminationAdapterStub()

    with pytest.raises(ValueError, match="trace to the claim context"):
        make_attempt(validator, adapter).attempt(claim, make_verdict(other_claim))

    assert validator.calls == []
    assert adapter.calls == []


def test_action_trace_mismatch_rejects_before_validator_or_adapter() -> None:
    claim = make_claim()
    verdict = make_verdict(claim)
    context = verdict.lock_participation.owner_approval_participation.prerequisite_status.readiness.association_set.context
    object.__setattr__(context, "requested_retirement", "release")
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM)
    adapter = TerminationAdapterStub()

    with pytest.raises(ValueError, match="trace to the claim context"):
        make_attempt(validator, adapter).attempt(claim, verdict)

    assert validator.calls == []
    assert adapter.calls == []


def test_adapter_request_failure_propagates_unchanged() -> None:
    claim = make_claim()
    error = RuntimeError("ec2 request failed")

    with pytest.raises(RuntimeError) as raised:
        make_attempt(
            ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
            TerminationAdapterStub(failure=error),
        ).attempt(claim, make_verdict(claim))

    assert raised.value is error


def test_non_accepted_adapter_outcome_is_returned_unchanged() -> None:
    claim = make_claim()
    adapter = TerminationAdapterStub(accepted=False)

    result = make_attempt(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        adapter,
    ).attempt(claim, make_verdict(claim))

    assert isinstance(result, EC2TerminationInvocation)
    assert result.outcome is EC2TerminationInvocationOutcome.EC2_TERMINATION_REQUEST_NOT_ACCEPTED
    assert result is not None
    assert result == EC2TerminationInvocation(adapter.calls[0], result.results)


def test_inputs_remain_unchanged() -> None:
    claim = make_claim()
    environment = claim.environment
    verdict = make_verdict(claim)
    lock_participation = verdict.lock_participation

    make_attempt(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        TerminationAdapterStub(),
    ).attempt(claim, verdict)

    assert claim.environment == environment
    assert verdict.lock_participation == lock_participation
    assert (
        verdict.lock_participation.owner_approval_participation.prerequisite_status.readiness.association_set.context.environment
        == environment
    )
