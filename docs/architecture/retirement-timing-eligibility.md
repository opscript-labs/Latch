# Retirement Timing Eligibility

Retirement Timing Eligibility is an immutable result derived solely from one
Admission Evaluation Context.

The closed outcome vocabulary is:

- RETIREMENT_TIME_NOT_ELIGIBLE
- RETIREMENT_TIME_ELIGIBLE

The deterministic mapping is:

- `evaluated_at < environment.ttl_expires_at` maps to
  RETIREMENT_TIME_NOT_ELIGIBLE.
- `evaluated_at >= environment.ttl_expires_at` maps to
  RETIREMENT_TIME_ELIGIBLE.

Exact expiry is eligible. The artifact reuses the Environment TTL boundary and
preserves the Context and Environment unchanged. Its identity consists only of
the Admission Evaluation Context; the outcome is derived and does not
independently participate in identity.

Timing eligibility is only a TTL condition. It does not establish operational
readiness, broader evidence sufficiency, an admission verdict, retirement
execution authority, or retirement safety.

Readiness combination, owner approval, locks, overrides, sessions, CloudTrail,
APIs, persistence, provider collection, serialization, AWS integration,
Terraform resources, dependencies, registries, plugins, and generic evaluators
remain deferred.
