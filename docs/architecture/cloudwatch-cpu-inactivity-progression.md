# CloudWatch CPU Inactivity Progression

Accepted.

CloudWatch CPU inactivity progression is a narrow per-target composition of
existing approved semantics. It accepts one `RetirementEvaluationClaim` and one
exact registered target ARN from the claim Environment.

The composition invokes the approved per-target CloudWatch CPU inactivity
collector. If collection produces no Evidence classification association, the
composition produces no dimension association. Request-level collection failures
propagate unchanged.

For affirmative collection, the composition constructs an
`AdmissionEvaluationContext` from the claim Environment, the sole retirement
request, and `evaluated_at` exactly equal to the claim time. It then applies the
existing relevance, operational assertion projection, source-standing, and
establishment behavior.

`CPU_ACTIVITY` attaches only to an established operational inactivity assertion.
The dimension association is not created directly from collected Evidence or
classification.

This composition produces no aggregate or Environment-wide evaluation
conclusion. Network and deployment collection, multi-target assembly, readiness,
conflicts, verdicts, authorization, retirement execution, persistence, APIs,
provider discovery, orchestration, retries, polling, Terraform, and new product
semantics remain deferred.
