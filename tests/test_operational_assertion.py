from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionOutcome,
    OperationalAssertionProjection,
)
from latch.domain.environment import Environment
from latch.domain.evidence import Evidence, EvidenceInstant, SourceProvenance

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def make_environment(identifier: str = "env-123") -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns={"arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"},
    )


def make_context(identifier: str = "env-123") -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=make_environment(identifier),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )


def make_evidence(
    proposition: str = "operational activity was observed",
    referent: str = "env-123",
    observed_at: datetime = EVALUATED_AT,
) -> Evidence:
    return Evidence(
        proposition=proposition,
        referent=referent,
        source_provenance=SourceProvenance(
            source_system="aws.cloudtrail.event",
            source_occurrence="cloudtrail event at 2026-07-23T10:00:00Z",
        ),
        temporal_context=EvidenceInstant(observed_at),
    )


def make_association(
    classification: EvidencePropositionClassification,
    evidence: Evidence | None = None,
) -> EvidencePropositionClassificationAssociation:
    if evidence is None:
        evidence = make_evidence()

    return EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=classification,
    )


def test_operational_assertion_outcome_has_exact_closed_vocabulary() -> None:
    assert list(OperationalAssertionOutcome) == [
        OperationalAssertionOutcome.ASSERTS_OPERATIONAL_ACTIVITY,
        OperationalAssertionOutcome.ASSERTS_OPERATIONAL_INACTIVITY,
        OperationalAssertionOutcome.NO_OPERATIONAL_ASSERTION,
    ]


def test_operational_activity_maps_to_activity_assertion() -> None:
    projection = OperationalAssertionProjection(
        association=make_association(EvidencePropositionClassification.OPERATIONAL_ACTIVITY),
        context=make_context(),
    )

    assert projection.outcome is OperationalAssertionOutcome.ASSERTS_OPERATIONAL_ACTIVITY


def test_operational_inactivity_maps_to_inactivity_assertion() -> None:
    projection = OperationalAssertionProjection(
        association=make_association(EvidencePropositionClassification.OPERATIONAL_INACTIVITY),
        context=make_context(),
    )

    assert projection.outcome is OperationalAssertionOutcome.ASSERTS_OPERATIONAL_INACTIVITY


def test_irrelevant_evidence_maps_to_no_operational_assertion() -> None:
    projection = OperationalAssertionProjection(
        association=make_association(
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            evidence=make_evidence(referent="env-456"),
        ),
        context=make_context(),
    )

    assert projection.outcome is OperationalAssertionOutcome.NO_OPERATIONAL_ASSERTION


def test_unclassified_evidence_maps_to_no_operational_assertion() -> None:
    projection = OperationalAssertionProjection(
        association=make_association(EvidencePropositionClassification.UNCLASSIFIED),
        context=make_context(),
    )

    assert projection.outcome is OperationalAssertionOutcome.NO_OPERATIONAL_ASSERTION


def test_operational_assertion_projection_is_immutable() -> None:
    projection = OperationalAssertionProjection(
        association=make_association(EvidencePropositionClassification.OPERATIONAL_ACTIVITY),
        context=make_context(),
    )

    with pytest.raises(FrozenInstanceError):
        projection.outcome = OperationalAssertionOutcome.NO_OPERATIONAL_ASSERTION


def test_equal_association_and_context_produce_equal_projections() -> None:
    association = make_association(EvidencePropositionClassification.OPERATIONAL_ACTIVITY)
    context = make_context()

    assert OperationalAssertionProjection(
        association=association,
        context=context,
    ) == OperationalAssertionProjection(
        association=association,
        context=context,
    )


def test_changing_association_changes_projection_identity_when_outcome_matches() -> None:
    context = make_context()

    projection = OperationalAssertionProjection(
        association=make_association(
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            evidence=make_evidence("cpu activity was observed"),
        ),
        context=context,
    )
    other_projection = OperationalAssertionProjection(
        association=make_association(
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            evidence=make_evidence("network traffic was observed"),
        ),
        context=context,
    )

    assert projection.outcome == other_projection.outcome
    assert projection != other_projection


def test_changing_context_changes_projection_identity() -> None:
    association = make_association(EvidencePropositionClassification.OPERATIONAL_ACTIVITY)

    projection = OperationalAssertionProjection(
        association=association,
        context=make_context("env-123"),
    )
    other_projection = OperationalAssertionProjection(
        association=association,
        context=AdmissionEvaluationContext(
            environment=make_environment("env-123"),
            requested_retirement=AdmissionRequest.RETIREMENT,
            evaluated_at=EVALUATED_AT + timedelta(seconds=1),
        ),
    )

    assert projection != other_projection


def test_outcome_is_derived_not_caller_supplied() -> None:
    with pytest.raises(TypeError):
        OperationalAssertionProjection(
            association=make_association(EvidencePropositionClassification.OPERATIONAL_ACTIVITY),
            context=make_context(),
            outcome=OperationalAssertionOutcome.NO_OPERATIONAL_ASSERTION,
        )


def test_operational_assertion_projection_does_not_mutate_inputs() -> None:
    evidence = make_evidence()
    association = make_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        evidence=evidence,
    )
    context = make_context()

    OperationalAssertionProjection(association=association, context=context)

    assert evidence == make_evidence()
    assert association == make_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        evidence=make_evidence(),
    )
    assert context == make_context()
