# Durable Owner Retirement Approval

Accepted.

Durable owner retirement approval is internal-only operational state stored on
the existing active-registration item. It does not add an HTTP endpoint,
external caller authentication, delegation, revocation, expiry, lock behavior,
verdict behavior, or execution behavior.

Approval issuance and retrieval are scoped to one `RetirementEvaluationClaim`
and one `AdmissionEvaluationContext`. The Context Environment must exactly equal
the claim Environment, the requested action must be retirement, and
`evaluated_at` must exactly equal the claim time.

The active registration must match the Environment identifier, immutable
registration fingerprint, active claim token, and active claim time. The approval
owner must exactly equal the recorded Environment owner.

Approval state is non-identity operational state and does not alter Environment
serialization, the immutable registration fingerprint, TTL-due GSI attributes,
target ownership records, or registration ordering. Stored approval content is
limited to approval claim token, approval claim time, approved action, and
approved owner.

Issuance uses one conditional DynamoDB update. It succeeds when approval state is
absent, or when stored approval state is already exactly equivalent to the
requested immutable approval content. Equivalent duplicate issuance is
idempotent. Conflicting, partial, malformed, stale, or mismatched approval state
is rejected and stores nothing.

Retrieval returns absence only when the exact active registration, claim, and
Context match and approval state is completely absent. Missing registrations,
changed fingerprints, mismatched claim token or time, mismatched Context, and
partial, malformed, or internally inconsistent stored approval state are rejected
rather than reported as absence.

Confirmed deregistration deletes the complete active-registration item, so
approval state is removed automatically without adding approval-specific
transaction actions.

Authentication, delegation, revocation, expiry, retries, recovery, workflow
coordination, API exposure, IAM, Terraform, verdict changes, and execution
behavior remain deferred.
