import os
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import CredentialRetrievalError

from latch.infrastructure.ecs_task_role_credentials import (
    ECSTaskRoleCredentialError,
    create_ecs_task_role_session,
)


def test_valid_relative_uri_uses_only_container_provider() -> None:
    credential_resolver = Mock()
    container_provider = Mock()
    botocore_session = Mock()
    boto3_session = Mock()
    boto3_session.get_credentials.return_value = object()

    with (
        patch.dict(
            os.environ,
            {"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task"},
            clear=True,
        ),
        patch(
            "latch.infrastructure.ecs_task_role_credentials.ContainerProvider"
        ) as container_provider_factory,
        patch(
            "latch.infrastructure.ecs_task_role_credentials.CredentialResolver"
        ) as resolver_factory,
        patch(
            "latch.infrastructure.ecs_task_role_credentials.BotocoreSession"
        ) as botocore_session_factory,
        patch(
            "latch.infrastructure.ecs_task_role_credentials.boto3.Session"
        ) as boto3_session_factory,
    ):
        container_provider_factory.return_value = container_provider
        resolver_factory.return_value = credential_resolver
        botocore_session_factory.return_value = botocore_session
        boto3_session_factory.return_value = boto3_session

        session = create_ecs_task_role_session()

    assert session == boto3_session
    container_provider_factory.assert_called_once_with(
        environ={"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task"}
    )
    resolver_factory.assert_called_once_with([container_provider])
    botocore_session.register_component.assert_called_once_with(
        "credential_provider",
        credential_resolver,
    )
    boto3_session_factory.assert_called_once_with(botocore_session=botocore_session)
    boto3_session.get_credentials.assert_called_once_with()


def test_root_relative_uri_is_valid_and_reaches_container_provider() -> None:
    boto3_session = Mock()
    boto3_session.get_credentials.return_value = object()

    with (
        patch.dict(
            os.environ,
            {"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/"},
            clear=True,
        ),
        patch(
            "latch.infrastructure.ecs_task_role_credentials.ContainerProvider"
        ) as container_provider_factory,
        patch("latch.infrastructure.ecs_task_role_credentials.CredentialResolver"),
        patch("latch.infrastructure.ecs_task_role_credentials.BotocoreSession"),
        patch(
            "latch.infrastructure.ecs_task_role_credentials.boto3.Session",
            return_value=boto3_session,
        ),
    ):
        create_ecs_task_role_session()

    container_provider_factory.assert_called_once_with(
        environ={"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/"}
    )


def test_missing_relative_uri_fails_closed() -> None:
    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(ECSTaskRoleCredentialError, match="required"),
    ):
        create_ecs_task_role_session()


@pytest.mark.parametrize(
    "relative_uri",
    [
        "https://169.254.170.2/v2/credentials/task",
        "//169.254.170.2/v2/credentials/task",
        "/v2/credentials/task?token=value",
        "/v2/credentials/task#fragment",
        " /v2/credentials/task",
        "/v2/credentials/task ",
        "v2/credentials/task",
    ],
)
def test_invalid_relative_uri_forms_fail_closed(relative_uri: str) -> None:
    with (
        patch.dict(
            os.environ,
            {"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": relative_uri},
            clear=True,
        ),
        pytest.raises(ECSTaskRoleCredentialError, match="relative path"),
    ):
        create_ecs_task_role_session()


def test_static_aws_credentials_cannot_become_credential_source() -> None:
    with (
        patch.dict(
            os.environ,
            {
                "AWS_ACCESS_KEY_ID": "static-key",
                "AWS_SECRET_ACCESS_KEY": "static-secret",
            },
            clear=True,
        ),
        pytest.raises(ECSTaskRoleCredentialError, match="required"),
    ):
        create_ecs_task_role_session()


def test_full_uri_and_authorization_token_settings_are_not_passed_to_provider() -> None:
    boto3_session = Mock()
    boto3_session.get_credentials.return_value = object()

    with (
        patch.dict(
            os.environ,
            {
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task",
                "AWS_CONTAINER_CREDENTIALS_FULL_URI": "https://example.test/creds",
                "AWS_CONTAINER_AUTHORIZATION_TOKEN": "token",
            },
            clear=True,
        ),
        patch(
            "latch.infrastructure.ecs_task_role_credentials.ContainerProvider"
        ) as container_provider_factory,
        patch("latch.infrastructure.ecs_task_role_credentials.CredentialResolver"),
        patch("latch.infrastructure.ecs_task_role_credentials.BotocoreSession"),
        patch(
            "latch.infrastructure.ecs_task_role_credentials.boto3.Session",
            return_value=boto3_session,
        ),
    ):
        create_ecs_task_role_session()

    container_provider_factory.assert_called_once_with(
        environ={"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task"}
    )


def test_provider_failure_fails_closed() -> None:
    boto3_session = Mock()
    boto3_session.get_credentials.side_effect = CredentialRetrievalError(
        provider="container-role",
        error_msg="not available",
    )

    with (
        patch.dict(
            os.environ,
            {"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/task"},
            clear=True,
        ),
        patch("latch.infrastructure.ecs_task_role_credentials.ContainerProvider"),
        patch("latch.infrastructure.ecs_task_role_credentials.CredentialResolver"),
        patch("latch.infrastructure.ecs_task_role_credentials.BotocoreSession"),
        patch(
            "latch.infrastructure.ecs_task_role_credentials.boto3.Session",
            return_value=boto3_session,
        ),
        pytest.raises(ECSTaskRoleCredentialError, match="unavailable"),
    ):
        create_ecs_task_role_session()
