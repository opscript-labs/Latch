# TTL-Due Registration Selection

Accepted.

Active Environment registration records include `record_kind =
ACTIVE_ENVIRONMENT_REGISTRATION` and a canonical `ttl_expires_at` index value. The
timestamp form is UTC RFC 3339 with a `Z` suffix and fixed six-digit fractional
second precision so lexical ordering preserves chronological ordering.

TTL-due registration selection is a page-scoped candidate observation from the
DynamoDB active-registration store. The query uses the fixed active-registration
record kind and selects records whose canonical TTL expiry is less than or equal
to the canonical selection time.

Each returned record must reconstruct the immutable `Environment` exactly and
must match the deterministic immutable-registration fingerprint. Malformed,
inconsistent, or non-reconstructable records fail the selection operation.

`TtlDueEnvironmentSelection` contains the normalized UTC selection time, an
immutable unordered set of reconstructed Environments from one DynamoDB query
page, and an explicit partial indicator. The partial indicator means only that
the DynamoDB page contained `LastEvaluatedKey`; the key is not exposed,
persisted, or continued from this artifact.

The selection is eventually consistent candidate observation. Absence from one
result does not prove no due registration exists, and a partial selection makes
no completeness claim. Repeated selection is permitted. The fixed `record_kind`
partition is an MVP scaling pressure point.

Scheduling, trigger behavior, pagination continuation, retries, leases,
idempotency, concurrency, evaluation, admission, authorization, execution,
deregistration, and infrastructure deployment remain deferred.
