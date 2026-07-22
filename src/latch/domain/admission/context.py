from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from latch.domain.environment import Environment
from latch.domain.evidence.temporal_context import normalize_aware_datetime


class AdmissionRequest(StrEnum):
    RETIREMENT = "retirement"


@dataclass(frozen=True, slots=True)
class AdmissionEvaluationContext:
    environment: Environment
    requested_retirement: AdmissionRequest
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if self.requested_retirement is not AdmissionRequest.RETIREMENT:
            raise ValueError("requested_retirement must be retirement")

        object.__setattr__(
            self,
            "evaluated_at",
            normalize_aware_datetime(self.evaluated_at, "evaluated_at"),
        )
