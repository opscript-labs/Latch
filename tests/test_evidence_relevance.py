from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    is_evidence_relevant_to_context,
)
from latch.domain.environment import Environment
from latch.domain.evidence import Evidence, EvidenceInstant, EvidenceInterval, EvidenceTimeless

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def make_environment(identifier: str = "env-123") -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
    )


def make_context(identifier: str = "env-123") -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=make_environment(identifier),
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
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
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
