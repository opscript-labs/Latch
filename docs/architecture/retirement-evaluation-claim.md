# Retirement Evaluation Claim

Accepted.

A `RetirementEvaluationClaim` records an exclusive operational claim over one
immutable Environment registration. The claim contains the Environment, an
opaque Latch-generated claim token, and a declared claim time normalized to UTC.
The claim identity is the exact Environment registration and claim token only;
claim time is occurrence metadata.

Claim acquisition is conditional DynamoDB metadata mutation on the active
registration record. Acquisition independently rechecks TTL eligibility against
the persisted canonical `ttl_expires_at` value and does not trust prior GSI
selection. The condition also requires the matching identifier, matching
immutable-registration fingerprint, and absence of an existing claim token.

Successful acquisition writes only non-identity operational claim metadata:
`evaluation_claim_token` and canonical `evaluation_claim_time`. Claims are
exclusive and non-expiring in this slice. The claimed registration remains
active.

Failed claims are non-diagnostic. A conditional failure returns no claim and
does not reveal whether the registration was missing, changed, already claimed,
or not yet due.

The claim does not authorize admission evaluation, EC2 invocation, destruction
confirmation, deregistration, or retirement execution. Future
retirement-affecting work must require an active matching claim token.

Claim release, expiry, recovery, reassignment, retry, timeout, leases, fencing,
evaluation, evidence collection, orchestration, APIs, Terraform, IAM, execution
changes, and generic locking or workflow frameworks remain deferred.
