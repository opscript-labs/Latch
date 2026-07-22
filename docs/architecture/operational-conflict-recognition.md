# Operational Conflict Recognition

Operational Conflict Recognition is an immutable, pair-specific result derived solely
from one Operational Assertion Compatibility result.

The closed outcomes are:

- OPERATIONAL_CONFLICT_RECOGNIZED
- NO_OPERATIONAL_CONFLICT_RECOGNIZED
- OPERATIONAL_CONFLICT_STATUS_UNRESOLVED

The deterministic mapping is:

- INCOMPATIBLE maps to OPERATIONAL_CONFLICT_RECOGNIZED.
- COMPATIBLE maps to NO_OPERATIONAL_CONFLICT_RECOGNIZED.
- UNRESOLVED maps to OPERATIONAL_CONFLICT_STATUS_UNRESOLVED.

OPERATIONAL_CONFLICT_STATUS_UNRESOLVED is neither a recognized conflict nor
confirmation of no conflict.

Recognition identity is the Compatibility result only. The recognition outcome is
derived and does not independently participate in identity.

Recognition is pair-specific only. It does not aggregate, resolve, select, discard,
prioritize, reconcile, or alter assertions.

Aggregation, resolution, weighting, source precedence, sufficiency, verdict behavior,
retirement behavior, provider mappings, APIs, persistence, AWS integration,
Terraform resources, dependencies, serialization, registries, plugins, and generic
conflict frameworks remain deferred.
