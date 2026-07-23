from unittest.mock import Mock, patch

import pytest

from latch.infrastructure.retirement_admission_lambda_entrypoint import (
    _build_handler,
    handle_event,
)


@pytest.fixture
def mock_session() -> Mock:
    session = Mock()
    session.client.return_value = Mock()
    return session


@pytest.fixture
def valid_env() -> dict[str, str]:
    return {
        "LATCH_DYNAMODB_REGION": "us-east-1",
        "LATCH_ACTIVE_REGISTRATION_TABLE": "latch-active-environments",
    }


def test_build_handler_success_creates_full_graph(
    mock_session: Mock,
    valid_env: dict[str, str],
) -> None:
    handler = _build_handler(mock_session, valid_env)
    assert callable(handler)

    mock_session.client.assert_any_call("dynamodb", region_name="us-east-1")
    mock_session.client.assert_any_call("cloudwatch", region_name="us-east-1")


@pytest.mark.parametrize(
    "env,match",
    [
        ({}, "LATCH_DYNAMODB_REGION is required"),
        ({"LATCH_DYNAMODB_REGION": ""}, "LATCH_DYNAMODB_REGION is required"),
        (
            {"LATCH_DYNAMODB_REGION": "invalid-region"},
            "LATCH_DYNAMODB_REGION must be a valid AWS Region",
        ),
        ({"LATCH_DYNAMODB_REGION": "us-east-1"}, "LATCH_ACTIVE_REGISTRATION_TABLE is required"),
        (
            {"LATCH_DYNAMODB_REGION": "us-east-1", "LATCH_ACTIVE_REGISTRATION_TABLE": ""},
            "LATCH_ACTIVE_REGISTRATION_TABLE is required",
        ),
        (
            {
                "LATCH_DYNAMODB_REGION": "us-east-1",
                "LATCH_ACTIVE_REGISTRATION_TABLE": "bad name!",
            },
            "LATCH_ACTIVE_REGISTRATION_TABLE must be a valid table name",
        ),
    ],
)
def test_build_handler_fails_closed_on_invalid_env(
    mock_session: Mock,
    env: dict[str, str],
    match: str,
) -> None:
    with pytest.raises(RuntimeError, match=match):
        _build_handler(mock_session, env)


def test_handle_event_caching_and_delegation(mock_session: Mock, valid_env: dict[str, str]) -> None:
    import latch.infrastructure.retirement_admission_lambda_entrypoint as entrypoint
    entrypoint._cached_handler = None

    event = {"version": "1"}
    mock_handler = Mock(return_value={"status": "success"})
    
    with (
        patch(
            "latch.infrastructure.retirement_admission_lambda_entrypoint.boto3.Session",
            return_value=mock_session,
        ),
        patch(
            "latch.infrastructure.retirement_admission_lambda_entrypoint._build_handler",
            return_value=mock_handler,
        ) as mock_builder,
        patch("os.environ", valid_env),
    ):
        result1 = handle_event(event)
        assert result1 == {"status": "success"}
        mock_builder.assert_called_once()
        mock_handler.assert_called_once_with(event, None)

        result2 = handle_event(event)
        assert result2 == {"status": "success"}
        assert mock_builder.call_count == 1
        assert mock_handler.call_count == 2


def test_handle_event_fails_closed_on_initialization_exception(mock_session: Mock) -> None:
    import latch.infrastructure.retirement_admission_lambda_entrypoint as entrypoint
    entrypoint._cached_handler = None

    with (
        patch(
            "latch.infrastructure.retirement_admission_lambda_entrypoint.boto3.Session",
            return_value=mock_session,
        ),
        patch(
            "latch.infrastructure.retirement_admission_lambda_entrypoint._build_handler",
            side_effect=RuntimeError("Config error"),
        ),
        patch("os.environ", {}),
    ):
        result = handle_event({"version": "1"})
        assert result == {"error": "Internal error"}
