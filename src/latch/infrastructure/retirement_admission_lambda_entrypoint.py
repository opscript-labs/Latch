import logging
import os
import re
from collections.abc import Callable
from typing import Any

import boto3  # type: ignore[import-untyped]

from latch.application.retirement_admission_adapter import RetirementAdmissionAdapter
from latch.infrastructure.claim_scoped_operational_evidence_collection import (
    ClaimScopedOperationalEvidenceCollection,
)
from latch.infrastructure.cloudwatch_cpu_inactivity_collector import (
    CloudWatchCpuInactivityCollector,
)
from latch.infrastructure.cloudwatch_cpu_inactivity_progression import (
    CloudWatchCpuInactivityProgression,
)
from latch.infrastructure.cloudwatch_network_inactivity_collector import (
    CloudWatchNetworkInactivityCollector,
)
from latch.infrastructure.cloudwatch_network_inactivity_progression import (
    CloudWatchNetworkInactivityProgression,
)
from latch.infrastructure.dynamodb_active_claim_validator import DynamoDBActiveClaimValidator
from latch.infrastructure.dynamodb_active_registration_adapter import (
    DynamoDBActiveRegistrationAdapter,
)
from latch.infrastructure.retirement_admission_coordinator import RetirementAdmissionCoordinator
from latch.infrastructure.retirement_admission_lambda import create_lambda_handler

logger = logging.getLogger("latch.retirement_admission_lambda_entrypoint")

REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d$")
TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,255}$")


def _build_handler(
    session: boto3.Session,
    env: dict[str, str],
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    region = env.get("LATCH_DYNAMODB_REGION")
    if not region or not region.strip():
        raise RuntimeError("LATCH_DYNAMODB_REGION is required")
    region = region.strip()
    if REGION_PATTERN.fullmatch(region) is None:
        raise RuntimeError("LATCH_DYNAMODB_REGION must be a valid AWS Region")

    table_name = env.get("LATCH_ACTIVE_REGISTRATION_TABLE")
    if not table_name or not table_name.strip():
        raise RuntimeError("LATCH_ACTIVE_REGISTRATION_TABLE is required")
    table_name = table_name.strip()
    if TABLE_NAME_PATTERN.fullmatch(table_name) is None:
        raise RuntimeError("LATCH_ACTIVE_REGISTRATION_TABLE must be a valid table name")

    dynamodb_client = session.client("dynamodb", region_name=region)
    cloudwatch_client = session.client("cloudwatch", region_name=region)

    active_claim_validator = DynamoDBActiveClaimValidator(dynamodb_client, table_name)
    active_registration_adapter = DynamoDBActiveRegistrationAdapter(dynamodb_client, table_name)

    cpu_collector = CloudWatchCpuInactivityCollector(cloudwatch_client)
    cpu_progression = CloudWatchCpuInactivityProgression(cpu_collector)

    network_collector = CloudWatchNetworkInactivityCollector(cloudwatch_client)
    network_progression = CloudWatchNetworkInactivityProgression(network_collector)

    evidence_collection = ClaimScopedOperationalEvidenceCollection(
        cpu_progression=cpu_progression,
        network_progression=network_progression,
    )

    coordinator = RetirementAdmissionCoordinator(
        active_claim_validator=active_claim_validator,
        evidence_collection=evidence_collection,
        active_registration_adapter=active_registration_adapter,
    )

    adapter = RetirementAdmissionAdapter(coordinator)
    return create_lambda_handler(
        adapter,
        default_producer_authority="RetirementAdmissionRequestProducer",
    )


_cached_handler: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None


def handle_event(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    global _cached_handler
    try:
        if _cached_handler is None:
            session = boto3.Session()
            _cached_handler = _build_handler(session, dict(os.environ))
        return _cached_handler(event, context)
    except Exception as error:
        logger.error(f"Failed to initialize or evaluate handler: {error}", exc_info=True)
        return {"error": "Internal error"}
