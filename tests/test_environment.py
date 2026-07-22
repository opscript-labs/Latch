from datetime import UTC, datetime, timedelta

import pytest

from latch.domain.environment import Environment

CREATED_AT = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
TTL_EXPIRES_AT = CREATED_AT + timedelta(hours=2)
RESOURCE_TARGET_ARNS = frozenset(
    {
        "arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api",
        "arn:aws:dynamodb:us-east-1:123456789012:table/temp-api",
    }
)


def test_environment_constructs_with_valid_lifecycle_fields() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=RESOURCE_TARGET_ARNS,
    )

    assert environment.identifier == "env-123"
    assert environment.created_at == CREATED_AT
    assert environment.ttl_expires_at == TTL_EXPIRES_AT
    assert environment.owner == "team-platform"
    assert environment.resource_target_arns == RESOURCE_TARGET_ARNS


def test_environment_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError, match="identifier"):
        Environment(
            identifier=" ",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns=RESOURCE_TARGET_ARNS,
        )


def test_environment_rejects_empty_owner() -> None:
    with pytest.raises(ValueError, match="owner"):
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner=" ",
            resource_target_arns=RESOURCE_TARGET_ARNS,
        )


def test_environment_rejects_empty_target_set() -> None:
    with pytest.raises(ValueError, match="resource_target_arns"):
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns=frozenset(),
        )


@pytest.mark.parametrize("resource_target_arn", ["", " "])
def test_environment_rejects_empty_resource_target_values(
    resource_target_arn: str,
) -> None:
    with pytest.raises(ValueError, match="resource_target_arns"):
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns={resource_target_arn},
        )


def test_environment_duplicate_targets_collapse() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=[
            "arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api",
            "arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api",
        ],
    )

    assert environment.resource_target_arns == frozenset(
        {"arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api"}
    )


def test_environment_target_order_does_not_affect_equality_or_hashing() -> None:
    first = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=[
            "arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api",
            "arn:aws:dynamodb:us-east-1:123456789012:table/temp-api",
        ],
    )
    second = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=[
            "arn:aws:dynamodb:us-east-1:123456789012:table/temp-api",
            "arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api",
        ],
    )

    assert first == second
    assert hash(first) == hash(second)


def test_changed_target_membership_creates_distinct_environment_identity() -> None:
    first = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns={
            "arn:aws:ecs:us-east-1:123456789012:service/demo/temp-api"
        },
    )
    second = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns={
            "arn:aws:dynamodb:us-east-1:123456789012:table/temp-api"
        },
    )

    assert first != second


def test_environment_targets_are_immutable() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=RESOURCE_TARGET_ARNS,
    )

    with pytest.raises(AttributeError):
        environment.resource_target_arns.add(
            "arn:aws:s3:::temporary-environment-artifacts"
        )


def test_environment_rejects_ttl_expiry_equal_to_creation_time() -> None:
    with pytest.raises(ValueError, match="later than created_at"):
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=CREATED_AT,
            owner="team-platform",
            resource_target_arns=RESOURCE_TARGET_ARNS,
        )


def test_environment_rejects_ttl_expiry_before_creation_time() -> None:
    with pytest.raises(ValueError, match="later than created_at"):
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=CREATED_AT - timedelta(seconds=1),
            owner="team-platform",
            resource_target_arns=RESOURCE_TARGET_ARNS,
        )


def test_environment_rejects_naive_creation_timestamp() -> None:
    with pytest.raises(ValueError, match="created_at"):
        Environment(
            identifier="env-123",
            created_at=datetime(2026, 7, 22, 10, 0),
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns=RESOURCE_TARGET_ARNS,
        )


def test_environment_rejects_naive_ttl_expiry_timestamp() -> None:
    with pytest.raises(ValueError, match="ttl_expires_at"):
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=datetime(2026, 7, 22, 12, 0),
            owner="team-platform",
            resource_target_arns=RESOURCE_TARGET_ARNS,
        )


def test_environment_ttl_is_not_expired_before_expiry() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=RESOURCE_TARGET_ARNS,
    )

    assert environment.is_ttl_expired(TTL_EXPIRES_AT - timedelta(microseconds=1)) is False


def test_environment_ttl_is_expired_at_exact_expiry() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=RESOURCE_TARGET_ARNS,
    )

    assert environment.is_ttl_expired(TTL_EXPIRES_AT) is True


def test_environment_ttl_is_expired_after_expiry() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=RESOURCE_TARGET_ARNS,
    )

    assert environment.is_ttl_expired(TTL_EXPIRES_AT + timedelta(seconds=1)) is True


def test_environment_rejects_naive_expiry_query_timestamp() -> None:
    environment = Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=RESOURCE_TARGET_ARNS,
    )

    with pytest.raises(ValueError, match="now"):
        environment.is_ttl_expired(datetime(2026, 7, 22, 12, 0))
