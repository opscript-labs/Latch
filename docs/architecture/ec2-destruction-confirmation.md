# EC2 Destruction Confirmation

EC2 Destruction Confirmation is an immutable execution-domain artifact derived
from one registered Environment and immutable AWS-reported lifecycle states for
EC2 instance ARNs.

Each reported state pairs exactly one target ARN with one non-empty AWS-reported
lifecycle state. Reported states do not add identifiers, timestamps, provider
calls, or execution behavior.

The closed outcome vocabulary is:

- DESTRUCTION_CONFIRMED
- DESTRUCTION_NOT_CONFIRMED

Confirmation is all-or-nothing across explicit registered EC2 targets. Only
registered target ARNs participate. DESTRUCTION_CONFIRMED means AWS reported
every registered EC2 target as exactly `terminated`. Missing registered targets,
outside targets, duplicate states for one target, or any other lifecycle state do
not confirm destruction.

Confirmation does not authorize execution, prove command success, confirm related
resource destruction, deregister the Environment, define retries, polling,
persistence, orchestration, or AWS client behavior.

This boundary does not add boto3, TerminateInstances, polling, retries, timeouts,
compensation, idempotency, orchestration, deregistration, provider discovery,
persistence, APIs, serialization, Terraform resources, or generic target-state
abstractions.
