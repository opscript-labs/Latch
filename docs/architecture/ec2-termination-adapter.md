# EC2 Termination Adapter

The EC2 termination adapter is a concrete infrastructure adapter for Capability 1
retirement execution. It accepts one Retirement Execution Authorization and
returns the existing EC2 Termination Invocation domain artifact.

The adapter is EC2-specific. It derives target ARNs, instance IDs, account, and
Region exclusively from the authorized Environment through the existing artifact
chain. It revalidates that targets are registered EC2 instance ARNs, belong to one
account, belong to one Region, and match the regional EC2 client.

The adapter constructs one regional EC2 client with the standard AWS SDK
credential provider chain. It passes no static access keys, secrets, or Secrets
Manager values. Production credentials come from the Latch execution workload IAM
role. On ECS, this is the task role, not the task execution role.

The adapter performs exactly one regional batch `TerminateInstances` request for
exactly the registered targets. AWS accepted state-change responses are translated
into per-target invocation results. Missing, duplicate, unexpected, malformed, or
request-level SDK failures are translated into non-accepted invocation results for
the complete registered target set.

Accepted invocation is not confirmed destruction. Destruction confirmation remains
the separate EC2 Destruction Confirmation boundary.

Retries, polling, timeouts, compensation, idempotency, persistence,
orchestration, deregistration, IAM policies, additional target types, provider
abstractions, registries, generic executors, Terraform, APIs, and serialization
remain out of scope.
