from typing import Any
from unittest.mock import Mock

import pytest

from latch.application.retirement_admission_adapter import RetirementAdmissionAdapter
from latch.infrastructure.retirement_admission_lambda import create_lambda_handler


@pytest.fixture
def mock_adapter() -> Mock:
    return Mock(spec=RetirementAdmissionAdapter)


@pytest.fixture
def valid_payload() -> dict[str, Any]:
    return {
        "product_event_type": "RETIREMENT_ADMISSION_REQUESTED",
        "version": "1",
        "claim_time": "2026-07-23T10:00:00Z",
        "request": {
            "environment_identity": {
                "identifier": "env-123",
                "created_at": "2026-07-23T08:00:00Z",
                "ttl_expires_at": "2026-07-23T10:00:00Z",
                "owner": "team-platform",
                "resource_target_arns": [
                    "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
                ],
            },
            "retirement_claim_identity": "claim-token-123",
            "claimant_identity": "team-platform",
        },
    }


def test_valid_dict_delegated_unchanged_to_adapter(
    mock_adapter: Mock, valid_payload: dict[str, Any]
) -> None:
    expected_response = {"verdict": "safe", "claim_token": "token-123"}
    mock_adapter.handle.return_value = expected_response
    handler = create_lambda_handler(
        mock_adapter, default_producer_authority="RetirementAdmissionRequestProducer"
    )

    response = handler(valid_payload, None)

    mock_adapter.handle.assert_called_once_with(
        valid_payload, producer_authority="RetirementAdmissionRequestProducer"
    )
    assert response == expected_response


@pytest.mark.parametrize(
    "adapter_result",
    [
        {"verdict": "safe", "claim_token": "token-123"},
        {"verdict": "unsafe", "claim_token": "token-123"},
        {"verdict": "insufficient", "claim_token": "token-123"},
        {"claim_token": "token-123"},
    ],
)
def test_handler_returns_adapter_results_unchanged(
    mock_adapter: Mock, valid_payload: dict[str, Any], adapter_result: dict[str, Any]
) -> None:
    mock_adapter.handle.return_value = adapter_result
    handler = create_lambda_handler(
        mock_adapter, default_producer_authority="RetirementAdmissionRequestProducer"
    )

    response = handler(valid_payload, None)

    assert response == adapter_result


def test_non_dictionary_event_fails_closed_without_calling_adapter(mock_adapter: Mock) -> None:
    handler = create_lambda_handler(
        mock_adapter, default_producer_authority="RetirementAdmissionRequestProducer"
    )

    response = handler("not-a-dict", None)  # type: ignore[arg-type]

    mock_adapter.handle.assert_not_called()
    assert response == {"error": "Malformed transport payload"}
    assert "verdict" not in response


def test_adapter_validation_failure_returns_deterministic_malformed_payload(
    mock_adapter: Mock, valid_payload: dict[str, Any]
) -> None:
    mock_adapter.handle.side_effect = ValueError("Parsing error")
    handler = create_lambda_handler(
        mock_adapter, default_producer_authority="RetirementAdmissionRequestProducer"
    )

    response = handler(valid_payload, None)

    assert response == {"error": "Malformed transport payload"}
    assert "verdict" not in response


def test_unexpected_adapter_exception_returns_generic_internal_error_and_does_not_leak_details(
    mock_adapter: Mock, valid_payload: dict[str, Any]
) -> None:
    mock_adapter.handle.side_effect = RuntimeError("Database offline or AWS connection lost")
    handler = create_lambda_handler(
        mock_adapter, default_producer_authority="RetirementAdmissionRequestProducer"
    )

    response = handler(valid_payload, None)

    assert response == {"error": "Internal error"}
    assert "Database offline" not in str(response)
    assert "verdict" not in response


def test_factory_requires_adapter_instance() -> None:
    with pytest.raises(TypeError):
        create_lambda_handler(None)  # type: ignore[arg-type]
