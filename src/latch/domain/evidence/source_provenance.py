from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    source_system: str
    source_occurrence: str

    def __post_init__(self) -> None:
        if not self.source_system.strip():
            raise ValueError("source_system must be non-empty")

        if not self.source_occurrence.strip():
            raise ValueError("source_occurrence must be non-empty")
