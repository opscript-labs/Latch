from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    EvidencePropositionClassification,
    EvidencePropositionClassificationAssociation,
    OperationalAssertionEstablishment,
    OperationalAssertionProjection,
    OperationalConflictRecognitionCoverage,
    OperationalConflictStatus,
    OperationalConflictStatusOutcome,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalDimensionAssociationSet,
)
from latch.domain.environment import Environment
from latch.domain.evidence import (
    Evidence,
    EvidenceInstant,
    EvidenceTemporalContext,
    EvidenceTimeless,
    SourceProvenance,
)

CREATED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
TTL_EXPIRES_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
CONTEXT_EVALUATED_AT = datetime(2026, 7, 23, 11, 0, tzinfo=UTC)


def make_context() -> AdmissionEvaluationContext:
    return AdmissionEvaluationContext(
        environment=Environment(
            identifier="env-123",
            created_at=CREATED_AT,
            ttl_expires_at=TTL_EXPIRES_AT,
            owner="team-platform",
            resource_target_arns={
                "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
            },
        ),
        requested_retirement=AdmissionRequest.RETIREMENT,
        evaluated_at=CONTEXT_EVALUATED_AT,
    )


def make_association(
    classification: EvidencePropositionClassification,
    proposition: str,
    context: AdmissionEvaluationContext,
    temporal_context: EvidenceTemporalContext | None = None,
) -> OperationalDimensionAssociation:
    if temporal_context is None:
        temporal_context = EvidenceInstant(EVALUATED_AT)

    source_system = (
        "aws.cloudtrail.event"
        if classification is EvidencePropositionClassification.OPERATIONAL_ACTIVITY
        else "aws.cloudwatch.metrics"
    )
    evidence = Evidence(
        proposition=proposition,
        referent=context.environment.identifier,
        source_provenance=SourceProvenance(
            source_system=source_system,
            source_occurrence=f"{source_system}:{proposition}",
        ),
        temporal_context=temporal_context,
    )
    establishment = OperationalAssertionEstablishment(
        projection=OperationalAssertionProjection(
            association=EvidencePropositionClassificationAssociation(
                evidence=evidence,
                classification=classification,
            ),
            context=context,
        )
    )
    return OperationalDimensionAssociation(
        establishment=establishment,
        dimension=OperationalDimension.CPU_ACTIVITY,
    )


def make_coverage(
    associations: list[OperationalDimensionAssociation],
    context: AdmissionEvaluationContext,
) -> OperationalConflictRecognitionCoverage:
    return OperationalConflictRecognitionCoverage(
        association_set=OperationalDimensionAssociationSet(context, associations)
    )


def test_operational_conflict_status_has_exact_closed_vocabulary() -> None:
    assert list(OperationalConflictStatusOutcome) == [
        OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_PRESENT,
        OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED,
        OperationalConflictStatusOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED,
    ]


def test_recognized_conflict_maps_to_operational_conflict_present() -> None:
    context = make_context()
    coverage = make_coverage(
        [
            make_association(
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
                "activity was observed",
                context,
            ),
            make_association(
                EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
                "inactivity was observed",
                context,
            ),
        ],
        context,
    )

    status = OperationalConflictStatus(coverage=coverage)

    assert status.outcome is OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_PRESENT


def test_unresolved_only_coverage_maps_to_unresolved_status() -> None:
    context = make_context()
    coverage = make_coverage(
        [
            make_association(
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
                "activity was observed",
                context,
                temporal_context=EvidenceTimeless(),
            ),
            make_association(
                EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
                "inactivity was observed",
                context,
            ),
        ],
        context,
    )

    status = OperationalConflictStatus(coverage=coverage)

    assert status.outcome is OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_STATUS_UNRESOLVED


