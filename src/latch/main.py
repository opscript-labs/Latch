import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from latch import __version__
from latch.domain.environment import Environment
from latch.infrastructure.dynamodb_active_registration_adapter import (
    DynamoDBActiveRegistrationAdapter,
)
from latch.infrastructure.ecs_task_role_credentials import (
    ECSTaskRoleCredentialError,
    create_ecs_task_role_session,
)

REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d$")
TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,255}$")


class HealthResponse(BaseModel):
    service: Literal["Latch"]
    version: str
    status: Literal["healthy"]


class EnvironmentRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str
    owner: str
    created_at: datetime
    ttl_expires_at: datetime
    resource_target_arns: list[str]


class EnvironmentRegistrationResponse(BaseModel):
    identifier: str
    owner: str
    created_at: str
    ttl_expires_at: str
    resource_target_arns: list[str]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.active_registration_adapter = _compose_active_registration_adapter()
    yield


app = FastAPI(title="Latch", version=__version__, lifespan=lifespan)


@app.get("/", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="Latch", version=__version__, status="healthy")


@app.post(
    "/environments",
    response_model=EnvironmentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_environment(
    request: Request,
    registration_request: EnvironmentRegistrationRequest,
) -> EnvironmentRegistrationResponse:
    try:
        environment = Environment(
            identifier=registration_request.identifier,
            created_at=registration_request.created_at,
            ttl_expires_at=registration_request.ttl_expires_at,
            owner=registration_request.owner,
            resource_target_arns=registration_request.resource_target_arns,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="invalid environment registration",
        ) from error

    adapter = request.app.state.active_registration_adapter
    try:
        adapter.register(environment)
    except ClientError as error:
        if _is_conditional_registration_conflict(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="environment already registered",
            ) from error

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="environment registration unavailable",
        ) from error
    except BotoCoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="environment registration unavailable",
        ) from error

    return _environment_response(environment)


def _compose_active_registration_adapter() -> DynamoDBActiveRegistrationAdapter:
    region = _required_env("LATCH_DYNAMODB_REGION")
    table_name = _required_env("LATCH_ACTIVE_REGISTRATION_TABLE")

    if REGION_PATTERN.fullmatch(region) is None:
        raise RuntimeError("LATCH_DYNAMODB_REGION must be a valid AWS Region")

    if TABLE_NAME_PATTERN.fullmatch(table_name) is None:
        raise RuntimeError("LATCH_ACTIVE_REGISTRATION_TABLE must be a valid table name")

    try:
        session = create_ecs_task_role_session()
    except ECSTaskRoleCredentialError as error:
        raise RuntimeError("ECS task-role credentials are required") from error

    dynamodb_client = session.client("dynamodb", region_name=region)
    return DynamoDBActiveRegistrationAdapter(dynamodb_client, table_name)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is required")

    return value.strip()


def _is_conditional_registration_conflict(error: ClientError) -> bool:
    error_code = error.response.get("Error", {}).get("Code")
    if error_code == "ConditionalCheckFailedException":
        return True

    if error_code != "TransactionCanceledException":
        return False

    cancellation_reasons = error.response.get("CancellationReasons")
    if not isinstance(cancellation_reasons, list):
        return False

    return any(
        isinstance(reason, dict) and reason.get("Code") == "ConditionalCheckFailed"
        for reason in cancellation_reasons
    )


def _environment_response(environment: Environment) -> EnvironmentRegistrationResponse:
    return EnvironmentRegistrationResponse(
        identifier=environment.identifier,
        owner=environment.owner,
        created_at=_rfc3339_utc(environment.created_at),
        ttl_expires_at=_rfc3339_utc(environment.ttl_expires_at),
        resource_target_arns=sorted(environment.resource_target_arns),
    )


def _rfc3339_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
