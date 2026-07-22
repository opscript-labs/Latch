from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    RetirementTimingEligibility,
    RetirementTimingEligibilityOutcome,
)
from latch.domain.environment import Environment

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def make_environment(identifier: str = "env-123") -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns={"arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api"},
    )


def make_context(
    *,
    environment: Environment | None = None,
    evaluated_at: datetime = TTL_EXPIRES_AT,
) -> AdmissionEvaluationContext:
    if environment is None:
        environment = make_environment()

    return AdmissionEvaluationContext(
        environment=environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=evaluated_at,
    )


def test_retirement_timing_eligibility_has_exact_closed_vocabulary() -> None:
    assert list(RetirementTimingEligibilityOutcome) == [
        RetirementTimingEligibilityOutcome.RETIREMENT_TIME_NOT_ELIGIBLE,
        RetirementTimingEligibilityOutcome.RETIREMENT_TIME_ELIGIBLE,
    ]


def test_pre_expiry_is_not_eligible() -> None:
    eligibility = RetirementTimingEligibility(
        context=make_context(evaluated_at=TTL_EXPIRES_AT - timedelta(microseconds=1))
    )

    assert (
        eligibility.outcome
        is RetirementTimingEligibilityOutcome.RETIREMENT_TIME_NOT_ELIGIBLE
    )


def test_exact_expiry_is_eligible() -> None:
    eligibility = RetirementTimingEligibility(
        context=make_context(evaluated_at=TTL_EXPIRES_AT)
    )

    assert (
        eligibility.outcome is RetirementTimingEligibilityOutcome.RETIREMENT_TIME_ELIGIBLE
    )


def test_post_expiry_is_eligible() -> None:
    eligibility = RetirementTimingEligibility(
        context=make_context(evaluated_at=TTL_EXPIRES_AT + timedelta(seconds=1))
    )

    assert (
        eligibility.outcome is RetirementTimingEligibilityOutcome.RETIREMENT_TIME_ELIGIBLE
    )


def test_identity_and_hashing_depend_only_on_context() -> None:
    context = make_context()

    eligibility = RetirementTimingEligibility(context=context)
    same_eligibility = RetirementTimingEligibility(context=context)

    assert eligibility == same_eligibility
    assert hash(eligibility) == hash(same_eligibility)


def test_equivalent_contexts_produce_equal_results() -> None:
    assert RetirementTimingEligibility(context=make_context()) == (
        RetirementTimingEligibility(context=make_context())
    )


def test_changed_environment_produces_distinct_result() -> None:
    assert RetirementTimingEligibility(context=make_context(environment=make_environment())) != (
        RetirementTimingEligibility(
            context=make_context(environment=make_environment(identifier="env-456"))
        )
    )


def test_changed_evaluation_time_produces_distinct_result() -> None:
    assert RetirementTimingEligibility(context=make_context(evaluated_at=TTL_EXPIRES_AT)) != (
        RetirementTimingEligibility(
            context=make_context(evaluated_at=TTL_EXPIRES_AT + timedelta(seconds=1))
        )
    )


def test_outcome_cannot_be_caller_supplied() -> None:
    with pytest.raises(TypeError):
        RetirementTimingEligibility(
            context=make_context(),
            outcome=RetirementTimingEligibilityOutcome.RETIREMENT_TIME_ELIGIBLE,
        )


def test_retirement_timing_eligibility_is_immutable() -> None:
    eligibility = RetirementTimingEligibility(context=make_context())

    with pytest.raises(FrozenInstanceError):
        eligibility.outcome = (
            RetirementTimingEligibilityOutcome.RETIREMENT_TIME_NOT_ELIGIBLE
        )


def test_retirement_timing_eligibility_preserves_context_and_environment() -> None:
    environment = make_environment()
    context = make_context(environment=environment)

    eligibility = RetirementTimingEligibility(context=context)

    assert eligibility.context == context
    assert eligibility.context.environment == environment
    assert context.environment == environment
