# EC2 Termination Invocation

One Environment maps to one same-account, same-Region EC2 target set containing
from 1 through 1,000 explicitly registered EC2 instance ARNs.

EC2 Termination Invocation is an immutable execution-domain artifact derived from
one Retirement Execution Authorization and an unordered set of per-target
invocation results. The Environment target set comes through the existing
authorization context chain; no Environment or target set is supplied separately.

Each per-target invocation result contains only one registered EC2 target ARN and
whether AWS returned an accepted state-change result for that exact target.

The closed invocation outcome vocabulary is:

- EC2_TERMINATION_REQUEST_ACCEPTED
- EC2_TERMINATION_REQUEST_NOT_ACCEPTED

A batch invocation is accepted only when AWS returned accepted state-change
results for every registered target. Missing registered targets, unknown returned
targets, duplicate returned targets, or any non-accepted result do not produce
acceptance. Partial acceptance is not accepted, but may still have changed target
state.

Invocation acceptance is distinct from EC2 destruction confirmation. It does not
mean instances are terminated.

This slice adds no AWS SDK, credentials, API calls, TerminateInstances invocation,
retries, polling, timeouts, compensation, idempotency, orchestration,
persistence, APIs, serialization, Terraform resources, or deregistration
behavior.
