# DynamoDB Active Registration

DynamoDB is the sole active-registration store for Capability 1 in this slice.
An active registration exists only while its immutable record is present.

The DynamoDB active-registration adapter manages one immutable Environment
registration at a time. `Environment.identifier` is the partition key and is
unique among active registrations. Registration creation uses one conditional
`PutItem` requiring the identifier not already exist. Existing registrations are
not overwritten, mutated, replaced, versioned, or merged.

The stored record contains the immutable Environment content required to prove
exact registration correspondence: identifier, owner, canonical UTC creation
timestamp, canonical UTC TTL expiry timestamp, the complete registered EC2 target
set, and a deterministic immutable-registration fingerprint.

The fingerprint is derived from all immutable Environment content using a stable
canonical representation, canonical UTC timestamp values, sorted target ARNs, and
SHA-256. Identifier alone is not correspondence.

Deregistration is confirmed-only. A non-confirmed EC2 destruction confirmation
performs no DynamoDB mutation. A confirmed destruction confirmation issues one
conditional `DeleteItem` requiring the Environment identifier and exact immutable
registration fingerprint. The adapter does not read before deleting and does not
delete a missing, changed, mismatched, or later registration sharing the
identifier. Conditional-check failures propagate unchanged.

Removal means only that this Environment is no longer actively registered in
Latch. It does not claim all related infrastructure was destroyed.

APIs, scheduling, retries, orchestration, archival, Terraform, IAM,
registration replacement, reads, scans, queries, lookup behavior, persistence
history, EventBridge, SQS, Step Functions, ECS changes, and deregistration
workflow orchestration remain deferred.
