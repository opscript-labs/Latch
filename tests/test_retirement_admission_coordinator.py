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
    OwnerRetirementApproval,
    RegisteredTargetOperationalEvidenceCoverage,
    RetirementAdmissionVerdict,
    RetirementLock,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import Evidence, EvidenceInstant, SourceProvenance
from latch.domain.execution import RetirementExecutionAuthorization
from latch.infrastructure.dynamodb_active_claim_validator import ActiveClaimValidationResult
from latch.infrastructure.retirement_admission_coordinator import (
    RetirementAdmissionCoordinator,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
CLAIM_TIME = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"


def make_environment(
    *,
    ttl_expires_at: datetime = TTL_EXPIRES_AT,
) -> Environment:
    return Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=ttl_expires_at,
        owner="team-platform",
        resource_target_arns={TARGET},
    )


def make_claim(
    *,
    environment: Environment | None = None,
    claim_time: datetime = CLAIM_TIME,
) -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(
        environment or make_environment(),
        claim_time,
    )


def make_context(claim: RetirementEvaluationClaim) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=claim.environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=claim.claim_time,
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


def make_readiness(
    claim: RetirementEvaluationClaim,
    associations: list[OperationalDimensionAssociation] | None = None,
) -> OperationalRetirementReadiness:
    context = make_context(claim)
    if associations is None:
        associations = [
            make_association(context, OperationalDimension.CPU_ACTIVITY),
            make_association(context, OperationalDimension.NETWORK_ACTIVITY),
        ]

    association_set = OperationalDimensionAssociationSet(context, associations)
    coverage = RegisteredTargetOperationalEvidenceCoverage(claim, association_set)
    return OperationalRetirementReadiness(coverage)


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


class EvidenceCollectionStub:
    def __init__(
        self,
        readiness: OperationalRetirementReadiness | None = None,
        failure: BaseException | None = None,
    ) -> None:
        self.readiness = readiness
        self.failure = failure
        self.calls: list[RetirementEvaluationClaim] = []

    def collect(self, claim: RetirementEvaluationClaim) -> OperationalRetirementReadiness:
        self.calls.append(claim)
        if self.failure is not None:
            raise self.failure

        if self.readiness is None:
            raise AssertionError("readiness was not configured")

        return self.readiness


class ActiveRegistrationAdapterStub:
    def __init__(
        self,
        approval: OwnerRetirementApproval | None = None,
        lock: RetirementLock | None = None,
        approval_failure: BaseException | None = None,
        lock_failure: BaseException | None = None,
    ) -> None:
        self.approval = approval
        self.lock = lock
        self.approval_failure = approval_failure
        self.lock_failure = lock_failure
        self.approval_calls: list[tuple[RetirementEvaluationClaim, AdmissionEvaluationContext]] = []
        self.lock_calls: list[Environment] = []

    def retrieve_owner_retirement_approval(
        self,
        claim: RetirementEvaluationClaim,
        context: AdmissionEvaluationContext,
    ) -> OwnerRetirementApproval | None:
        self.approval_calls.append((claim, context))
        if self.approval_failure is not None:
            raise self.approval_failure

        return self.approval

    def retrieve_retirement_lock(self, environment: Environment) -> RetirementLock | None:
        self.lock_calls.append(environment)
        if self.lock_failure is not None:
            raise self.lock_failure

        return self.lock


def make_coordinator(
    validator: ActiveClaimValidatorStub,
    collection: EvidenceCollectionStub,
    adapter: ActiveRegistrationAdapterStub,
) -> RetirementAdmissionCoordinator:
    return RetirementAdmissionCoordinator(
        active_claim_validator=validator,
        evidence_collection=collection,
        active_registration_adapter=adapter,
    )


def test_invalid_active_claim_returns_no_admission_result_before_collection() -> None:
    claim = make_claim()
    validator = ActiveClaimValidatorStub(ActiveClaimValidationResult.INVALID_ACTIVE_CLAIM)
    collection = EvidenceCollectionStub(make_readiness(claim))
    adapter = ActiveRegistrationAdapterStub()

    result = make_coordinator(validator, collection, adapter).evaluate(claim)

    assert result is None
    assert validator.calls == [claim]
    assert collection.calls == []
    assert adapter.approval_calls == []
    assert adapter.lock_calls == []


def test_ready_timing_eligible_approved_and_unlocked_claim_returns_safe_verdict() -> None:
    claim = make_claim()
    readiness = make_readiness(claim)
    context = readiness.association_set.context
    adapter = ActiveRegistrationAdapterStub(
        approval=OwnerRetirementApproval(context, "team-platform")
    )

    result = make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        EvidenceCollectionStub(readiness),
        adapter,
    ).evaluate(claim)

    assert isinstance(result, RetirementAdmissionVerdict)
    assert result.verdict is AdmissionVerdict.SAFE


