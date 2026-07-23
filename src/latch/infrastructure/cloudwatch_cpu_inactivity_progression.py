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
from latch.infrastructure.cloudwatch_cpu_inactivity_collector import (
    CloudWatchCpuInactivityCollector,
)


class CloudWatchCpuInactivityProgression:
    def __init__(self, collector: CloudWatchCpuInactivityCollector | None = None) -> None:
        self._collector = collector or CloudWatchCpuInactivityCollector()

    def progress(
        self,
        claim: RetirementEvaluationClaim,
        target_arn: str,
    ) -> OperationalDimensionAssociation | None:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if target_arn not in claim.environment.resource_target_arns:
            raise ValueError("target_arn must be registered in the claim Environment")

        association = self._collector.collect(claim, target_arn)
        if association is None:
            return None

        context = AdmissionEvaluationContext(
            environment=claim.environment,
            requested_retirement=AdmissionRequest.RETIREMENT,
            evaluated_at=claim.claim_time,
        )
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
            dimension=OperationalDimension.CPU_ACTIVITY,
        )
