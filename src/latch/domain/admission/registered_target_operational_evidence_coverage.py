from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.operational_dimension import OperationalDimension
from latch.domain.admission.operational_dimension_association_set import (
    OperationalDimensionAssociationSet,
)
from latch.domain.admission.source_standing import OperationalEstablishmentOutcome
from latch.domain.environment import RetirementEvaluationClaim


class RegisteredTargetOperationalEvidenceCoverageOutcome(Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class RegisteredTargetOperationalEvidenceCoverage:
    claim: RetirementEvaluationClaim
    association_set: OperationalDimensionAssociationSet
    outcome: RegisteredTargetOperationalEvidenceCoverageOutcome = field(
        init=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.claim, RetirementEvaluationClaim):
            raise ValueError("claim must be a RetirementEvaluationClaim")

        if not isinstance(self.association_set, OperationalDimensionAssociationSet):
            raise ValueError("association_set must be an OperationalDimensionAssociationSet")

        if self.association_set.context.environment != self.claim.environment:
            raise ValueError("association_set context Environment must match claim")

        if self.association_set.context.evaluated_at != self.claim.claim_time:
            raise ValueError("association_set context evaluated_at must match claim_time")

        object.__setattr__(self, "outcome", self._derive_outcome())

    def _derive_outcome(self) -> RegisteredTargetOperationalEvidenceCoverageOutcome:
        for target_arn in self.claim.environment.resource_target_arns:
            if not (
                self._has_inactivity_for_target_dimension(
                    target_arn,
                    OperationalDimension.CPU_ACTIVITY,
                )
                and self._has_inactivity_for_target_dimension(
                    target_arn,
                    OperationalDimension.NETWORK_ACTIVITY,
                )
            ):
                return RegisteredTargetOperationalEvidenceCoverageOutcome.INCOMPLETE

        return RegisteredTargetOperationalEvidenceCoverageOutcome.COMPLETE

    def _has_inactivity_for_target_dimension(
        self,
        target_arn: str,
        dimension: OperationalDimension,
    ) -> bool:
        return any(
            association.dimension is dimension
            and association.establishment.outcome
            is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY
            and association.establishment.projection.association.evidence.referent == target_arn
            for association in self.association_set.associations
        )
