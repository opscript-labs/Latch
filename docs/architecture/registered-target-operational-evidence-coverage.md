# Registered-Target Operational Evidence Coverage

Accepted.

Registered-target operational evidence coverage is an immutable,
claim-scoped artifact. It contains one `RetirementEvaluationClaim` and one
`OperationalDimensionAssociationSet`. Its identity is exactly that claim and
association set.

The association set must belong to the same immutable Environment as the claim,
and its Context `evaluated_at` must equal the claim time exactly. Mismatches are
construction failures.

Coverage traces operational evidence to registered targets by exact canonical
Evidence referent equality. For every exact target ARN in the claimed
Environment registration, coverage requires at least one supplied association
that establishes operational inactivity for `CPU_ACTIVITY` and at least one
supplied association that establishes operational inactivity for
`NETWORK_ACTIVITY`. The antecedent Evidence referent must equal that target ARN.

An association for target A never satisfies coverage for target B. Multiple
qualifying associations for the same target and dimension are preserved in the
supplied set but do not add requirements.

`COMPLETE` means every registered target has both CPU and network inactivity
coverage in the supplied set. `INCOMPLETE` means any registered target lacks
either requirement. Partial supplied sets are valid input but cannot be
`COMPLETE`; they make retirement readiness unresolved unless a higher-priority
disqualifier applies.

Provider failures remain outside coverage. Collection failures must propagate
before coverage construction and produce neither coverage nor readiness.

Operational retirement readiness now derives from registered-target coverage. It
still uses the underlying association set only for already-approved
disqualifying conditions and conflict behavior. Existing downstream prerequisite,
approval, lock, verdict, and authorization boundaries are unchanged.

Activity collection, multi-target collector orchestration, active-registration
exclusivity, provider recovery, persistence, APIs, retries, Terraform, execution
behavior, and new verdict semantics remain deferred.
