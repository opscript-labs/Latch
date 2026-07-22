# Retirement Prerequisite Status

Retirement Prerequisite Status is an immutable result derived from exactly one
Operational Retirement Readiness artifact.

The artifact is context-scoped through readiness: the Admission Evaluation
Context is obtained from the readiness artifact's Operational Dimension
Association Set. Retirement Timing Eligibility is then derived from that Context.
The prerequisite status retains readiness as its exclusive identity; timing
eligibility and outcome are derived and do not independently participate in
identity.

The closed outcome vocabulary is:

- RETIREMENT_PREREQUISITES_SATISFIED
- RETIREMENT_PREREQUISITES_NOT_SATISFIED
- RETIREMENT_PREREQUISITES_UNRESOLVED

The deterministic mapping is:

- Timing eligible and readiness READY maps to
  RETIREMENT_PREREQUISITES_SATISFIED.
- Timing not eligible, or readiness NOT_READY, maps to
  RETIREMENT_PREREQUISITES_NOT_SATISFIED.
- Otherwise, the result is RETIREMENT_PREREQUISITES_UNRESOLVED.

NOT_SATISFIED takes precedence over UNRESOLVED.

SATISFIED means only that the approved operational-readiness and TTL-timing
prerequisites are satisfied. It does not infer owner approval, locks, overrides,
broader evidence sufficiency, an Admission verdict, retirement authorization, or
execution authority.

Collection, owner approval, locks, overrides, sessions, CloudTrail, APIs,
persistence, serialization, AWS integration, Terraform resources, dependencies,
registries, plugins, and generic evaluators remain deferred.
