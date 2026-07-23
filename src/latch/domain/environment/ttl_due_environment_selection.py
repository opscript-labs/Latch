from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from latch.domain.environment.environment import Environment


@dataclass(frozen=True, slots=True)
class TtlDueEnvironmentSelection:
    selection_time: datetime
    environments: frozenset[Environment]
    is_partial: bool = field(init=False, compare=False)

    def __init__(
        self,
        selection_time: datetime,
        environments: Iterable[Environment],
        *,
        page_has_last_evaluated_key: bool,
    ) -> None:
        if selection_time.tzinfo is None or selection_time.utcoffset() is None:
            raise ValueError("selection_time must be timezone-aware")

        environment_set = frozenset(environments)
        for environment in environment_set:
            if not isinstance(environment, Environment):
                raise ValueError("environments must contain Environment values")

        object.__setattr__(
            self,
            "selection_time",
            selection_time.astimezone(UTC),
        )
        object.__setattr__(self, "environments", environment_set)
        object.__setattr__(self, "is_partial", page_has_last_evaluated_key)