def test_no_recognized_no_unresolved_coverage_maps_to_no_conflict_recognized() -> None:
    context = make_context()
    coverage = make_coverage(
        [
            make_association(
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
                "first activity was observed",
                context,
            ),
            make_association(
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
                "second activity was observed",
                context,
            ),
        ],
        context,
    )

    status = OperationalConflictStatus(coverage=coverage)

    assert status.outcome is OperationalConflictStatusOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED


def test_empty_coverage_maps_to_no_conflict_recognized() -> None:
    status = OperationalConflictStatus(
        coverage=OperationalConflictRecognitionCoverage(
            OperationalDimensionAssociationSet(context=make_context())
        )
    )

    assert status.outcome is OperationalConflictStatusOutcome.NO_OPERATIONAL_CONFLICT_RECOGNIZED


def test_recognized_conflict_takes_precedence_over_unresolved_results() -> None:
    context = make_context()
    coverage = make_coverage(
        [
            make_association(
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
                "activity was observed",
                context,
            ),
            make_association(
                EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
                "inactivity was observed",
                context,
            ),
            make_association(
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
                "timeless activity was observed",
                context,
                temporal_context=EvidenceTimeless(),
            ),
        ],
        context,
    )

    status = OperationalConflictStatus(coverage=coverage)

    assert status.outcome is OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_PRESENT


def test_identity_and_hashing_depend_only_on_coverage() -> None:
    context = make_context()
    coverage = make_coverage(
        [
            make_association(
                EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
                "activity was observed",
                context,
            ),
            make_association(
                EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
                "inactivity was observed",
                context,
            ),
        ],
        context,
    )

    status = OperationalConflictStatus(coverage=coverage)
    same_status = OperationalConflictStatus(coverage=coverage)

    assert status == same_status
    assert hash(status) == hash(same_status)


def test_equivalent_coverage_produces_equal_status() -> None:
    context = make_context()
    first = make_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        "activity was observed",
        context,
    )
    second = make_association(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        "inactivity was observed",
        context,
    )

    assert OperationalConflictStatus(make_coverage([first, second], context)) == (
        OperationalConflictStatus(make_coverage([second, first], context))
    )


def test_changed_coverage_produces_distinct_status() -> None:
    context = make_context()
    first = make_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        "activity was observed",
        context,
    )
    second = make_association(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        "inactivity was observed",
        context,
    )

    assert OperationalConflictStatus(make_coverage([first], context)) != (
        OperationalConflictStatus(make_coverage([first, second], context))
    )


def test_status_outcome_cannot_be_caller_supplied() -> None:
    coverage = OperationalConflictRecognitionCoverage(
        OperationalDimensionAssociationSet(context=make_context())
    )

    with pytest.raises(TypeError):
        OperationalConflictStatus(
            coverage=coverage,
            outcome=OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_PRESENT,
        )


def test_operational_conflict_status_is_immutable() -> None:
    status = OperationalConflictStatus(
        coverage=OperationalConflictRecognitionCoverage(
            OperationalDimensionAssociationSet(context=make_context())
        )
    )

    with pytest.raises(FrozenInstanceError):
        status.outcome = OperationalConflictStatusOutcome.OPERATIONAL_CONFLICT_PRESENT


def test_operational_conflict_status_does_not_mutate_coverage_or_upstream_inputs() -> None:
    context = make_context()
    first = make_association(
        EvidencePropositionClassification.OPERATIONAL_ACTIVITY,
        "activity was observed",
        context,
    )
    second = make_association(
        EvidencePropositionClassification.OPERATIONAL_INACTIVITY,
        "inactivity was observed",
        context,
    )
    coverage = make_coverage([first, second], context)
    recognitions = coverage.recognitions
    association_set = coverage.association_set

    OperationalConflictStatus(coverage=coverage)

    assert coverage == make_coverage([first, second], context)
    assert coverage.recognitions == recognitions
    assert coverage.association_set == association_set
    assert first == next(
        association for association in association_set.associations if association == first
    )
    assert second == next(
        association for association in association_set.associations if association == second
    )
