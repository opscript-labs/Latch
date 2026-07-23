from dataclasses import dataclass
from typing import Literal

from latch.domain.environment.environment import Environment


@dataclass(frozen=True, slots=True)
class RetirementAdmissionRequest:
    environment_identity: Environment
    retirement_claim_identity: str
    claimant_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.environment_identity, Environment):
            raise ValueError("environment_identity must be an Environment")
        if (
            not isinstance(self.retirement_claim_identity, str)
            or not self.retirement_claim_identity.strip()
        ):
            raise ValueError("retirement_claim_identity must be a non-empty string")
        if (
            not isinstance(self.claimant_identity, str)
            or not self.claimant_identity.strip()
        ):
            raise ValueError("claimant_identity must be a non-empty string")
        
        # Ingress claimant identity shall be validated exactly as approved.
        # claimant_identity == Environment.owner (exact case-sensitive check)
        if self.claimant_identity != self.environment_identity.owner:
            raise ValueError("claimant_identity must match environment owner exactly")


@dataclass(frozen=True, slots=True)
class RetirementAdmissionRequested:
    request: RetirementAdmissionRequest
    product_event_type: Literal["RETIREMENT_ADMISSION_REQUESTED"] = "RETIREMENT_ADMISSION_REQUESTED"

    def __post_init__(self) -> None:
        if not isinstance(self.request, RetirementAdmissionRequest):
            raise ValueError("request must be a RetirementAdmissionRequest")
        if self.product_event_type != "RETIREMENT_ADMISSION_REQUESTED":
            raise ValueError("product_event_type must be RETIREMENT_ADMISSION_REQUESTED")
