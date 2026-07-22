from dataclasses import dataclass, field

from latch.domain.admission.context import AdmissionEvaluationContext


@dataclass(frozen=True, slots=True)
class OwnerRetirementApproval:
    context: AdmissionEvaluationContext
    approved_by: str = field(compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, AdmissionEvaluationContext):
            raise ValueError("context must be an AdmissionEvaluationContext")

        if not self.approved_by.strip():
            raise ValueError("approved_by must be non-empty")

        if self.approved_by != self.context.environment.owner:
            raise ValueError("approved_by must match the environment owner")
