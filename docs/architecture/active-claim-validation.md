# Active Claim Validation

Accepted.

Active claim validation is a read-only DynamoDB boundary for one
`RetirementEvaluationClaim`. It is not an admission result, verdict, execution
authorization, refusal, missing-approval result, or unresolved-evidence result.

Validation performs one direct strongly consistent read of the active-registration
key. It does not scan, query the TTL-due GSI, or mutate any record.

The validation fence has exactly four parts:

- Environment identifier;
- immutable-registration fingerprint;
- claim token;
- claim time.

`VALID_ACTIVE_CLAIM` is returned only when the active-registration record contains
all four exact matching values. `INVALID_ACTIVE_CLAIM` is returned when the
registration is absent, the fingerprint differs, the claim token differs, the
claim time differs, or the record is malformed or incomplete for active-claim
validation.

Invalid claim validation is a precondition failure for future
retirement-affecting work, not an admission result. Future retirement-affecting
actions must recheck the active claim immediately before acting.

This validation is explicitly non-atomic with any later action. It does not add
execution atomicity, retries, recovery, claim release, admission coordination,
EC2 invocation, deregistration changes, API behavior, or new product semantics.
