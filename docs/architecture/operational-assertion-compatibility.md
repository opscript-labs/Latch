# Operational Assertion Compatibility

Operational Assertion Compatibility is an immutable, symmetric result over two
distinct Operational Dimension Associations.

Valid inputs must have the same dimension, trace to established activity or established
inactivity propositions, belong to the same Admission Evaluation Context, and form a
valid Operational Assertion Temporal Relationship.

The closed outcomes are:

- COMPATIBLE
- INCOMPATIBLE
- UNRESOLVED

The approved compatibility matrix is:

| Proposition pair | OVERLAPPING | FIRST_WHOLELY_BEFORE_SECOND or FIRST_WHOLELY_AFTER_SECOND | TIMELESS_INVOLVED |
|---|---|---|---|
| Activity + Activity | COMPATIBLE | COMPATIBLE | COMPATIBLE |
| Inactivity + Inactivity | COMPATIBLE | COMPATIBLE | COMPATIBLE |
| Activity + Inactivity | INCOMPATIBLE | COMPATIBLE | UNRESOLVED |

Closed-boundary overlap has the same effect as any other overlap.

Compatibility identity is the unordered pair of Dimension Associations. Reversing the
pair produces equal and hash-equal compatibility results. The temporal relationship
and compatibility outcome are derived from the inputs and do not independently
participate in identity.

INCOMPATIBLE means only that two established operational assertions are incompatible
under this matrix. It does not select, discard, prioritize, resolve, or alter either
assertion.

Source preference, source ranking, precedence, weighting, conflict resolution,
assertion discarding, aggregation changes, freshness, TTL, staleness, sufficiency,
verdict behavior, retirement behavior, provider mappings, APIs, persistence,
AWS integration, Terraform resources, dependencies, serialization, registries,
plugins, and generic compatibility frameworks remain deferred.
