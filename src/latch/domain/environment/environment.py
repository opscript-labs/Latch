from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Environment:
    identifier: str
    created_at: datetime
    ttl_expires_at: datetime
    owner: str

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("environment identifier must be non-empty")

        if not self.owner.strip():
            raise ValueError("environment owner must be non-empty")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        if self.ttl_expires_at.tzinfo is None or self.ttl_expires_at.utcoffset() is None:
            raise ValueError("ttl_expires_at must be timezone-aware")

        if self.ttl_expires_at <= self.created_at:
            raise ValueError("ttl_expires_at must be later than created_at")

    def is_ttl_expired(self, now: datetime) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")

        return now >= self.ttl_expires_at
