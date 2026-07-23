import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from latch.domain.environment.environment import Environment


@dataclass(frozen=True, slots=True)
class RetirementEvaluationClaim:
    environment: Environment
    claim_token: str = field(init=False)
    claim_time: datetime = field(compare=False)

    def __init__(self, environment: Environment, claim_time: datetime) -> None:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        if claim_time.tzinfo is None or claim_time.utcoffset() is None:
            raise ValueError("claim_time must be timezone-aware")

        claim_token = str(uuid.uuid4())
        if not claim_token.strip():
            raise ValueError("claim_token must be non-empty")

        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "claim_token", claim_token)
        object.__setattr__(self, "claim_time", claim_time.astimezone(UTC))
