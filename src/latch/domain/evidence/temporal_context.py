from dataclasses import dataclass
from datetime import UTC, datetime


def normalize_aware_datetime(value: datetime, member_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{member_name} must be timezone-aware")

    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class EvidenceInstant:
    instant: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instant",
            normalize_aware_datetime(self.instant, "instant"),
        )


@dataclass(frozen=True, slots=True)
class EvidenceInterval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        normalized_start = normalize_aware_datetime(self.start, "start")
        normalized_end = normalize_aware_datetime(self.end, "end")

        if normalized_start > normalized_end:
            raise ValueError("start must be earlier than or equal to end")

        object.__setattr__(self, "start", normalized_start)
        object.__setattr__(self, "end", normalized_end)


@dataclass(frozen=True, slots=True)
class EvidenceTimeless:
    pass


EvidenceTemporalContext = EvidenceInstant | EvidenceInterval | EvidenceTimeless
