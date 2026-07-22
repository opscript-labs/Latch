from dataclasses import FrozenInstanceError

import pytest

from latch.domain.evidence import SourceProvenance


def test_source_provenance_equality_requires_both_members_equal() -> None:
    source_provenance = SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    )
    same_source_provenance = SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    )

    assert source_provenance == same_source_provenance
    assert hash(source_provenance) == hash(same_source_provenance)


def test_source_provenance_differs_when_source_system_differs() -> None:
    assert SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    ) != SourceProvenance(
        source_system="aws.cloudtrail.event",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    )


def test_source_provenance_differs_when_source_occurrence_differs() -> None:
    assert SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    ) != SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T11:00:00Z",
    )


def test_source_provenance_rejects_blank_members() -> None:
    with pytest.raises(ValueError, match="source_system"):
        SourceProvenance(source_system="", source_occurrence="occurrence")

    with pytest.raises(ValueError, match="source_occurrence"):
        SourceProvenance(source_system="source", source_occurrence=" ")


def test_source_provenance_is_immutable() -> None:
    source_provenance = SourceProvenance(
        source_system="aws.cloudwatch.metrics",
        source_occurrence="cloudwatch metric query at 2026-07-23T10:00:00Z",
    )

    with pytest.raises(FrozenInstanceError):
        source_provenance.source_occurrence = "changed"
