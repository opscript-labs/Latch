from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    OwnerRetirementApproval,
)
from latch.domain.environment import Environment

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 13, 0, tzinfo=UTC)


def make_environment(
    *,
    identifier: str = "env-123",
    owner: str = "team-platform",
) -> Environment:
    return Environment(
        identifier=identifier,
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner=owner,
        resource_target_arns={"arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api"},
    )


def make_context(
    *,
    environment: Environment | None = None,
    evaluated_at: datetime = EVALUATED_AT,
) -> AdmissionEvaluationContext:
    if environment is None:
        environment = make_environment()

    return AdmissionEvaluationContext(
        environment=environment,
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=evaluated_at,
    )


def test_valid_exact_owner_approval() -> None:
    context = make_context()

    approval = OwnerRetirementApproval(
        context=context,
        approved_by="team-platform",
    )

    assert approval.context == context
    assert approval.approved_by == "team-platform"


def test_empty_owner_is_rejected() -> None:
    with pytest.raises(ValueError, match="approved_by"):
        OwnerRetirementApproval(
            context=make_context(),
            approved_by="",
        )


def test_whitespace_only_owner_is_rejected() -> None:
    with pytest.raises(ValueError, match="approved_by"):
        OwnerRetirementApproval(
            context=make_context(),
            approved_by="   ",
        )


def test_mismatched_owner_is_rejected() -> None:
    with pytest.raises(ValueError, match="environment owner"):
        OwnerRetirementApproval(
            context=make_context(),
            approved_by="team-security",
        )


def test_equivalent_approvals_for_same_context_are_equal_and_hash_equal() -> None:
    context = make_context()

    approval = OwnerRetirementApproval(context=context, approved_by="team-platform")
    same_approval = OwnerRetirementApproval(context=context, approved_by="team-platform")

    assert approval == same_approval
    assert hash(approval) == hash(same_approval)


def test_changed_context_produces_distinct_approval_identity() -> None:
    approval = OwnerRetirementApproval(
        context=make_context(),
        approved_by="team-platform",
    )
    changed_approval = OwnerRetirementApproval(
        context=make_context(environment=make_environment(identifier="env-456")),
        approved_by="team-platform",
    )

    assert approval != changed_approval


def test_approval_identity_depends_exclusively_on_context() -> None:
    context = make_context(environment=make_environment(owner="team-platform"))
    same_context = make_context(environment=make_environment(owner="team-platform"))

    assert OwnerRetirementApproval(context=context, approved_by="team-platform") == (
        OwnerRetirementApproval(context=same_context, approved_by="team-platform")
    )


def test_owner_retirement_approval_is_immutable() -> None:
    approval = OwnerRetirementApproval(
        context=make_context(),
        approved_by="team-platform",
    )

    with pytest.raises(FrozenInstanceError):
        approval.approved_by = "team-security"


def test_approval_construction_does_not_mutate_context_or_environment() -> None:
    environment = make_environment()
    context = make_context(environment=environment)

    approval = OwnerRetirementApproval(context=context, approved_by="team-platform")

    assert approval.context == context
    assert context.environment == environment
    assert environment.owner == "team-platform"


def test_owner_retirement_approval_is_exported_from_admission_domain() -> None:
    assert OwnerRetirementApproval.__module__.startswith("latch.domain.admission")
