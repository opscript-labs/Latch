import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

EC2_INSTANCE_ARN_PATTERN = re.compile(
    r"^arn:"
    r"(?P<partition>aws|aws-cn|aws-us-gov):"
    r"ec2:"
    r"(?P<region>[a-z]{2}(?:-gov)?-[a-z]+-\d):"
    r"(?P<account_id>\d{12}):"
    r"instance/"
    r"(?P<instance_id>i-[0-9a-f]{8,17})$"
)


@dataclass(frozen=True, slots=True)
class Environment:
    identifier: str
    created_at: datetime
    ttl_expires_at: datetime
    owner: str
    resource_target_arns: frozenset[str]

    def __init__(
        self,
        identifier: str,
        created_at: datetime,
        ttl_expires_at: datetime,
        owner: str,
        resource_target_arns: Iterable[str],
    ) -> None:
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "ttl_expires_at", ttl_expires_at)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "resource_target_arns", frozenset(resource_target_arns))
        self.__post_init__()

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("environment identifier must be non-empty")

        if not self.owner.strip():
            raise ValueError("environment owner must be non-empty")

        if not self.resource_target_arns:
            raise ValueError("resource_target_arns must be non-empty")

        for resource_target_arn in self.resource_target_arns:
            if not resource_target_arn.strip():
                raise ValueError("resource_target_arns must contain non-empty values")

            if not EC2_INSTANCE_ARN_PATTERN.fullmatch(resource_target_arn):
                raise ValueError(
                    "resource_target_arns must contain valid EC2 instance ARNs"
                )

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
