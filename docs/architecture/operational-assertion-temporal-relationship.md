# Operational Assertion Temporal Relationship

An Operational Assertion Temporal Relationship is an immutable result derived from an
ordered pair of Operational Dimension Associations.

Valid pairs must have the same operational dimension and must trace to established
outcomes in the same Admission Evaluation Context. Invalid pairs are rejected rather
than assigned a relationship.

The closed outcome vocabulary is:

- OVERLAPPING
- FIRST_WHOLELY_BEFORE_SECOND
- FIRST_WHOLELY_AFTER_SECOND
- TIMELESS_INVOLVED

Comparison rules:

- Any TIMELESS temporal context involved maps to TIMELESS_INVOLVED.
- INSTANT is a zero-duration point.
- Same instants overlap.
- Different instants are before or after according to their order.
- An instant and closed interval overlap when the instant is within `[start, end]`.
- Two closed intervals overlap unless the first ends strictly before the second starts,
  or the first starts strictly after the second ends.
- Intervals meeting at a boundary instant overlap.

Identity is ordered and consists only of the first and second dimension associations.
Reversing an overlapping or timeless pair preserves the outcome. Reversing before or
after produces the inverse directed outcome.

Compatibility, conflict handling, precedence, freshness, authority, sufficiency,
verdict behavior, retirement behavior, source-ranking changes, provider mappings,
APIs, persistence, AWS integration, Terraform resources, dependencies, serialization,
registries, plugins, and generic comparison frameworks remain deferred.
