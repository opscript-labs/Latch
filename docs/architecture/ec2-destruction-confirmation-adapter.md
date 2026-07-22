# EC2 Destruction Confirmation Adapter

The EC2 destruction confirmation adapter is a concrete EC2 read adapter. It
accepts one registered Environment and returns the existing EC2 Destruction
Confirmation domain artifact.

The adapter reuses the ECS task-role-only credential boundary. It derives target
ARNs, instance IDs, account, and Region only from the Environment. It constructs
one regional EC2 client for the registered target Region and performs exactly one
`DescribeInstances` request for exactly the registered instance IDs.

The adapter flattens `Reservations[].Instances[]` into instance-ID and lifecycle
state pairs, then passes only expected registered target results into the domain
confirmation artifact. Invalid or incomplete AWS data becomes non-confirmation,
never termination evidence. Missing, duplicate, unexpected, malformed, or
request-level SDK failures produce an empty valid report for the registered
Environment, causing DESTRUCTION_NOT_CONFIRMED through the domain boundary.

This adapter does not invoke termination, retry, poll, persist state, orchestrate
workflow, deregister an Environment, configure IAM policies, add Terraform
resources, expose APIs, serialize public schemas, or introduce generic AWS reader
abstractions.
