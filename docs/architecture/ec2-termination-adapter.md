# EC2 Termination Adapter

The EC2 termination adapter is a concrete infrastructure adapter for Capability 1
retirement execution. It accepts one Retirement Execution Authorization and
returns the existing EC2 Termination Invocation domain artifact.

The adapter is EC2-specific. It derives target ARNs, instance IDs, account, and
Region exclusively from the authorized Environment through the existing artifact
chain. It revalidates that targets are registered EC2 instance ARNs, belong to one
account, belong to one Region, and match the regional EC2 client.

Real Capability 1 retirement execution runs only in ECS. The adapter constructs
one regional EC2 client using credentials from the Latch execution workload IAM
role. On ECS, this is the task role, not the task execution role.

The adapter requires `AWS_CONTAINER_CREDENTIALS_RELATIVE_URI` to be present and
to contain a valid relative credential URI path. It fails closed otherwise. The
credential factory uses botocore's ECS container credential provider as the sole
provider so returned credentials remain refreshable task-role credentials.

Static credentials, profile/shared-file credentials, EC2 instance metadata,
Secrets Manager, web identity, full-URI credentials, authorization-token
settings, and default AWS credential chains are excluded.

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
remain out of scope. The future confirmation adapter must reuse the same ECS
task-role credential factory.
