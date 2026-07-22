from collections.abc import Iterable
from dataclasses import dataclass, field

from latch.domain.admission.context import AdmissionEvaluationContext
from latch.domain.admission.operational_conflict import OperationalConflictRecognition


@dataclass(frozen=True, slots=True)
class OperationalConflictSet:
    context: AdmissionEvaluationContext
    recognitions: frozenset[OperationalConflictRecognition] = field(default_factory=frozenset)

    def __init__(
        self,
        context: AdmissionEvaluationContext,
        recognitions: Iterable[OperationalConflictRecognition] = (),
    ) -> None:
        if not isinstance(context, AdmissionEvaluationContext):
            raise ValueError("context must be an AdmissionEvaluationContext")

        normalized_recognitions = frozenset(recognitions)
        for recognition in normalized_recognitions:
            if not isinstance(recognition, OperationalConflictRecognition):
                raise ValueError("recognitions must contain OperationalConflictRecognition results")

            if _recognition_context(recognition) != context:
                raise ValueError("recognition must belong to the conflict set context")

        object.__setattr__(self, "context", context)
        object.__setattr__(self, "recognitions", normalized_recognitions)


def _recognition_context(
    recognition: OperationalConflictRecognition,
) -> AdmissionEvaluationContext:
    first_association = next(iter(recognition.compatibility.associations))
    return first_association.establishment.projection.context
