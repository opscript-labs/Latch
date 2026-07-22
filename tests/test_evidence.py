from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from latch.domain.evidence import Evidence, EvidenceInstant, EvidenceInterval, EvidenceTimeless

TEMPORAL_CONTEXT = EvidenceInstant(datetime(2026, 7, 23, 10, 0, tzinfo=UTC))


def test_evidence_constructs_with_required_semantic_members() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context=TEMPORAL_CONTEXT,
    )

    assert evidence.proposition == "cpu activity is below the approved retirement boundary"
    assert evidence.referent == "temporary-environment:env-123"
    assert evidence.source_provenance == "cloudwatch metric query at 2026-07-23T10:00:00Z"
    assert evidence.temporal_context == TEMPORAL_CONTEXT


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("proposition", ""),
        ("proposition", " "),
        ("referent", ""),
        ("referent", " "),
        ("source_provenance", ""),
        ("source_provenance", " "),
    ],
)
def test_evidence_rejects_empty_semantic_members(
    member_name: str, member_value: str
) -> None:
    values = {
        "proposition": "cpu activity is below the approved retirement boundary",
        "referent": "temporary-environment:env-123",
        "source_provenance": "cloudwatch metric query at 2026-07-23T10:00:00Z",
        "temporal_context": TEMPORAL_CONTEXT,
    }
    values[member_name] = member_value

    with pytest.raises(ValueError, match=member_name):
        Evidence(**values)


def test_evidence_is_equal_when_all_semantic_members_match() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context=TEMPORAL_CONTEXT,
    )
    same_evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context=TEMPORAL_CONTEXT,
    )

    assert evidence == same_evidence
    assert hash(evidence) == hash(same_evidence)


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("proposition", "network traffic is below the approved retirement boundary"),
        ("referent", "temporary-environment:env-456"),
        ("source_provenance", "cloudwatch metric query at 2026-07-23T11:00:00Z"),
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
        "source_provenance": "cloudwatch metric query at 2026-07-23T10:00:00Z",
        "temporal_context": TEMPORAL_CONTEXT,
    }
    changed_values = values.copy()
    changed_values[member_name] = member_value

    assert Evidence(**values) != Evidence(**changed_values)


def test_evidence_is_defined_in_latch_domain_not_provider_package() -> None:
    assert Evidence.__module__ == "latch.domain.evidence.evidence"


def test_evidence_is_immutable() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context=TEMPORAL_CONTEXT,
    )

    with pytest.raises(FrozenInstanceError):
        evidence.proposition = "network traffic is below the approved retirement boundary"


def test_evidence_rejects_invalid_temporal_context() -> None:
    with pytest.raises(ValueError, match="temporal_context"):
        Evidence(
            proposition="cpu activity is below the approved retirement boundary",
            referent="temporary-environment:env-123",
            source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
            temporal_context="observed during retirement review window",
        )
