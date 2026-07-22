# Operational Conflict Set

An Operational Conflict Set is immutable and scoped to exactly one Admission
Evaluation Context.

The set records only supplied pair-specific Operational Conflict Recognition results.
It provides no context-level conflict status, does not imply all possible assertion
pairs were compared, and does not derive any aggregate conflict status.

An empty set is valid. Empty does not mean "no conflict"; it only means no
recognitions were supplied.

The set preserves all three approved recognition outcomes without interpretation:

- OPERATIONAL_CONFLICT_RECOGNIZED
- NO_OPERATIONAL_CONFLICT_RECOGNIZED
- OPERATIONAL_CONFLICT_STATUS_UNRESOLVED

Identity consists only of the Admission Evaluation Context and an unordered frozenset
of recognition results. Equal recognition results collapse through set semantics, and
input order does not affect identity or hashing.

Pair generation, aggregate status, conflict resolution, weighting, sufficiency,
verdict logic, retirement behavior, provider mappings, APIs, persistence,
AWS integration, Terraform resources, dependencies, generic collection abstractions,
and serialization remain deferred.
