from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime

import pytest

from latch.domain.evidence import (
    Evidence,
    EvidenceInstant,
    EvidenceInterval,
    EvidenceTimeless,
    SourceProvenance,
)

TEMPORAL_CONTEXT = EvidenceInstant(datetime(2026, 7, 23, 10, 0, tzinfo=UTC))
SOURCE_PROVENANCE = SourceProvenance(
    source_system="aws.cloudwatch.metrics",
    source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
)


def test_evidence_constructs_with_required_semantic_members() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance=SOURCE_PROVENANCE,
        temporal_context=TEMPORAL_CONTEXT,
    )

    assert evidence.proposition == "cpu activity is below the approved retirement boundary"
    assert evidence.referent == "temporary-environment:env-123"
    assert evidence.source_provenance == SOURCE_PROVENANCE
    assert evidence.temporal_context == TEMPORAL_CONTEXT


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("proposition", ""),
        ("proposition", " "),
        ("referent", ""),
        ("referent", " "),
    ],
)
def test_evidence_rejects_empty_semantic_members(
    member_name: str, member_value: str
) -> None:
    values = {
        "proposition": "cpu activity is below the approved retirement boundary",
        "referent": "temporary-environment:env-123",
        "source_provenance": SOURCE_PROVENANCE,
        "temporal_context": TEMPORAL_CONTEXT,
    }
    values[member_name] = member_value

    with pytest.raises(ValueError, match=member_name):
        Evidence(**values)


def test_evidence_is_equal_when_all_semantic_members_match() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance=SOURCE_PROVENANCE,
        temporal_context=TEMPORAL_CONTEXT,
    )
    same_evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance=SOURCE_PROVENANCE,
        temporal_context=TEMPORAL_CONTEXT,
    )

    assert evidence == same_evidence
    assert hash(evidence) == hash(same_evidence)


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("proposition", "network traffic is below the approved retirement boundary"),
        ("referent", "temporary-environment:env-456"),
        (
            "source_provenance",
            SourceProvenance(
                source_system="aws.cloudwatch.metrics",
                source_occurrence="cloudwatch metric query at 2026-07-23T11:00:00Z",
            ),
        ),
        (
            "source_provenance",
            SourceProvenance(
                source_system="aws.cloudtrail.event",
                source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
            ),
        ),
        ("temporal_context", EvidenceInstant(datetime(2026, 7, 23, 11, 0, tzinfo=UTC))),
        ("temporal_context", EvidenceInterval(TEMPORAL_CONTEXT.instant, TEMPORAL_CONTEXT.instant)),
        ("temporal_context", EvidenceTimeless()),
    ],
)
def test_evidence_is_unequal_when_exactly_one_semantic_member_differs(
    member_name: str, member_value: str
) -> None:
    values = {
        "proposition": "cpu activity is below the approved retirement boundary",
        "referent": "temporary-environment:env-123",
        "source_provenance": SOURCE_PROVENANCE,
        "temporal_context": TEMPORAL_CONTEXT,
    }
    changed_values = values.copy()
    changed_values[member_name] = member_value

    assert Evidence(**values) != Evidence(**changed_values)


def test_evidence_equality_requires_exact_proposition_content() -> None:
    values = {
        "proposition": "cpu activity is below the approved retirement boundary",
        "referent": "temporary-environment:env-123",
        "source_provenance": SOURCE_PROVENANCE,
        "temporal_context": TEMPORAL_CONTEXT,
    }
    changed_values = {
        **values,
        "proposition": "cpu usage is below the approved retirement boundary",
    }

    assert Evidence(**values) != Evidence(**changed_values)


def test_evidence_equality_requires_exact_referent_content() -> None:
    values = {
        "proposition": "cpu activity is below the approved retirement boundary",
        "referent": "temporary-environment:env-123",
        "source_provenance": SOURCE_PROVENANCE,
        "temporal_context": TEMPORAL_CONTEXT,
    }
    changed_values = {
        **values,
        "referent": "env/env-123",
    }

    assert Evidence(**values) != Evidence(**changed_values)


def test_evidence_has_only_four_canonical_identity_bearing_contents() -> None:
    assert [field.name for field in fields(Evidence)] == [
        "proposition",
        "referent",
        "source_provenance",
        "temporal_context",
    ]


def test_evidence_is_defined_in_latch_domain_not_provider_package() -> None:
    assert Evidence.__module__ == "latch.domain.evidence.evidence"


def test_evidence_is_immutable() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance=SOURCE_PROVENANCE,
        temporal_context=TEMPORAL_CONTEXT,
    )

    with pytest.raises(FrozenInstanceError):
        evidence.proposition = "network traffic is below the approved retirement boundary"


def test_source_provenance_constructs_with_required_members() -> None:
    source_provenance = SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    )

    assert source_provenance.source_system == "aws.cloudwatch.metrics"
    assert (
        source_provenance.source_occurrence
        == "cloudwatch metric query at 2026-07-23T10:00:00Z"
    )


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("source_system", ""),
        ("source_system", " "),
        ("source_occurrence", ""),
        ("source_occurrence", " "),
    ],
)
def test_source_provenance_rejects_blank_members(
    member_name: str, member_value: str
) -> None:
    values = {
        "source_system": "aws.cloudwatch.metrics",
        "source_occurrence": "cloudwatch metric query at 2026-07-23T10:00:00Z",
    }
    values[member_name] = member_value

    with pytest.raises(ValueError, match=member_name):
        SourceProvenance(**values)


def test_source_provenance_is_immutable() -> None:
    source_provenance = SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    )

    with pytest.raises(FrozenInstanceError):
        source_provenance.source_system = "aws.cloudtrail.event"


def test_evidence_rejects_invalid_temporal_context() -> None:
    with pytest.raises(ValueError, match="temporal_context"):
        Evidence(
            proposition="cpu activity is below the approved retirement boundary",
            referent="temporary-environment:env-123",
            source_provenance=SOURCE_PROVENANCE,
            temporal_context="observed during retirement review window",
        )


@pytest.mark.parametrize("temporal_context", [None, "", "unknown"])
def test_evidence_rejects_absent_empty_or_unknown_temporal_context(
    temporal_context: object,
) -> None:
    with pytest.raises(ValueError, match="temporal_context"):
        Evidence(
            proposition="cpu activity is below the approved retirement boundary",
            referent="temporary-environment:env-123",
            source_provenance=SOURCE_PROVENANCE,
            temporal_context=temporal_context,
        )


def test_evidence_rejects_invalid_source_provenance() -> None:
    with pytest.raises(ValueError, match="source_provenance"):
        Evidence(
            proposition="cpu activity is below the approved retirement boundary",
            referent="temporary-environment:env-123",
            source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
            temporal_context=TEMPORAL_CONTEXT,
        )
