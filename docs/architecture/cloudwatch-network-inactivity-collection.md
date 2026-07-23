# CloudWatch Network Inactivity Collection

Accepted.

CloudWatch network inactivity collection is a concrete per-target collection and
progression boundary. It accepts one `RetirementEvaluationClaim` and one EC2
target ARN that is an exact member of the claim Environment registration.

The collector uses the ECS task-role credential boundary and creates one
regional CloudWatch client in the target ARN Region. It performs exactly one
`GetMetricData` request with two stable query IDs: `NetworkIn` and `NetworkOut`.
Both queries use `AWS/EC2`, the exact target `InstanceId`, `Sum`, and a 300-second
period.

The claim time is the evaluation time. The observation end is the latest UTC
five-minute boundary at or before the claim time, and the observation start is
30 minutes before that end. The queried interval is
`[observation_start, observation_end)`. The six required timestamps are exactly
the period starts `observation_start + n * 5 minutes` for `n = 0..5`; the end is
exclusive.

A successful response is affirmative only when exactly two metric results are
returned, their identities exactly match the two requested query IDs, result
order has no meaning, both statuses are `Complete`, no pagination token remains,
each metric has exactly six one-to-one timestamp/value pairs, every required
timestamp appears once with no outside timestamps, all values are finite numeric
values, and every `NetworkIn` and `NetworkOut` value is strictly below 1024
bytes.

Missing, duplicate, substituted, or unexpected query IDs are non-affirmative.
Malformed data and threshold failures are also non-affirmative and produce no
Evidence. Request-level AWS SDK failure is collection failure and propagates
unchanged.

Affirmative collection produces exactly one canonical Evidence artifact and one
`OPERATIONAL_INACTIVITY` classification association. The narrow progression then
composes existing relevance, assertion projection, source standing, and
establishment semantics to create `OperationalDimensionAssociation` with
`NETWORK_ACTIVITY` only after established operational inactivity.

No CPU association, activity Evidence, aggregate, readiness, verdict, execution,
or other downstream artifact is produced. Retries, polling, multi-target
aggregation, provider discovery, persistence, APIs, Terraform, orchestration,
activity collection, and generic abstractions remain deferred.
