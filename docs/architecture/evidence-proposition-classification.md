# Evidence Proposition Classification

Evidence proposition classification is a separate immutable association between one
canonical Evidence artifact and one classification.

The approved closed classification vocabulary is:

- OPERATIONAL_ACTIVITY
- OPERATIONAL_INACTIVITY
- UNCLASSIFIED

The association does not alter canonical Evidence, its identity, or its representation.

UNCLASSIFIED remains canonical Evidence but cannot establish retirement relevance.

For the narrow approved relevance check, classified Evidence is relevant to an
Admission Evaluation Context if and only if its classification is OPERATIONAL_ACTIVITY
or OPERATIONAL_INACTIVITY, its referent corresponds to the registered Environment
bound to the context, and its temporal context is not wholly after the context's
evaluation time.

Referent correspondence is exact canonical string equality only. Evidence corresponds
when its referent exactly equals the registered Environment identifier or exactly
equals one immutable registered target ARN in the Context Environment's
`resource_target_arns`.

Target-scoped correspondence is exact immutable target-set membership. Latch does not
normalize, parse, infer, or match correspondence by tags, account, Region, instance ID
similarity, textual similarity, or provider discovery.

Temporal context is wholly after evaluation time exactly when INSTANT(t) has
`t > evaluated_at`, or INTERVAL(start, end) has `start > evaluated_at`. TIMELESS is
never wholly after evaluation time.

Automatic classification, provider mappings, authority, truth, reliability, freshness,
TTL, sufficiency, conflicts, verdicts, APIs, persistence, AWS integration, and broader
temporal interpretation remain deferred.

The same-target-across-active-registrations ownership or exclusivity question remains
deferred. Target correspondence does not change downstream admission semantics and does
not establish assertion, standing, establishment, dimension, readiness, verdict, or
execution behavior.
