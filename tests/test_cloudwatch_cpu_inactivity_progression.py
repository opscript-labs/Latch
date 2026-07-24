from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionOutcome,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalEstablishmentOutcome,
)
from latch.domain.environment import Environment, RetirementEvaluationClaim
from latch.domain.evidence import Evidence, EvidenceInstant, EvidenceInterval, SourceProvenance
from latch.infrastructure.cloudwatch_cpu_inactivity_progression import (
    CloudWatchCpuInactivityProgression,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
CLAIM_TIME = datetime(2026, 7, 23, 10, 2, 17, tzinfo=UTC)
TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
OTHER_TARGET = "arn:aws:ec2:us-east-1:123456789012:instance/i-0fedcba9876543210"


def make_environment() -> Environment:
    return Environment(
        identifier="env-123",
        created_at=CREATED_AT,
        ttl_expires_at=TTL_EXPIRES_AT,
        owner="team-platform",
        resource_target_arns=[TARGET],
    )


def make_claim() -> RetirementEvaluationClaim:
    return RetirementEvaluationClaim(make_environment(), CLAIM_TIME)


def make_association(
    *,
    referent: str = TARGET,
    classification: EvidencePropositionClassification = (
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY
    ),
    source_system: str = "aws.cloudwatch.metrics",
    temporal_context: EvidenceInstant | EvidenceInterval | None = None,
) -> EvidencePropositionClassificationAssociation:
    if temporal_context is None:
        temporal_context = EvidenceInterval(
            CLAIM_TIME - timedelta(minutes=30),
            CLAIM_TIME,
        )

    return EvidencePropositionClassificationAssociation(
        evidence=Evidence(
            proposition="cpu inactivity observed",
            referent=referent,
            source_provenance=SourceProvenance(
                source_system=source_system,
                source_occurrence="cloudwatch cpu occurrence",
            ),
            temporal_context=temporal_context,
        ),
        classification=classification,
    )


def progression_with_collector(
    collector: Mock,
) -> CloudWatchCpuInactivityProgression:
    return CloudWatchCpuInactivityProgression(collector=collector)


def test_affirmative_cpu_collection_progresses_to_cpu_dimension_association() -> None:
    collector = Mock()
    collector.collect.return_value = make_association()

    association = progression_with_collector(collector).progress(make_claim(), TARGET)

    assert isinstance(association, OperationalDimensionAssociation)
    assert association.dimension is OperationalDimension.CPU_ACTIVITY
    assert (
        association.establishment.outcome
        is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY
    )
    assert (
        association.establishment.projection.outcome
        is OperationalAssertionOutcome.ASSERTS_OPERATIONAL_INACTIVITY
    )


def test_derived_context_uses_claim_time_as_evaluated_at() -> None:
    collector = Mock()
    collector.collect.return_value = make_association()
    claim = make_claim()

    association = progression_with_collector(collector).progress(claim, TARGET)

    assert association is not None
    assert association.establishment.projection.context.environment == claim.environment
    assert association.establishment.projection.context.evaluated_at == claim.claim_time


def test_supplied_matching_context_is_used() -> None:
    collector = Mock()
    collector.collect.return_value = make_association()
    claim = make_claim()
    context = AdmissionEvaluationContext(
        claim.environment,
        AdmissionRequest.RETIREMENT,
        claim.claim_time,
    )

    association = progression_with_collector(collector).progress(claim, TARGET, context)

    assert association is not None
    assert association.establishment.projection.context is context


def test_supplied_context_must_match_claim_environment_and_time() -> None:
    collector = Mock()
    collector.collect.return_value = make_association()
    claim = make_claim()
    mismatched_context = AdmissionEvaluationContext(
        claim.environment,
        AdmissionRequest.RETIREMENT,
        claim.claim_time + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="evaluated_at"):
        progression_with_collector(collector).progress(claim, TARGET, mismatched_context)

    collector.collect.assert_not_called()


def test_non_affirmative_collection_produces_no_dimension_association() -> None:
    collector = Mock()
    collector.collect.return_value = None

    assert progression_with_collector(collector).progress(make_claim(), TARGET) is None


def test_collector_failure_propagates_unchanged() -> None:
    collector = Mock()
    error = RuntimeError("cloudwatch request failed")
    collector.collect.side_effect = error

    with pytest.raises(RuntimeError) as raised:
        progression_with_collector(collector).progress(make_claim(), TARGET)

    assert raised.value is error


def test_non_member_target_is_rejected_before_collection() -> None:
    collector = Mock()

    with pytest.raises(ValueError, match="registered"):
        progression_with_collector(collector).progress(make_claim(), OTHER_TARGET)

    collector.collect.assert_not_called()


@pytest.mark.parametrize(
    "collected_association",
    [
        make_association(referent=OTHER_TARGET),
        make_association(temporal_context=EvidenceInstant(CLAIM_TIME + timedelta(microseconds=1))),
        make_association(source_system="aws.unapproved.metrics"),
        make_association(
            classification=EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
            source_system="aws.cloudwatch.metrics",
        ),
        make_association(classification=EvidencePropositionClassification.UNCLASSIFIED),
    ],
)
def test_no_direct_dimension_association_when_approved_chain_does_not_permit_it(
    collected_association: EvidencePropositionClassificationAssociation,
) -> None:
    collector = Mock()
    collector.collect.return_value = collected_association

    assert progression_with_collector(collector).progress(make_claim(), TARGET) is None


def test_composition_does_not_mutate_upstream_artifacts() -> None:
    collector = Mock()
    collected_association = make_association()
    collector.collect.return_value = collected_association
    claim = make_claim()
    environment = claim.environment
    targets = environment.resource_target_arns
    evidence = collected_association.evidence
    classification = collected_association.classification

    association = progression_with_collector(collector).progress(claim, TARGET)

    assert association is not None
    assert claim.environment == environment
    assert environment.resource_target_arns == targets
    assert collected_association.evidence == evidence
    assert collected_association.classification is classification
    assert association.establishment.projection.association == collected_association
