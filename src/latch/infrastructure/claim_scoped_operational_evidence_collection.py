from latch.domain.admission import (
    AdmissionEvaluationContext,
    AdmissionRequest,
    OperationalDimensionAssociation,
    OperationalDimensionAssociationSet,
    OperationalRetirementReadiness,
    RegisteredTargetOperationalEvidenceCoverage,
)
from latch.domain.environment import RetirementEvaluationClaim
from latch.infrastructure.cloudwatch_cpu_inactivity_progression import (
    CloudWatchCpuInactivityProgression,
)
from latch.infrastructure.cloudwatch_network_inactivity_progression import (
    CloudWatchNetworkInactivityProgression,
)


class ClaimScopedOperationalEvidenceCollection:
    def __init__(
        self,
        cpu_progression: CloudWatchCpuInactivityProgression,
        network_progression: CloudWatchNetworkInactivityProgression,
    ) -> None:
        self._cpu_progression = cpu_progression
        self._network_progression = network_progression

    def collect(
        self,
        claim: RetirementEvaluationClaim,
    ) -> OperationalRetirementReadiness:
        if not isinstance(claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        context = AdmissionEvaluationContext(
            environment=claim.environment,
            requested_retirement=AdmissionRequest.RETIREMENT,
            evaluated_at=claim.claim_time,
        )

        associations: list[OperationalDimensionAssociation] = []
        for target_arn in sorted(claim.environment.resource_target_arns):
            cpu_association = self._cpu_progression.progress(
                claim,
                target_arn,
                context,
            )
            if cpu_association is not None:
                associations.append(cpu_association)

            network_association = self._network_progression.progress(
                claim,
                target_arn,
                context,
            )
            if network_association is not None:
                associations.append(network_association)

        association_set = OperationalDimensionAssociationSet(context, associations)
        coverage = RegisteredTargetOperationalEvidenceCoverage(claim, association_set)
        return OperationalRetirementReadiness(coverage)
