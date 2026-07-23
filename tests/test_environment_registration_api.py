import os
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient

from latch.main import app

CREATED_AT = "2026-07-23T13:30:00+05:30"
TTL_EXPIRES_AT = "2026-07-23T15:30:00+05:30"
FIRST_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
SECOND_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


@contextmanager
def configured_client(dynamodb_client: Mock | None = None) -> Iterator[TestClient]:
    if dynamodb_client is None:
        dynamodb_client = Mock()

    session = Mock()
    session.client.return_value = dynamodb_client
    with (
        patch.dict(
            os.environ,
            {
                "LATCH_DYNAMODB_REGION": "us-east-1",
                "LATCH_ACTIVE_REGISTRATION_TABLE": "latch-active-environments",
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task",
            },
            clear=True,
        ),
        patch("latch.main.create_ecs_task_role_session", return_value=session) as factory,
        TestClient(app) as client,
    ):
        client.aws_session = session  # type: ignore[attr-defined]
        client.credentials_factory = factory  # type: ignore[attr-defined]
        client.dynamodb_client = dynamodb_client  # type: ignore[attr-defined]
        yield client


def valid_request() -> dict[str, object]:
    return {
        "identifier": "env-123",
        "owner": "team-platform",
        "created_at": CREATED_AT,
        "ttl_expires_at": TTL_EXPIRES_AT,
        "resource_target_arns": [SECOND_TARGET, FIRST_TARGET],
    }


def conditional_failure() -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "condition failed",
            }
        },
        "PutItem",
    )


def service_failure() -> ClientError:
    return ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "service unavailable"}},
        "PutItem",
    )


def transaction_conditional_failure() -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "transaction cancelled",
            },
            "CancellationReasons": [{"Code": "ConditionalCheckFailed"}],
        },
        "TransactWriteItems",
    )


def ambiguous_transaction_failure() -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "transaction cancelled",
            }
        },
        "TransactWriteItems",
    )


def test_valid_request_returns_created_deterministic_projection() -> None:
    with configured_client() as client:
        response = client.post("/environments", json=valid_request())

    assert response.status_code == 201
    assert response.json() == {
        "identifier": "env-123",
        "owner": "team-platform",
        "created_at": "2026-07-23T08:00:00Z",
        "ttl_expires_at": "2026-07-23T10:00:00Z",
        "resource_target_arns": sorted([FIRST_TARGET, SECOND_TARGET]),
    }


def test_target_arns_are_returned_in_lexicographic_order() -> None:
    with configured_client() as client:
        response = client.post("/environments", json=valid_request())

    assert response.json()["resource_target_arns"] == [FIRST_TARGET, SECOND_TARGET]


def test_timestamps_are_returned_as_normalized_utc_rfc3339_values() -> None:
    with configured_client() as client:
        response = client.post("/environments", json=valid_request())

    assert response.json()["created_at"] == "2026-07-23T08:00:00Z"
    assert response.json()["ttl_expires_at"] == "2026-07-23T10:00:00Z"


def test_extra_request_member_returns_422() -> None:
    request = valid_request()
    request["unexpected"] = "value"

    with configured_client() as client:
        response = client.post("/environments", json=request)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("member_name", "member_value"),
    [
        ("identifier", ""),
        ("owner", " "),
        ("created_at", "2026-07-23T08:00:00"),
        ("ttl_expires_at", "2026-07-23T07:59:59Z"),
        ("resource_target_arns", []),
        (
            "resource_target_arns",
            ["arn:aws:s3:us-east-1:123456789012:instance/i-0123456789abcdef0"],
        ),
    ],
)
def test_malformed_or_invariant_violating_environment_request_returns_422(
    member_name: str,
    member_value: object,
) -> None:
    request = valid_request()
    request[member_name] = member_value

    with configured_client() as client:
        response = client.post("/environments", json=request)

    assert response.status_code == 422


