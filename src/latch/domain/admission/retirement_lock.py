from dataclasses import dataclass

from latch.domain.environment import Environment


@dataclass(frozen=True, slots=True)
class RetirementLock:
    environment: Environment

    def __post_init__(self) -> None:
        if not isinstance(self.environment, Environment):
            raise ValueError("environment must be an Environment")
