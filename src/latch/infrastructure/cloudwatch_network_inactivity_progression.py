from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    OperationalAssertionEstablishment,
    OperationalAssertionProjection,
    OperationalDimension,
    OperationalDimensionAssociation,
    OperationalEstablishmentOutcome,
)
from latch.domain.environment import RetirementEvaluationClaim
from latch.infrastructure.cloudwatch_network_inactivity_collector import (
    CloudWatchNetworkInactivityCollector,
)


class CloudWatchNetworkInactivityProgression:
    def __init__(
        self,
        collector: CloudWatchNetworkInactivityCollector,
    ) -> None:
        self._collector = collector

    def progress(
        self,
        claim: RetirementEvaluationClaim,
        target_arn: str,
        context: AdmissionEvaluationContext | None = None,
    ) -> OperationalDimensionAssociation | None:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if target_arn not in claim.environment.resource_target_arns:
            raise ValueError("target_arn must be registered in the claim Environment")

        if context is None:
            context = AdmissionEvaluationContext(
                environment=claim.environment,
                requested_retirement=AdmissionRequest.RETIREMENT,
                evaluated_at=claim.claim_time,
            )
        else:
            _validate_context_for_claim(context, claim)

        association = self._collector.collect(claim, target_arn)
        if association is None:
            return None

        projection = OperationalAssertionProjection(
            association=association,
            context=context,
        )
        establishment = OperationalAssertionEstablishment(projection)
        if (
            establishment.outcome
            is not OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY
        ):
            return None

        return OperationalDimensionAssociation(
            establishment=establishment,
            dimension=OperationalDimension.NETWORK_ACTIVITY,
        )


def _validate_context_for_claim(
    context: AdmissionEvaluationContext,
    claim: RetirementEvaluationClaim,
) -> None:
    if not isinstance(context, AdmissionEvaluationContext):
        raise ValueError("context must be an AdmissionEvaluationContext")

    if context.environment != claim.environment:
        raise ValueError("context Environment must match claim")

    if context.evaluated_at != claim.claim_time:
        raise ValueError("context evaluated_at must match claim_time")
