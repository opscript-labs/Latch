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
    RetirementPrerequisiteStatus,
    RetirementPrerequisiteStatusOutcome,
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


def make_readiness(
    context: AdmissionEvaluationContext,
    associations: list[OperationalDimensionAssociation],
) -> OperationalRetirementReadiness:
    return OperationalRetirementReadiness(
        OperationalDimensionAssociationSet(context, associations)
    )


def make_ready_readiness(
    evaluated_at: datetime = TTL_EXPIRES_AT,
) -> OperationalRetirementReadiness:
    context = make_context(evaluated_at=evaluated_at)
    return make_readiness(
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


def test_retirement_prerequisite_status_has_exact_closed_vocabulary() -> None:
    assert list(RetirementPrerequisiteStatusOutcome) == [
        RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_SATISFIED,
        RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_NOT_SATISFIED,
        RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_UNRESOLVED,
    ]


def test_timing_eligible_and_ready_is_satisfied() -> None:
    status = RetirementPrerequisiteStatus(make_ready_readiness())

    assert (
        status.outcome
        is RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_SATISFIED
    )


def test_timing_not_eligible_and_ready_is_not_satisfied() -> None:
    status = RetirementPrerequisiteStatus(
        make_ready_readiness(TTL_EXPIRES_AT - timedelta(microseconds=1))
    )

    assert (
        status.outcome
        is RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_NOT_SATISFIED
    )


def test_timing_eligible_and_not_ready_is_not_satisfied() -> None:
    context = make_context()
    readiness = make_readiness(
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

    status = RetirementPrerequisiteStatus(readiness)

    assert (
        status.outcome
        is RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_NOT_SATISFIED
    )


def test_timing_eligible_and_unresolved_readiness_is_unresolved() -> None:
    context = make_context()
    readiness = make_readiness(
        context,
        [make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")],
    )

    status = RetirementPrerequisiteStatus(readiness)

    assert (
        status.outcome
        is RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_UNRESOLVED
    )


def test_timing_not_eligible_takes_precedence_over_unresolved_readiness() -> None:
    context = make_context(evaluated_at=TTL_EXPIRES_AT - timedelta(microseconds=1))
    readiness = make_readiness(
        context,
        [make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")],
    )

    status = RetirementPrerequisiteStatus(readiness)

    assert (
        status.outcome
        is RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_NOT_SATISFIED
    )


def test_identity_and_hashing_depend_only_on_readiness() -> None:
    readiness = make_ready_readiness()

    status = RetirementPrerequisiteStatus(readiness)
    same_status = RetirementPrerequisiteStatus(readiness)

    assert status == same_status
    assert hash(status) == hash(same_status)


def test_equivalent_readiness_artifacts_produce_equal_status() -> None:
    assert RetirementPrerequisiteStatus(make_ready_readiness()) == (
        RetirementPrerequisiteStatus(make_ready_readiness())
    )


def test_changed_readiness_artifact_produces_distinct_status() -> None:
    context = make_context()
    ready = make_ready_readiness()
    unresolved = make_readiness(
        context,
        [make_inactivity(context, OperationalDimension.CPU_ACTIVITY, "cpu inactive")],
    )

    assert RetirementPrerequisiteStatus(ready) != RetirementPrerequisiteStatus(
        unresolved
    )


def test_timing_eligibility_and_outcome_cannot_be_caller_supplied() -> None:
    readiness = make_ready_readiness()

    with pytest.raises(TypeError):
        RetirementPrerequisiteStatus(
            readiness=readiness,
            timing_eligibility=object(),
        )

    with pytest.raises(TypeError):
        RetirementPrerequisiteStatus(
            readiness=readiness,
            outcome=(
                RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_SATISFIED
            ),
        )


def test_retirement_prerequisite_status_is_immutable() -> None:
    status = RetirementPrerequisiteStatus(make_ready_readiness())

    with pytest.raises(FrozenInstanceError):
        status.outcome = (
            RetirementPrerequisiteStatusOutcome.RETIREMENT_PREREQUISITES_UNRESOLVED
        )


def test_retirement_prerequisite_status_does_not_mutate_upstream_artifacts() -> None:
    readiness = make_ready_readiness()
    association_set = readiness.association_set
    context = association_set.context
    environment = context.environment
    readiness_coverage = readiness.coverage
    readiness_conflict_status = readiness.conflict_status

    status = RetirementPrerequisiteStatus(readiness)

    assert status.readiness == readiness
    assert readiness.association_set == association_set
    assert readiness.coverage == readiness_coverage
    assert readiness.conflict_status == readiness_conflict_status
    assert association_set.context == context
    assert context.environment == environment
