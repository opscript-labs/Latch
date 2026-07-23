import math
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import EndpointConnectionError

from latch.domain.admission import (
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalEstablishmentOutcome,
    OperationalRetirementReadiness,
    RetirementAdmissionVerdict,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import Evidence, EvidenceInstant, EvidenceInterval, SourceProvenance
from latch.infrastructure.cloudwatch_network_inactivity_collector import (
    NETWORK_IN_QUERY_ID,
    NETWORK_OUT_QUERY_ID,
    CloudWatchNetworkInactivityCollector,
)
from latch.infrastructure.cloudwatch_network_inactivity_progression import (
    CloudWatchNetworkInactivityProgression,
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


def metric_result(
    result_id: str,
    *,
    timestamps: list[object] | None = None,
    values: list[object] | None = None,
    status: str = "Complete",
) -> dict[str, object]:
    return {
        "Id": result_id,
        "StatusCode": status,
        "Timestamps": expected_timestamps() if timestamps is None else timestamps,
        "Values": [0.0, 100.0, 512.0, 64.0, 1.0, 1023.0] if values is None else values,
    }


def metric_response(
    *results: dict[str, object],
    next_token: bool = False,
) -> dict[str, object]:
    response: dict[str, object] = {
        "MetricDataResults": list(results)
        or [metric_result(NETWORK_IN_QUERY_ID), metric_result(NETWORK_OUT_QUERY_ID)]
    }
    if next_token:
        response["NextToken"] = "token"
    return response


def collect_with_response(
    response: dict[str, object],
) -> tuple[
    EvidencePropositionClassificationAssociation | None,
    Mock,
    Mock,
]:
    cloudwatch_client = Mock()
    cloudwatch_client.get_metric_data.return_value = response
    session = Mock()
    session.client.return_value = cloudwatch_client

    with patch(
        "latch.infrastructure.cloudwatch_network_inactivity_collector.create_ecs_task_role_session",
        return_value=session,
    ):
        result = CloudWatchNetworkInactivityCollector().collect(make_claim(), TARGET)

    return result, session, cloudwatch_client


def make_collected_association(
    *,
    referent: str = TARGET,
    classification: EvidencePropositionClassification = (
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY
    ),
    source_system: str = "aws.cloudwatch.metrics",
    temporal_context: EvidenceInstant | EvidenceInterval | None = None,
) -> EvidencePropositionClassificationAssociation:
    if temporal_context is None:
        temporal_context = EvidenceInterval(CLAIM_TIME - timedelta(minutes=30), CLAIM_TIME)

    return EvidencePropositionClassificationAssociation(
        evidence=Evidence(
            proposition="network inactivity observed",
            referent=referent,
            source_provenance=SourceProvenance(
                source_system=source_system,
                source_occurrence="cloudwatch network occurrence",
            ),
            temporal_context=temporal_context,
        ),
        classification=classification,
    )


def test_non_aligned_claim_time_queries_latest_complete_six_period_window() -> None:
    _, _, cloudwatch_client = collect_with_response(metric_response())

    request = cloudwatch_client.get_metric_data.call_args.kwargs
    assert request["StartTime"] == OBSERVATION_START
    assert request["EndTime"] == OBSERVATION_END


def test_cloudwatch_request_scope_and_regional_client_selection() -> None:
    _, session, cloudwatch_client = collect_with_response(metric_response())

    session.client.assert_called_once_with("cloudwatch", region_name="us-east-1")
    request = cloudwatch_client.get_metric_data.call_args.kwargs
    assert request["MetricDataQueries"] == [
        {
            "Id": NETWORK_IN_QUERY_ID,
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": "NetworkIn",
                    "Dimensions": [{"Name": "InstanceId", "Value": "i-0123456789abcdef0"}],
                },
                "Period": 300,
                "Stat": "Sum",
            },
            "ReturnData": True,
        },
        {
            "Id": NETWORK_OUT_QUERY_ID,
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": "NetworkOut",
                    "Dimensions": [{"Name": "InstanceId", "Value": "i-0123456789abcdef0"}],
                },
                "Period": 300,
                "Stat": "Sum",
            },
            "ReturnData": True,
        },
    ]


def test_result_order_does_not_matter() -> None:
    result, _, _ = collect_with_response(
        metric_response(
            metric_result(NETWORK_OUT_QUERY_ID),
            metric_result(NETWORK_IN_QUERY_ID),
        )
    )

    assert result is not None


def test_valid_dual_metric_data_produces_exact_evidence_and_classification() -> None:
    result, _, _ = collect_with_response(metric_response())

    assert result is not None
    assert result.classification is EvidencePropositionClassification.OPERATIONAL_INACTIVITY
    assert result.evidence.referent == TARGET
    assert result.evidence.source_provenance.source_system == "aws.cloudwatch.metrics"
    assert result.evidence.source_provenance.source_occurrence == (
        "AWS/EC2:NetworkIn+NetworkOut:Sum:300:"
        "InstanceId=i-0123456789abcdef0:"
        "2026-07-23T09:30:00.000000Z/2026-07-23T10:00:00.000000Z"
    )
    assert result.evidence.temporal_context == EvidenceInterval(
        OBSERVATION_START,
        OBSERVATION_END,
    )
    assert (
        result.evidence.proposition
        == f"EC2 instance {TARGET} CloudWatch NetworkIn and NetworkOut Sum were "
        "each below 1024 bytes in every complete 300-second period of "
        "2026-07-23T09:30:00.000000Z/2026-07-23T10:00:00.000000Z"
    )