def test_duplicate_conditional_failure_returns_409() -> None:
    dynamodb_client = Mock()
    dynamodb_client.transact_write_items.side_effect = transaction_conditional_failure()

    with configured_client(dynamodb_client) as client:
        response = client.post("/environments", json=valid_request())

    assert response.status_code == 409
    assert response.json() == {"detail": "environment already registered"}


@pytest.mark.parametrize(
    "error",
    [
        service_failure(),
        ambiguous_transaction_failure(),
        EndpointConnectionError(endpoint_url="x"),
    ],
)
def test_dynamodb_service_or_transport_failure_returns_503(error: BaseException) -> None:
    dynamodb_client = Mock()
    dynamodb_client.transact_write_items.side_effect = error

    with configured_client(dynamodb_client) as client:
        response = client.post("/environments", json=valid_request())

    assert response.status_code == 503
    assert response.json() == {"detail": "environment registration unavailable"}


def test_exactly_one_registration_attempt_per_request() -> None:
    dynamodb_client = Mock()

    with configured_client(dynamodb_client) as client:
        client.post("/environments", json=valid_request())

    dynamodb_client.transact_write_items.assert_called_once()


def test_valid_startup_does_not_make_dynamodb_request() -> None:
    dynamodb_client = Mock()

    with configured_client(dynamodb_client):
        pass

    dynamodb_client.put_item.assert_not_called()
    dynamodb_client.delete_item.assert_not_called()
    dynamodb_client.transact_write_items.assert_not_called()


@pytest.mark.parametrize(
    "missing_name",
    ["LATCH_DYNAMODB_REGION", "LATCH_ACTIVE_REGISTRATION_TABLE"],
)
def test_missing_required_configuration_value_prevents_startup(
    missing_name: str,
) -> None:
    environment = {
        "LATCH_DYNAMODB_REGION": "us-east-1",
        "LATCH_ACTIVE_REGISTRATION_TABLE": "latch-active-environments",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task",
    }
    environment.pop(missing_name)

    with (
        patch.dict(os.environ, environment, clear=True),
        patch("latch.main.create_ecs_task_role_session", return_value=Mock()),
        pytest.raises(RuntimeError, match=missing_name),TestClient(app)
    ):
        pass


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LATCH_DYNAMODB_REGION", "not-a-region"),
        ("LATCH_ACTIVE_REGISTRATION_TABLE", "x"),
        ("LATCH_ACTIVE_REGISTRATION_TABLE", "bad table"),
    ],
)
def test_blank_or_invalid_configuration_value_prevents_startup(
    name: str,
    value: str,
) -> None:
    environment = {
        "LATCH_DYNAMODB_REGION": "us-east-1",
        "LATCH_ACTIVE_REGISTRATION_TABLE": "latch-active-environments",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task",
    }
    environment[name] = value

    with (
        patch.dict(os.environ, environment, clear=True),
        patch("latch.main.create_ecs_task_role_session", return_value=Mock()),
        pytest.raises(RuntimeError),TestClient(app)
    ):
        pass


def test_invalid_ecs_credential_source_configuration_prevents_startup() -> None:
    with (
        patch.dict(
            os.environ,
            {
                "LATCH_DYNAMODB_REGION": "us-east-1",
                "LATCH_ACTIVE_REGISTRATION_TABLE": "latch-active-environments",
            },
            clear=True,
        ),
        pytest.raises(RuntimeError, match="ECS task-role credentials"),TestClient(app)
    ):
        pass


def test_no_default_credential_chain_static_credentials_or_alternate_source_is_used() -> None:
    with configured_client() as client:
        client.credentials_factory.assert_called_once_with()  # type: ignore[attr-defined]
        client.aws_session.client.assert_called_once_with(  # type: ignore[attr-defined]
            "dynamodb",
            region_name="us-east-1",
        )


def test_health_endpoint_remains_available_with_valid_configuration() -> None:
    with configured_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Latch",
        "version": "0.1.0",
        "status": "healthy",
    }
