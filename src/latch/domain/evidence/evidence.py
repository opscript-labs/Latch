from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Evidence:
    """Latch product-domain concept distinct from external operational observations."""

    proposition: str
    referent: str
    source_provenance: str
    temporal_context: str

    def __post_init__(self) -> None:
        for member_name in (
            "proposition",
            "referent",
            "source_provenance",
            "temporal_context",
        ):
            member_value = getattr(self, member_name)
            if not member_value.strip():
                raise ValueError(f"{member_name} must be non-empty")