def test_readiness_context_is_reused_for_approval_and_lock_retrieval() -> None:
    claim = make_claim()
    readiness = make_readiness(claim)
    context = readiness.association_set.context
    adapter = ActiveRegistrationAdapterStub(
        approval=OwnerRetirementApproval(context, "team-platform")
    )

    make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        EvidenceCollectionStub(readiness),
        adapter,
    ).evaluate(claim)

    assert adapter.approval_calls == [(claim, context)]
    assert adapter.approval_calls[0][1] is context
    assert adapter.lock_calls == [context.environment]
    assert adapter.lock_calls[0] is context.environment


def test_timing_ineligible_unresolved_readiness_returns_unsafe_verdict() -> None:
    claim = make_claim(
        environment=make_environment(ttl_expires_at=CLAIM_TIME + timedelta(minutes=5))
    )
    context = make_context(claim)
    readiness = make_readiness(
        claim,
        [make_association(context, OperationalDimension.CPU_ACTIVITY)],
    )
    adapter = ActiveRegistrationAdapterStub(
        approval=OwnerRetirementApproval(readiness.association_set.context, "team-platform")
    )

    result = make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        EvidenceCollectionStub(readiness),
        adapter,
    ).evaluate(claim)

    assert result is not None
    assert result.verdict is AdmissionVerdict.UNSAFE


def test_unresolved_readiness_with_valid_timing_returns_insufficient_verdict() -> None:
    claim = make_claim()
    context = make_context(claim)
    readiness = make_readiness(
        claim,
        [make_association(context, OperationalDimension.CPU_ACTIVITY)],
    )
    adapter = ActiveRegistrationAdapterStub(
        approval=OwnerRetirementApproval(readiness.association_set.context, "team-platform")
    )

    result = make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        EvidenceCollectionStub(readiness),
        adapter,
    ).evaluate(claim)

    assert result is not None
    assert result.verdict is AdmissionVerdict.INSUFFICIENT


def test_missing_approval_blocks_admission() -> None:
    claim = make_claim()
    readiness = make_readiness(claim)

    result = make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        EvidenceCollectionStub(readiness),
        ActiveRegistrationAdapterStub(),
    ).evaluate(claim)

    assert result is not None
    assert result.verdict is AdmissionVerdict.UNSAFE


def test_supplied_lock_blocks_admission() -> None:
    claim = make_claim()
    readiness = make_readiness(claim)
    context = readiness.association_set.context
    adapter = ActiveRegistrationAdapterStub(
        approval=OwnerRetirementApproval(context, "team-platform"),
        lock=RetirementLock(context.environment),
    )

    result = make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        EvidenceCollectionStub(readiness),
        adapter,
    ).evaluate(claim)

    assert result is not None
    assert result.verdict is AdmissionVerdict.UNSAFE


def test_collection_failure_propagates_unchanged() -> None:
    claim = make_claim()
    error = RuntimeError("collection failed")

    with pytest.raises(RuntimeError) as raised:
        make_coordinator(
            ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
            EvidenceCollectionStub(failure=error),
            ActiveRegistrationAdapterStub(),
        ).evaluate(claim)

    assert raised.value is error


def test_approval_retrieval_failure_propagates_unchanged() -> None:
    claim = make_claim()
    error = RuntimeError("approval retrieval failed")

    with pytest.raises(RuntimeError) as raised:
        make_coordinator(
            ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
            EvidenceCollectionStub(make_readiness(claim)),
            ActiveRegistrationAdapterStub(approval_failure=error),
        ).evaluate(claim)

    assert raised.value is error


def test_lock_retrieval_failure_propagates_unchanged() -> None:
    claim = make_claim()
    readiness = make_readiness(claim)
    context = readiness.association_set.context
    error = RuntimeError("lock retrieval failed")

    with pytest.raises(RuntimeError) as raised:
        make_coordinator(
            ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
            EvidenceCollectionStub(readiness),
            ActiveRegistrationAdapterStub(
                approval=OwnerRetirementApproval(context, "team-platform"),
                lock_failure=error,
            ),
        ).evaluate(claim)

    assert raised.value is error


def test_mismatched_readiness_context_is_rejected() -> None:
    claim = make_claim()
    other_claim = make_claim(claim_time=CLAIM_TIME + timedelta(seconds=1))

    with pytest.raises(ValueError, match="trace to the claim context"):
        make_coordinator(
            ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
            EvidenceCollectionStub(make_readiness(other_claim)),
            ActiveRegistrationAdapterStub(),
        ).evaluate(claim)


def test_coordinator_does_not_create_execution_authorization() -> None:
    claim = make_claim()
    readiness = make_readiness(claim)
    context = readiness.association_set.context

    result = make_coordinator(
        ActiveClaimValidatorStub(ActiveClaimValidationResult.VALID_ACTIVE_CLAIM),
        EvidenceCollectionStub(readiness),
        ActiveRegistrationAdapterStub(approval=OwnerRetirementApproval(context, "team-platform")),
    ).evaluate(claim)

    assert isinstance(result, RetirementAdmissionVerdict)
    assert not isinstance(result, RetirementExecutionAuthorization)
