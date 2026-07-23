# Durable Retirement Lock

Accepted.

Durable retirement lock state is internal-only operational state stored on the
existing active-registration item for one immutable Environment. It uses the
existing `RetirementLock` domain artifact and does not add an HTTP endpoint,
external caller authentication, lock release, expiry, delegation, override,
claim behavior, verdict behavior, or execution behavior.

Lock issuance and retrieval require exact active-registration correspondence:
the supplied Environment identifier and immutable registration fingerprint must
match the active-registration item.

Lock state is non-identity operational state. It does not alter Environment
serialization, the immutable registration fingerprint, TTL-due GSI partition key,
sort key, membership, or ordering. It is not stored as a separate DynamoDB item
and does not affect target ownership records.

Issuance uses one conditional DynamoDB update. It succeeds when lock state is
absent or already exactly equal to the approved locked state. Equivalent duplicate
issuance is idempotent. Missing, stale, replaced, mismatched, conflicting,
partial, or malformed state is rejected and stores nothing.

Retrieval returns absence only when exact active-registration correspondence
holds and lock state is completely absent. Missing registrations, fingerprint
mismatches, replacements, and partial or malformed lock state are rejected rather
than reported as absence.

Confirmed deregistration deletes the complete active-registration item, so lock
state is removed automatically without adding lock-specific transaction actions.
Lock state does not block confirmed cleanup.

Authentication, lock release, expiry, delegation, override, retries, recovery,
workflow coordination, API exposure, IAM, Terraform, verdict changes, and
execution behavior remain deferred.
