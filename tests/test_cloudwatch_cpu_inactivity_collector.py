import math
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from botocore.exceptions import EndpointConnectionError

from latch.domain.admission import (
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalDimensionAssociation,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import EvidenceInterval
from latch.infrastructure.cloudwatch_cpu_inactivity_collector import (
    CloudWatchCpuInactivityCollector,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
CLAIM_TIME = datetime(2026, 7, 23, 10, 2, 17, tzinfo=UTC)
OBSERVATION_START = datetime(2026, 7, 23, 9, 30, tzinfo=UTC)
OBSERVATION_END = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
OTHER_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


def make_claim() -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(
        Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns=[TARGET],
        ),
        CLAIM_TIME,
    )


def expected_timestamps() -> list[datetime]:
    return [OBSERVATION_START + timedelta(minutes=5 * index) for index in range(6)]


def metric_response(
    *,
    timestamps: list[object] | None = None,
    values: list[object] | None = None,
    status: str = "Complete",
    extra_results: bool = False,
    next_token: bool = False,
) -> dict[str, object]:
    result = {
        "Id": "cpu_utilization_average",
        "StatusCode": status,
        "Timestamps": expected_timestamps() if timestamps is None else timestamps,
        "Values": [0.2, 0.0, 0.8, 0.7, 0.4, 0.3] if values is None else values,
    }
    response: dict[str, object] = {"MetricDataResults": [result]}
    if extra_results:
        response["MetricDataResults"] = [result, result]
    if next_token:
        response["NextToken"] = "token"
    return response


def collect_with_response(response: dict[str, object]) -> tuple[
    EvidencePropositionClassificationAssociation | None,
    Mock,
    Mock,
]:
    cloudwatch_client = Mock()
    cloudwatch_client.get_metric_data.return_value = response
    result = CloudWatchCpuInactivityCollector(cloudwatch_client).collect(make_claim(), TARGET)
    return result, Mock(), cloudwatch_client


def test_non_aligned_claim_time_queries_latest_complete_six_period_window() -> None:
    _, _, cloudwatch_client = collect_with_response(metric_response())

    request = cloudwatch_client.get_metric_data.call_args.kwargs
    assert request["StartTime"] == OBSERVATION_START
    assert request["EndTime"] == OBSERVATION_END


def test_cloudwatch_request_scope() -> None:
    _, _, cloudwatch_client = collect_with_response(metric_response())

    cloudwatch_client.get_metric_data.assert_called_once()
    request = cloudwatch_client.get_metric_data.call_args.kwargs
    assert request["MetricDataQueries"] == [
        {
            "Id": "cpu_utilization_average",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": "CPUUtilization",
                    "Dimensions": [
                        {
                            "Name": "InstanceId",
                            "Value": "i-0123456789abcdef0",
                        }
                    ],
                },
                "Period": 300,
                "Stat": "Average",
            },
            "ReturnData": True,
        }
    ]


def test_affirmative_output_has_exact_evidence_and_inactivity_classification() -> None:
    result, _, _ = collect_with_response(metric_response())

    assert result is not None
    assert result.classification is EvidencePropositionClassification.OPERATIONAL_INACTIVITY
    assert result.evidence.referent == TARGET
    assert result.evidence.source_provenance.source_system == "aws.cloudwatch.metrics"
    assert result.evidence.source_provenance.source_occurrence == (
        "AWS/EC2:CPUUtilization:Average:300:"
        "InstanceId=i-0123456789abcdef0:"
        "2026-07-23T09:30:00.000000Z/2026-07-23T10:00:00.000000Z"
    )
    assert result.evidence.temporal_context == EvidenceInterval(
        OBSERVATION_START,
        OBSERVATION_END,
    )
    assert (
        result.evidence.proposition
        == f"EC2 instance {TARGET} AWS/EC2 CPUUtilization Average was below "
        "1.0 percent in every complete 300-second period of "
        "2026-07-23T09:30:00.000000Z/2026-07-23T10:00:00.000000Z"
    )


def test_unregistered_target_is_rejected_before_client_call() -> None:
    cloudwatch_client = Mock()
    with pytest.raises(ValueError, match="registered"):
        CloudWatchCpuInactivityCollector(cloudwatch_client).collect(make_claim(), OTHER_TARGET)
    cloudwatch_client.get_metric_data.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [
        {"MetricDataResults": []},
        metric_response(timestamps=expected_timestamps()[:5], values=[0.2] * 5),
        metric_response(
            timestamps=[*expected_timestamps()[:5], expected_timestamps()[0]],
        ),
        metric_response(
            timestamps=[*expected_timestamps(), OBSERVATION_END],
            values=[0.2] * 7,
        ),
        metric_response(
            timestamps=[*expected_timestamps()[:5], OBSERVATION_START - timedelta(minutes=5)],
        ),
        metric_response(timestamps=["not-a-timestamp", *expected_timestamps()[:5]]),
        metric_response(timestamps=[datetime(2026, 7, 23, 9, 30), *expected_timestamps()[1:]]),
        metric_response(values=[0.2, 0.3, "x", 0.4, 0.5, 0.6]),
        metric_response(values=[0.2, math.inf, 0.3, 0.4, 0.5, 0.6]),
        {"MetricDataResults": [{"StatusCode": "Complete"}]},
        metric_response(status="PartialData"),
        metric_response(next_token=True),
        metric_response(values=[0.2, 0.3, 1.0, 0.4, 0.5, 0.6]),
    ],
)
def test_non_affirmative_responses_return_no_artifacts(response: dict[str, object]) -> None:
    result, _, _ = collect_with_response(response)

    assert result is None


def test_request_level_sdk_failure_propagates_and_produces_no_artifacts() -> None:
    cloudwatch_client = Mock()
    error = EndpointConnectionError(endpoint_url="https://cloudwatch.us-east-1.amazonaws.com")
    cloudwatch_client.get_metric_data.side_effect = error

    with pytest.raises(EndpointConnectionError) as raised:
        CloudWatchCpuInactivityCollector(cloudwatch_client).collect(make_claim(), TARGET)

    assert raised.value is error


def test_no_downstream_admission_artifact_is_created() -> None:
    result, _, _ = collect_with_response(metric_response())

    assert isinstance(result, EvidencePropositionClassificationAssociation)
    assert not isinstance(result, OperationalDimensionAssociation)
