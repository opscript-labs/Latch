from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from latch.domain.admission import RetirementLock
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


def test_retirement_lock_has_environment_only_identity() -> None:
    environment = make_environment()

    lock = RetirementLock(environment)

    assert lock.environment == environment


def test_equivalent_environment_locks_are_equal_and_hash_equal() -> None:
    lock = RetirementLock(make_environment())
    same_lock = RetirementLock(make_environment())

    assert lock == same_lock
    assert hash(lock) == hash(same_lock)


def test_changed_environment_changes_lock_identity() -> None:
    assert RetirementLock(make_environment()) != RetirementLock(
        make_environment(identifier="env-456")
    )


def test_retirement_lock_is_immutable() -> None:
    lock = RetirementLock(make_environment())

    with pytest.raises(FrozenInstanceError):
        lock.environment = make_environment(identifier="env-456")


def test_retirement_lock_is_exported_from_admission_domain() -> None:
    assert RetirementLock.__module__.startswith("latch.domain.admission")
