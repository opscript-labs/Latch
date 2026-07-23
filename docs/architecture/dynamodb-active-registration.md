# DynamoDB Active Registration

DynamoDB is the sole active-registration store for Capability 1 in this slice.
An active registration exists only while its immutable record is present.

The DynamoDB active-registration adapter manages one immutable Environment
registration at a time. `Environment.identifier` is the active-registration
partition key and is unique among active registrations. Registration creation
uses one bounded `TransactWriteItems` request containing one conditional
active-registration put and one conditional ownership-reservation put for every
registered target ARN. Existing registrations and active target ownership
reservations are not overwritten, mutated, replaced, versioned, or merged.

The stored record contains the immutable Environment content required to prove
exact registration correspondence: identifier, owner, canonical UTC creation
timestamp, canonical UTC TTL expiry timestamp, the complete registered EC2 target
set, and a deterministic immutable-registration fingerprint.

The fingerprint is derived from all immutable Environment content using a stable
canonical representation, canonical UTC timestamp values, sorted target ARNs, and
SHA-256. Identifier alone is not correspondence.

Each target ownership reservation contains an injectively namespaced primary key,
the exact target ARN, the owning Environment identifier, and the owning immutable
registration fingerprint. Ownership keys use a fixed prefix and the exact target
ARN so they cannot collide with Environment identifier keys. Ownership records do
not contain active-registration GSI attributes such as `record_kind` or
`ttl_expires_at`.

Deregistration is confirmed-only. A non-confirmed EC2 destruction confirmation
performs no DynamoDB mutation. A confirmed destruction confirmation issues one
bounded `TransactWriteItems` request containing one conditional active-registration
delete and one conditional ownership-reservation delete for every registered
target ARN. Reservation deletion requires the same owning Environment identifier
and immutable registration fingerprint. The adapter does not read before deleting
and does not delete a missing, changed, mismatched, or later registration sharing
the identifier. Conditional transaction failures abort the whole operation and
propagate unchanged.

Removal means only that this Environment is no longer actively registered in
Latch and its exact target ownership reservations have been released. It does not
claim all related infrastructure was destroyed.

APIs, scheduling, retries, orchestration, archival, Terraform, IAM,
registration replacement, reads, scans, target discovery, shared ownership,
ownership transfer, compensation, migration, lookup behavior, persistence history,
EventBridge, SQS, Step Functions, ECS changes, and deregistration workflow
orchestration remain deferred.
