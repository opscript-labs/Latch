from dataclasses import FrozenInstanceError

import pytest

from latch.domain.evidence import Evidence


def test_evidence_constructs_with_required_semantic_members() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context="observed during retirement review window",
    )

    assert evidence.proposition == "cpu activity is below the approved retirement boundary"
    assert evidence.referent == "temporary-environment:env-123"
    assert evidence.source_provenance == "cloudwatch metric query at 2026-07-23T10:00:00Z"
    assert evidence.temporal_context == "observed during retirement review window"


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("proposition", ""),
        ("proposition", " "),
        ("referent", ""),
        ("referent", " "),
        ("source_provenance", ""),
        ("source_provenance", " "),
        ("temporal_context", ""),
        ("temporal_context", " "),
    ],
)
def test_evidence_rejects_empty_semantic_members(
    member_name: str, member_value: str
) -> None:
    values = {
        "proposition": "cpu activity is below the approved retirement boundary",
        "referent": "temporary-environment:env-123",
        "source_provenance": "cloudwatch metric query at 2026-07-23T10:00:00Z",
        "temporal_context": "observed during retirement review window",
    }
    values[member_name] = member_value

    with pytest.raises(ValueError, match=member_name):
        Evidence(**values)


def test_evidence_is_equal_when_all_semantic_members_match() -> None:
    evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context="observed during retirement review window",
    )
    same_evidence = Evidence(
        proposition="cpu activity is below the approved retirement boundary",
        referent="temporary-environment:env-123",
        source_provenance="cloudwatch metric query at 2026-07-23T10:00:00Z",
        temporal_context="observed during retirement review window",
    )

    assert evidence == same_evidence
    assert hash(evidence) == hash(same_evidence)


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("proposition", "network traffic is below the approved retirement boundary"),
        ("referent", "temporary-environment:env-456"),
        ("source_provenance", "cloudwatch metric query at 2026-07-23T11:00:00Z"),
        ("temporal_context", "observed during follow-up retirement review window"),
    ],
)
def test_evidence_is_unequal_when_exactly_one_semantic_member_differs(
    member_name: str, member_value: str
) -> None:
    values = {
        "proposition": "cpu activity is below the approved retirement boundary",
        "referent": "temporary-environment:env-123",
        "source_provenance": "cloudwatch metric query at 2026-07-23T10:00:00Z",
        "temporal_context": "observed during retirement review window",
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
        temporal_context="observed during retirement review window",
    )

    with pytest.raises(FrozenInstanceError):
        evidence.proposition = "network traffic is below the approved retirement boundary"