def test_valid_collection_progresses_to_network_activity_association() -> None:
    collector = Mock()
    collector.collect.return_value = make_collected_association()

    association = CloudWatchNetworkInactivityProgression(collector).progress(
        make_claim(),
        TARGET,
    )

    assert isinstance(association, OperationalDimensionAssociation)
    assert association.dimension is OperationalDimension.NETWORK_ACTIVITY
    assert (
        association.establishment.outcome
        is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY
    )
    assert not isinstance(association, OperationalRetirementReadiness)
    assert not isinstance(association, RetirementAdmissionVerdict)


@pytest.mark.parametrize(
    "response",
    [
        metric_response(metric_result(NETWORK_IN_QUERY_ID)),
        metric_response(metric_result(NETWORK_IN_QUERY_ID), metric_result(NETWORK_IN_QUERY_ID)),
        metric_response(metric_result(NETWORK_IN_QUERY_ID), metric_result("substituted")),
        metric_response(
            metric_result(NETWORK_IN_QUERY_ID),
            metric_result(NETWORK_OUT_QUERY_ID),
            metric_result("unexpected"),
        ),
        metric_response(
            metric_result(NETWORK_IN_QUERY_ID, status="PartialData"),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(next_token=True),
        metric_response(
            metric_result(
                NETWORK_IN_QUERY_ID,
                timestamps=expected_timestamps()[:5],
                values=[0] * 5,
            ),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            metric_result(
                NETWORK_IN_QUERY_ID,
                timestamps=[*expected_timestamps()[:5], expected_timestamps()[0]],
            ),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            metric_result(
                NETWORK_IN_QUERY_ID,
                timestamps=[*expected_timestamps(), OBSERVATION_END],
                values=[0] * 7,
            ),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            metric_result(
                NETWORK_IN_QUERY_ID,
                timestamps=[
                    *expected_timestamps()[:5],
                    OBSERVATION_START - timedelta(minutes=5),
                ],
            ),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            metric_result(NETWORK_IN_QUERY_ID, timestamps=["bad", *expected_timestamps()[:5]]),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            metric_result(NETWORK_IN_QUERY_ID, values=[0, 1, "bad", 2, 3, 4]),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            metric_result(NETWORK_IN_QUERY_ID, values=[0, 1, math.inf, 2, 3, 4]),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            {"Id": NETWORK_IN_QUERY_ID, "StatusCode": "Complete"},
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
        metric_response(
            metric_result(NETWORK_IN_QUERY_ID, values=[0, 1, 1024, 2, 3, 4]),
            metric_result(NETWORK_OUT_QUERY_ID),
        ),
    ],
)
def test_non_affirmative_responses_return_no_artifacts(response: dict[str, object]) -> None:
    result, _, _ = collect_with_response(response)

    assert result is None


def test_non_affirmative_progression_returns_no_dimension_association() -> None:
    collector = Mock()
    collector.collect.return_value = None

    assert CloudWatchNetworkInactivityProgression(collector).progress(make_claim(), TARGET) is None


def test_non_member_target_is_rejected_before_client_or_collection() -> None:
    with (
        patch(
            "latch.infrastructure.cloudwatch_network_inactivity_collector."
            "create_ecs_task_role_session"
        ) as factory,
        pytest.raises(ValueError, match="registered"),
    ):
        CloudWatchNetworkInactivityCollector().collect(make_claim(), OTHER_TARGET)

    factory.assert_not_called()

    collector = Mock()
    with pytest.raises(ValueError, match="registered"):
        CloudWatchNetworkInactivityProgression(collector).progress(make_claim(), OTHER_TARGET)
    collector.collect.assert_not_called()


def test_request_level_sdk_failure_propagates() -> None:
    cloudwatch_client = Mock()
    error = EndpointConnectionError(endpoint_url="https://cloudwatch.us-east-1.amazonaws.com")
    cloudwatch_client.get_metric_data.side_effect = error
    session = Mock()
    session.client.return_value = cloudwatch_client

    with (
        patch(
            "latch.infrastructure.cloudwatch_network_inactivity_collector."
            "create_ecs_task_role_session",
            return_value=session,
        ),
        pytest.raises(EndpointConnectionError) as raised,
    ):
        CloudWatchNetworkInactivityCollector().collect(make_claim(), TARGET)

    assert raised.value is error


@pytest.mark.parametrize(
    "collected_association",
    [
        make_collected_association(referent=OTHER_TARGET),
        make_collected_association(
            temporal_context=EvidenceInstant(CLAIM_TIME + timedelta(microseconds=1))
        ),
        make_collected_association(source_system="aws.unapproved.metrics"),
        make_collected_association(
            classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            source_system="aws.cloudwatch.metrics",
        ),
        make_collected_association(classification=EvidencePropositionClassification.UNCLASSIFIED),
    ],
)
def test_no_direct_network_association_when_chain_does_not_permit_it(
    collected_association: EvidencePropositionClassificationAssociation,
) -> None:
    collector = Mock()
    collector.collect.return_value = collected_association

    assert CloudWatchNetworkInactivityProgression(collector).progress(make_claim(), TARGET) is None
