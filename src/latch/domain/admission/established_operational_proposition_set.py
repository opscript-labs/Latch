from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from latch.domain.admission.context import AdmissionEvaluationContext
from latch.domain.admission.source_standing import (
    OperationalAssertionEstablishment,
    OperationalEstablishmentOutcome,
)


class EstablishedOperationalProposition(Enum):
    OPERATIONAL_ACTIVITY = "OPERATIONAL_ACTIVITY"
    OPERATIONAL_INACTIVITY = "OPERATIONAL_INACTIVITY"


@dataclass(frozen=True, slots=True)
class EstablishedOperationalPropositionSet:
    context: AdmissionEvaluationContext
    supporting_establishments: frozenset[OperationalAssertionEstablishment] = field(
        default_factory=frozenset
    )

    def __init__(
        self,
        context: AdmissionEvaluationContext,
        supporting_establishments: Iterable[OperationalAssertionEstablishment] = (),
    ) -> None:
        if not isinstance(context, AdmissionEvaluationContext):
            raise ValueError("context must be an AdmissionEvaluationContext")

        normalized_supports = frozenset(supporting_establishments)
        for support in normalized_supports:
            if not isinstance(support, OperationalAssertionEstablishment):
                raise ValueError("supporting_establishments must contain establishments")

            if support.outcome is OperationalEstablishmentOutcome.ESTABLISHES_NOTHING:
                raise ValueError("ESTABLISHES_NOTHING cannot support an established set")

            if support.projection.context != context:
                raise ValueError("supporting establishment must belong to the aggregate context")

        object.__setattr__(self, "context", context)
        object.__setattr__(self, "supporting_establishments", normalized_supports)

    @property
    def members(self) -> frozenset[EstablishedOperationalProposition]:
        members: set[EstablishedOperationalProposition] = set()
        for support in self.supporting_establishments:
            if support.outcome is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_ACTIVITY:
                members.add(EstablishedOperationalProposition.OPERATIONAL_ACTIVITY)
            elif (
                support.outcome
                is OperationalEstablishmentOutcome.ESTABLISHES_OPERATIONAL_INACTIVITY
            ):
                members.add(EstablishedOperationalProposition.OPERATIONAL_INACTIVITY)

        return frozenset(members)
