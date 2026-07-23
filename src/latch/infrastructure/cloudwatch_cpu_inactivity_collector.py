import math
from datetime import UTC, datetime, timedelta
from typing import Any

from latch.domain.admission import (
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
)
from latch.domain.environment import RetirementEvaluationClaim
from latch.domain.environment.environment import EC2_INSTANCE_ARN_PATTERN
from latch.domain.evidence import Evidence, EvidenceInterval, SourceProvenance
from latch.infrastructure.dynamodb_active_registration_adapter import (
    canonical_registration_timestamp,
)
from latch.infrastructure.ecs_task_role_credentials import create_ecs_task_role_session

CPU_INACTIVITY_THRESHOLD_PERCENT = 1.0
OBSERVATION_PERIOD_SECONDS = 300
OBSERVATION_PERIOD_COUNT = 6


class CloudWatchCpuInactivityCollector:
    def collect(
        self,
        claim: RetirementEvaluationClaim,
        target_arn: str,
    ) -> EvidencePropositionClassificationAssociation | None:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if target_arn not in claim.environment.resource_target_arns:
            raise ValueError("target_arn must be registered in the claim Environment")

        match = EC2_INSTANCE_ARN_PATTERN.fullmatch(target_arn)
        if match is None:
            raise ValueError("target_arn must be a valid EC2 instance ARN")

        instance_id = match.group("instance_id")
        region = match.group("region")
        observation_end = _latest_five_minute_boundary(claim.claim_time)
        observation_start = observation_end - timedelta(
            seconds=OBSERVATION_PERIOD_SECONDS * OBSERVATION_PERIOD_COUNT
        )

        session = create_ecs_task_role_session()
        cloudwatch_client = session.client("cloudwatch", region_name=region)
        response = cloudwatch_client.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "cpu_utilization_average",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EC2",
                            "MetricName": "CPUUtilization",
                            "Dimensions": [
                                {
                                    "Name": "InstanceId",
                                    "Value": instance_id,
                                }
                            ],
                        },
                        "Period": OBSERVATION_PERIOD_SECONDS,
                        "Stat": "Average",
                    },
                    "ReturnData": True,
                }
            ],
            StartTime=observation_start,
            EndTime=observation_end,
        )

        if not _is_affirmative_response(response, observation_start):
            return None

        return EvidencePropositionClassificationAssociation(
            evidence=Evidence(
                proposition=(
                    f"EC2 instance {target_arn} AWS/EC2 CPUUtilization Average was "
                    "below 1.0 percent in every complete 300-second period of "
                    f"{canonical_registration_timestamp(observation_start)}/"
                    f"{canonical_registration_timestamp(observation_end)}"
                ),
                referent=target_arn,
                source_provenance=SourceProvenance(
                    source_system="aws.cloudwatch.metrics",
                    source_occurrence=(
                        "AWS/EC2:CPUUtilization:Average:300:"
                        f"InstanceId={instance_id}:"
                        f"{canonical_registration_timestamp(observation_start)}/"
                        f"{canonical_registration_timestamp(observation_end)}"
                    ),
                ),
                temporal_context=EvidenceInterval(observation_start, observation_end),
            ),
            classification=EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        )


def _latest_five_minute_boundary(value: datetime) -> datetime:
    claim_time = value.astimezone(UTC)
    seconds_since_hour = claim_time.minute * 60 + claim_time.second
    seconds_to_remove = seconds_since_hour % OBSERVATION_PERIOD_SECONDS
    return (
        claim_time
        - timedelta(
            seconds=seconds_to_remove,
            microseconds=claim_time.microsecond,
        )
    ).replace(tzinfo=UTC)


def _is_affirmative_response(
    response: dict[str, Any],
    observation_start: datetime,
) -> bool:
    if "NextToken" in response:
        return False

    metric_results = response.get("MetricDataResults")
    if not isinstance(metric_results, list) or len(metric_results) != 1:
        return False

    result = metric_results[0]
    if not isinstance(result, dict) or result.get("StatusCode") != "Complete":
        return False

    timestamps = result.get("Timestamps")
    values = result.get("Values")
    if not isinstance(timestamps, list) or not isinstance(values, list):
        return False

    if len(timestamps) != OBSERVATION_PERIOD_COUNT or len(values) != OBSERVATION_PERIOD_COUNT:
        return False

    required_timestamps = {
        observation_start + timedelta(seconds=OBSERVATION_PERIOD_SECONDS * index)
        for index in range(OBSERVATION_PERIOD_COUNT)
    }
    observed_timestamps: set[datetime] = set()
    for timestamp in timestamps:
        if not isinstance(timestamp, datetime):
            return False

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return False

        observed_timestamp = timestamp.astimezone(UTC)
        if observed_timestamp in observed_timestamps:
            return False

        observed_timestamps.add(observed_timestamp)

    if observed_timestamps != required_timestamps:
        return False

    return all(_is_qualifying_cpu_value(value) for value in values)


def _is_qualifying_cpu_value(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False

    return math.isfinite(value) and value < CPU_INACTIVITY_THRESHOLD_PERCENT
