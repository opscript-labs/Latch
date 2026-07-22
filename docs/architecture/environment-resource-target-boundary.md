# Environment Resource Target Boundary

An Environment registration contains an explicit immutable unordered set of
represented infrastructure resource targets. Capability 1 supports only explicitly
registered EC2 instance ARN targets.

Target membership is identity-bearing Environment content. Equal target values
collapse through set semantics, and target ordering does not affect Environment
identity or hashing. Changing target membership creates a distinct Environment
registration.

An Environment represents only those registered EC2 instances. Only exact
registered target members are eligible future destruction targets. Tags and
retirement-time discovery cannot alter target membership. Empty target sets are
not approved for this execution capability.

Attached volumes, security groups, load balancers, stacks, tags, and inferred
related resources are excluded.

Latch validates the structural EC2 instance ARN form only. It does not call AWS,
verify that an instance exists, normalize ARNs, infer resource types, discover
targets, use tags, invoke AWS, persist targets, expose registration APIs, execute
destruction, confirm termination, retry, compensate, guarantee idempotency, or
orchestrate retirement in this boundary.

AWS invocation, termination confirmation, broader resource-type support,
registration workflows, destruction, retries, compensation, idempotency, and
orchestration remain deferred.
