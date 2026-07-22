# Environment Resource Target Boundary

An Environment registration contains an explicit immutable unordered set of
represented infrastructure resource targets.

Target membership is identity-bearing Environment content. Equal target values
collapse through set semantics, and target ordering does not affect Environment
identity or hashing. Changing target membership creates a distinct Environment
registration.

Only exact registered target members are eligible future destruction targets.
Tags and retirement-time discovery cannot alter target membership. Empty target
sets are not approved for this execution capability.

Latch does not validate ARN syntax, normalize ARNs, infer resource types,
discover targets, use tags, invoke AWS, persist targets, expose registration
APIs, execute destruction, confirm destruction, retry, compensate, guarantee
idempotency, or orchestrate retirement in this boundary.

ARN syntax, normalization, resource-type support, registration workflows,
destruction, confirmation, retries, compensation, idempotency, and orchestration
remain deferred.
