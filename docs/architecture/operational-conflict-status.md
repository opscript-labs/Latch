# Operational Conflict Status

Operational Conflict Status is an immutable result derived solely from one Operational
Conflict Recognition Coverage.

The closed status vocabulary is:

- OPERATIONAL_CONFLICT_PRESENT
- OPERATIONAL_CONFLICT_STATUS_UNRESOLVED
- NO_OPERATIONAL_CONFLICT_RECOGNIZED

The deterministic mapping is:

- At least one OPERATIONAL_CONFLICT_RECOGNIZED maps to OPERATIONAL_CONFLICT_PRESENT.
- Otherwise, at least one OPERATIONAL_CONFLICT_STATUS_UNRESOLVED maps to
  OPERATIONAL_CONFLICT_STATUS_UNRESOLVED.
- Otherwise, including empty coverage, maps to NO_OPERATIONAL_CONFLICT_RECOGNIZED.

Recognized conflict takes precedence over unresolved results. The coverage is preserved
unchanged; pair-level results are not discarded or resolved.

NO_OPERATIONAL_CONFLICT_RECOGNIZED means only that no conflict was recognized within
complete coverage of the supplied Operational Dimension Association Set. It does not
imply globally complete collection, conflict resolution, evidence sufficiency,
retirement safety, or an admission verdict.

Conflict resolution, precedence beyond this aggregate mapping, weighting, sufficiency,
verdicts, retirement execution, provider collection, APIs, persistence, serialization,
AWS integration, Terraform resources, dependencies, registries, plugins, and generic
evaluation abstractions remain deferred.
