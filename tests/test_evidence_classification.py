from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from latch.domain.admission import (
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
)
from latch.domain.evidence import Evidence, EvidenceInstant


def make_evidence(proposition: str = "cpu activity was observed") -> Evidence:
    return Evidence(
        proposition=proposition,
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context=EvidenceInstant(datetime(2026, 7, 23, 10, 0, tzinfo=UTC)),
    )


def test_evidence_proposition_classification_has_exact_closed_vocabulary() -> None:
    assert list(EvidencePropositionClassification) == [
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        EvidencePropositionClassification.UNCLASSIFIED,
    ]


def test_evidence_proposition_classification_association_constructs() -> None:
    evidence = make_evidence()

    association = EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )

    assert association.evidence == evidence
    assert association.classification is EvidencePropositionClassification.OPERATIONAL_ACTIVITY


def test_evidence_proposition_classification_association_equality() -> None:
    evidence = make_evidence()

    association = EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )
    same_association = EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )

    assert association == same_association


def test_evidence_proposition_classification_association_differs_by_evidence() -> None:
    association = EvidencePropositionClassificationAssociation(
        evidence=make_evidence("cpu activity was observed"),
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )
    other_association = EvidencePropositionClassificationAssociation(
        evidence=make_evidence("network traffic was observed"),
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )

    assert association != other_association


def test_evidence_proposition_classification_association_differs_by_classification() -> None:
    evidence = make_evidence()

    association = EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )
    other_association = EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
    )

    assert association != other_association


def test_evidence_proposition_classification_association_rejects_invalid_classification() -> None:
    with pytest.raises(ValueError, match="classification"):
        EvidencePropositionClassificationAssociation(
            evidence=make_evidence(),
            classification="OPERATIONAL_ACTIVITY",
        )


def test_evidence_proposition_classification_association_is_immutable() -> None:
    association = EvidencePropositionClassificationAssociation(
        evidence=make_evidence(),
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )

    with pytest.raises(FrozenInstanceError):
        association.classification = EvidencePropositionClassification.UNCLASSIFIED


def test_evidence_proposition_classification_association_does_not_mutate_evidence() -> None:
    evidence = make_evidence()

    EvidencePropositionClassificationAssociation(
        evidence=evidence,
        classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
    )

    assert evidence == make_evidence()
