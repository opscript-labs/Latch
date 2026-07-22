from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from latch.domain.admission import AdmissionEvaluationContext, AdmissionRequest
from latch.domain.environment import Environment

CREATED_AT = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
EVALUATED_AT = datetime(2026, 7, 22, 11, 0, tzinfo=UTC)


def make_environment(identifier: str = "env-123") -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
    )


def test_admission_evaluation_context_constructs_for_retirement_request() -> None:
    environment = make_environment()

    context = AdmissionEvaluationContext(
        environment=environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )

    assert context.environment == environment
    assert context.requested_retirement is AdmissionRequest.RETIREMENT
    assert context.evaluated_at == EVALUATED_AT


def test_admission_evaluation_context_normalizes_evaluation_time_to_utc() -> None:
    context = AdmissionEvaluationContext(
        environment=make_environment(),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=datetime(2026, 7, 22, 16, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    )

    assert context.evaluated_at == EVALUATED_AT


def test_admission_evaluation_context_rejects_unrecognized_action() -> None:
    with pytest.raises(ValueError, match="retirement"):
        AdmissionEvaluationContext(
            environment=make_environment(),
            requested_retirement="deployment",
            evaluated_at=EVALUATED_AT,
        )


def test_admission_evaluation_context_rejects_naive_evaluation_time() -> None:
    with pytest.raises(ValueError, match="evaluated_at"):
        AdmissionEvaluationContext(
            environment=make_environment(),
            requested_retirement=AdmissionRequest.RETIREMENT,
            evaluated_at=datetime(2026, 7, 22, 11, 0),
        )


def test_admission_evaluation_context_is_equal_when_identity_contents_match() -> None:
    context = AdmissionEvaluationContext(
        environment=make_environment(),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )
    same_context = AdmissionEvaluationContext(
        environment=make_environment(),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )

    assert context == same_context


def test_admission_evaluation_context_is_unequal_when_environment_differs() -> None:
    context = AdmissionEvaluationContext(
        environment=make_environment("env-123"),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )
    other_context = AdmissionEvaluationContext(
        environment=make_environment("env-456"),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )

    assert context != other_context


def test_admission_evaluation_context_is_unequal_when_evaluation_time_differs() -> None:
    context = AdmissionEvaluationContext(
        environment=make_environment(),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )
    other_context = AdmissionEvaluationContext(
        environment=make_environment(),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT + timedelta(seconds=1),
    )

    assert context != other_context


def test_admission_evaluation_context_is_immutable() -> None:
    context = AdmissionEvaluationContext(
        environment=make_environment(),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=EVALUATED_AT,
    )

    with pytest.raises(FrozenInstanceError):
        context.evaluated_at = EVALUATED_AT + timedelta(seconds=1)
