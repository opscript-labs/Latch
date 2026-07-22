from datetime import UTC, datetime, timedelta, timezone

import pytest

from latch.domain.evidence import EvidenceInstant, EvidenceInterval, EvidenceTimeless

EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def test_evidence_instant_constructs() -> None:
    temporal_context = EvidenceInstant(EVALUATED_AT)

    assert temporal_context.instant == EVALUATED_AT


def test_evidence_interval_constructs() -> None:
    temporal_context = EvidenceInterval(
        start=EVALUATED_AT,
        end=EVALUATED_AT + timedelta(minutes=5),
    )

    assert temporal_context.start == EVALUATED_AT
    assert temporal_context.end == EVALUATED_AT + timedelta(minutes=5)


def test_evidence_timeless_constructs_explicitly() -> None:
    assert isinstance(EvidenceTimeless(), EvidenceTimeless)


def test_evidence_instant_normalizes_aware_datetime_to_utc() -> None:
    temporal_context = EvidenceInstant(
        datetime(2026, 7, 23, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    )

    assert temporal_context.instant == EVALUATED_AT


def test_equivalent_timezone_aware_instants_normalize_to_equal_utc_contexts() -> None:
    assert EvidenceInstant(EVALUATED_AT) == EvidenceInstant(
        datetime(2026, 7, 23, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    )


def test_evidence_interval_normalizes_aware_bounds_to_utc() -> None:
    temporal_context = EvidenceInterval(
        start=datetime(2026, 7, 23, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        end=datetime(2026, 7, 23, 15, 35, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    )

    assert temporal_context.start == EVALUATED_AT
    assert temporal_context.end == EVALUATED_AT + timedelta(minutes=5)


def test_evidence_instant_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="instant"):
        EvidenceInstant(datetime(2026, 7, 23, 10, 0))


def test_evidence_interval_rejects_naive_start() -> None:
    with pytest.raises(ValueError, match="start"):
        EvidenceInterval(
            start=datetime(2026, 7, 23, 10, 0),
            end=EVALUATED_AT,
        )


def test_evidence_interval_rejects_naive_end() -> None:
    with pytest.raises(ValueError, match="end"):
        EvidenceInterval(
            start=EVALUATED_AT,
            end=datetime(2026, 7, 23, 10, 0),
        )


def test_evidence_interval_rejects_start_after_end() -> None:
    with pytest.raises(ValueError, match="start"):
        EvidenceInterval(
            start=EVALUATED_AT + timedelta(seconds=1),
            end=EVALUATED_AT,
        )


def test_evidence_interval_accepts_equal_closed_bounds() -> None:
    temporal_context = EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT)

    assert temporal_context.start == EVALUATED_AT
    assert temporal_context.end == EVALUATED_AT


def test_temporal_context_equality_requires_same_form_and_normalized_value() -> None:
    instant = EvidenceInstant(EVALUATED_AT)
    equivalent_instant = EvidenceInstant(
        datetime(2026, 7, 23, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    )
    equal_bound_interval = EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT)

    assert instant == equivalent_instant
    assert instant != equal_bound_interval


def test_different_interval_bounds_are_distinct() -> None:
    assert EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT) != EvidenceInterval(
        start=EVALUATED_AT,
        end=EVALUATED_AT + timedelta(microseconds=1),
    )


def test_timeless_equals_only_timeless() -> None:
    assert EvidenceTimeless() == EvidenceTimeless()
    assert EvidenceTimeless() != EvidenceInstant(EVALUATED_AT)
    assert EvidenceTimeless() != EvidenceInterval(start=EVALUATED_AT, end=EVALUATED_AT)
