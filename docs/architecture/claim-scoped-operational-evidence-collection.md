# Claim-Scoped Operational Evidence Collection

Accepted.

Claim-scoped operational evidence collection evaluates exactly one
`RetirementEvaluationClaim` across the complete immutable registered target set
on the claimed Environment.

Each invocation creates one `AdmissionEvaluationContext` from the claim
Environment, the sole retirement request, and `evaluated_at` exactly equal to the
claim time. Every affirmative CPU or network association retained for the
invocation must belong to that same Context before the association set is formed.

Targets are derived only from `claim.environment.resource_target_arns` and are
traversed in lexicographic order for reproducible engineering behavior. That
order has no product meaning and does not affect identity.

For every registered target, the coordinator attempts CPU inactivity progression
and network inactivity progression in one fixed order. Valid non-affirmative
collection returns no association and does not stop subsequent metric or target
collection.

A request-level provider failure stops collection immediately, propagates
unchanged, and produces no association set, coverage artifact, readiness result,
persistent state, event, or partial output.

Only after all required collection attempts complete without failure does the
coordinator construct the existing `OperationalDimensionAssociationSet`, existing
registered-target operational evidence coverage, and existing
`OperationalRetirementReadiness`.

This slice adds no claim-level result artifact, persistence, retry, recovery,
claim release, workflow framework, multi-target collection abstraction,
conflicts, verdicts, authorization, execution, confirmation, deregistration, or
Terraform behavior.
