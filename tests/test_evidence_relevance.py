from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionProjection,
    OperationalDimensionAssociation,
    OperationalRetirementReadiness,
    RetirementAdmissionVerdict,
    is_evidence_relevant_to_context,
)
from latch.domain.environment import Environment
from latch.domain.evidence import (
    Evidence,
    EvidenceInstant,
    EvidenceInterval,
    EvidenceTimeless,
    SourceProvenance,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"
SIMILAR_INSTANCE_ID_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef1"
SIMILAR_ACCOUNT_TARGET = "arn:aws:ec2:us-east-1:123456789013:instance/i-0123456789abcdef0"
SIMILAR_REGION_TARGET = "arn:aws:ec2:us-west-2:123456789012:instance/i-0123456789abcdef0"
SIMILAR_TEXT_TARGET = " arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"


def make_environment(
    identifier: str = "env-123",
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
) -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=resource_target_arns,
    )


def make_context(
    identifier: str = "env-123",
    resource_target_arns: frozenset[str] = frozenset({FIRST_TARGET}),
) -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=make_environment(identifier, resource_target_arns),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )


def make_evidence(
    referent: str = "env-123",
    temporal_context: EvidenceInstant | EvidenceInterval | EvidenceTimeless | None = None,
) -> Evidence:
    if temporal_context is None:
        temporal_context = EvidenceInstant(EVALUATED_AT)

    return Evidence(
        proposition="operational activity was observed",
        referent=referent,
        source_provenance=SourceProvenance(
            source_system="aws.cloudtrail.event",
            source_occurrence="cloudtrail event at 2026-07-23T10:00:00Z",
        ),
        temporal_context=temporal_context,
    )


def classify(
    evidence: Evidence,
    classification: EvidencePropositionClassification,
) -> EvidencePropositionClassificationAssociation:
    return EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=classification,
    )


@pytest.mark.parametrize(
    "classification",
    [
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
    ],
)
def test_evidence_is_relevant_for_operational_classifications_with_exact_environment(
    classification: EvidencePropositionClassification,
) -> None:
    assert is_evidence_relevant_to_context(
        classify(make_evidence(), classification),
        make_context(),
    )


def test_unclassified_evidence_is_not_relevant() -> None:
    assert (
        is_evidence_relevant_to_context(
            classify(make_evidence(), EvidencePropositionClassification.UNCLASSIFIED),
            make_context(),
        )
        is False
    )


def test_evidence_for_different_environment_is_not_relevant() -> None:
    assert (
        is_evidence_relevant_to_context(
            classify(
                make_evidence("env-456"),
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            ),
            make_context("env-123"),
        )
        is False
    )


def test_target_scoped_evidence_for_registered_target_is_relevant() -> None:
    assert is_evidence_relevant_to_context(
        classify(
            make_evidence(FIRST_TARGET),
            EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        ),
        make_context(),
    )


def test_target_scoped_evidence_for_non_member_target_is_irrelevant() -> None:
    assert (
        is_evidence_relevant_to_context(
            classify(
                make_evidence(SECOND_TARGET),
                EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
            ),
            make_context(),
        )
        is False
    )


@pytest.mark.parametrize(
    "referent",
    [
        SIMILAR_INSTANCE_ID_TARGET,
        SIMILAR_ACCOUNT_TARGET,
        SIMILAR_REGION_TARGET,
        SIMILAR_TEXT_TARGET,
    ],
)
def test_similar_target_referents_are_irrelevant_unless_exactly_registered(
    referent: str,
) -> None:
    assert (
        is_evidence_relevant_to_context(
            classify(
                make_evidence(referent),
                EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
            ),
            make_context(),
        )
        is False
    )


def test_changed_target_membership_changes_correspondence_for_distinct_context() -> None:
    first_context = make_context(resource_target_arns=frozenset({FIRST_TARGET}))
    second_context = make_context(resource_target_arns=frozenset({SECOND_TARGET}))
    association = classify(
        make_evidence(SECOND_TARGET),
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
    )

    assert first_context != second_context
    assert is_evidence_relevant_to_context(association, first_context) is False
    assert is_evidence_relevant_to_context(association, second_context) is True


def test_relevance_result_does_not_establish_downstream_behavior() -> None:
    relevance = is_evidence_relevant_to_context(
        classify(
            make_evidence(FIRST_TARGET),
            EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        ),
        make_context(),
    )

    assert relevance is True
    assert not isinstance(relevance, OperationalAssertionProjection)
    assert not isinstance(relevance, OperationalDimensionAssociation)
    assert not isinstance(relevance, OperationalRetirementReadiness)
    assert not isinstance(relevance, RetirementAdmissionVerdict)


@pytest.mark.parametrize(
    "temporal_context",
    [
        EvidenceInstant(EVALUATED_AT + timedelta(microseconds=1)),
        EvidenceInterval(
            start=EVALUATED_AT + timedelta(microseconds=1),
            end=EVALUATED_AT + timedelta(seconds=1),
        ),
    ],
)
def test_evidence_wholly_after_evaluation_time_is_not_relevant(
    temporal_context: EvidenceInstant | EvidenceInterval,
) -> None:
    assert (
        is_evidence_relevant_to_context(
            classify(
                make_evidence(temporal_context=temporal_context),
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            ),
            make_context(),
        )
        is False
    )


def test_instant_exactly_at_evaluation_time_is_relevant() -> None:
    assert is_evidence_relevant_to_context(
        classify(
            make_evidence(temporal_context=EvidenceInstant(EVALUATED_AT)),
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        ),
        make_context(),
    )


def test_interval_beginning_at_evaluation_time_is_relevant() -> None:
    assert is_evidence_relevant_to_context(
        classify(
            make_evidence(
                temporal_context=EvidenceInterval(
                    start=EVALUATED_AT,
                    end=EVALUATED_AT + timedelta(seconds=1),
                )
            ),
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        ),
        make_context(),
    )


def test_timeless_evidence_is_never_wholly_after_evaluation_time() -> None:
    assert is_evidence_relevant_to_context(
        classify(
            make_evidence(temporal_context=EvidenceTimeless()),
            EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        ),
        make_context(),
    )
