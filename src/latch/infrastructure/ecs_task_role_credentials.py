import os
from urllib.parse import urlsplit

import boto3  # type: ignore[import-untyped]
from botocore.credentials import (  # type: ignore[import-untyped]
    ContainerProvider,
    CredentialResolver,
)
from botocore.exceptions import BotoCoreError  # type: ignore[import-untyped]
from botocore.session import Session as BotocoreSession  # type: ignore[import-untyped]

ECS_RELATIVE_URI_ENV_VAR = "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"


class ECSTaskRoleCredentialError(RuntimeError):
    pass


def create_ecs_task_role_session() -> boto3.Session:
    environ = _validated_container_provider_environ()
    botocore_session = BotocoreSession()
    botocore_session.register_component(
        "credential_provider",
        CredentialResolver([ContainerProvider(environ=environ)]),
    )
    session = boto3.Session(botocore_session=botocore_session)

    try:
        credentials = session.get_credentials()
    except BotoCoreError as error:
        raise ECSTaskRoleCredentialError("ECS task role credentials are unavailable") from error

    if credentials is None:
        raise ECSTaskRoleCredentialError("ECS task role credentials are unavailable")

    return session


def _validated_container_provider_environ() -> dict[str, str]:
    raw_relative_uri = os.environ.get(ECS_RELATIVE_URI_ENV_VAR)
    if raw_relative_uri is None:
        raise ECSTaskRoleCredentialError(
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI is required"
        )

    relative_uri = raw_relative_uri.strip()
    if relative_uri != raw_relative_uri or not relative_uri:
        raise ECSTaskRoleCredentialError(
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI must be a relative path"
        )

    parsed_uri = urlsplit(relative_uri)
    if (
        parsed_uri.scheme
        or parsed_uri.netloc
        or parsed_uri.query
        or parsed_uri.fragment
        or not parsed_uri.path.startswith("/")
    ):
        raise ECSTaskRoleCredentialError(
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI must be a relative path"
        )

    return {ECS_RELATIVE_URI_ENV_VAR: relative_uri}
