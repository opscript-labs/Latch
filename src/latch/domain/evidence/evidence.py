from dataclasses import dataclass

from latch.domain.evidence.source_provenance import SourceProvenance
from latch.domain.evidence.temporal_context import EvidenceTemporalContext


@dataclass(frozen=True, slots=True)
class Evidence:
    """Latch product-domain concept distinct from external operational observations."""

    proposition: str
    referent: str
    source_provenance: SourceProvenance
    temporal_context: EvidenceTemporalContext

    def __post_init__(self) -> None:
        for member_name in (
            "proposition",
            "referent",
        ):
            member_value = getattr(self, member_name)
            if not member_value.strip():
                raise ValueError(f"{member_name} must be non-empty")

        if not isinstance(self.source_provenance, SourceProvenance):
            raise ValueError("source_provenance must be a SourceProvenance")

        if not isinstance(self.temporal_context, EvidenceTemporalContext):
            raise ValueError("temporal_context must be an approved Evidence temporal context")
