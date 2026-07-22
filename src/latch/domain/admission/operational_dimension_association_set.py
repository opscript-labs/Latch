from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import combinations

from latch.domain.admission.context import AdmissionEvaluationContext
from latch.domain.admission.operational_dimension import OperationalDimensionAssociation

OperationalDimensionAssociationPair = frozenset[OperationalDimensionAssociation]


@dataclass(frozen=True, slots=True)
class OperationalDimensionAssociationSet:
    context: AdmissionEvaluationContext
    associations: frozenset[OperationalDimensionAssociation] = field(default_factory=frozenset)

    def __init__(
        self,
        context: AdmissionEvaluationContext,
        associations: Iterable[OperationalDimensionAssociation] = (),
    ) -> None:
        if not isinstance(context, AdmissionEvaluationContext):
            raise ValueError("context must be an AdmissionEvaluationContext")

        normalized_associations = frozenset(associations)
        for association in normalized_associations:
            if not isinstance(association, OperationalDimensionAssociation):
                raise ValueError("associations must contain OperationalDimensionAssociation values")

            if association.establishment.projection.context != context:
                raise ValueError("association must belong to the association set context")

        object.__setattr__(self, "context", context)
        object.__setattr__(self, "associations", normalized_associations)

    @property
    def required_comparison_pairs(self) -> tuple[OperationalDimensionAssociationPair, ...]:
        pairs = []
        ordered_associations = sorted(self.associations, key=repr)
        for first, second in combinations(ordered_associations, 2):
            if first.dimension is second.dimension:
                pairs.append(frozenset({first, second}))

        return tuple(sorted(pairs, key=repr))
