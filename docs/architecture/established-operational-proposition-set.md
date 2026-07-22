# Established Operational Proposition Set

An Established Operational Proposition Set is immutable and scoped to exactly one
Admission Evaluation Context.

The only permitted proposition members are:

- OPERATIONAL_ACTIVITY
- OPERATIONAL_INACTIVITY

An empty set is valid and means no operational proposition has been independently
established for that context.

The aggregate retains an immutable unordered set of supporting operational
establishment outcomes. Identity is based only on the Admission Evaluation Context and
that unordered support set. Input order does not affect identity or membership.

Multiple establishment outcomes for the same proposition produce one proposition
member while retaining all supporting outcomes. Operational activity and operational
inactivity may coexist unchanged.

Conflict resolution, sufficiency, weighting, priority, freshness, verdict behavior,
retirement execution, provider mappings, APIs, persistence, AWS integration,
Terraform resources, dependencies, serialization, and generic collection abstractions
remain deferred.
