# CloudWatch CPU Inactivity Collection

Accepted.

The CloudWatch CPU inactivity collector is a concrete per-target collector. It
accepts one `RetirementEvaluationClaim` and one EC2 target ARN that is an exact
member of the claimed Environment registration. It never processes multiple
targets and never creates Environment-wide or aggregate output.

The collector uses the existing ECS task-role credential boundary and creates
one regional CloudWatch client in the target ARN Region. It queries exactly one
`AWS/EC2` `CPUUtilization` `Average` metric for the target `InstanceId` with a
300-second period.

The claim time is the evaluation time. The observation end is the latest UTC
five-minute boundary at or before the claim time. The observation start is 30
minutes before that end. CloudWatch is requested for the six complete periods in
`[observation_start, observation_end)`. Returned timestamps must map exactly to
the six UTC period starts: `observation_start + n * 5 minutes` for `n = 0..5`.
The observation end is exclusive for CloudWatch period completeness.

A successful CloudWatch response is affirmative only when exactly one metric
result is returned, its status is `Complete`, no pagination token remains, it
contains exactly six timestamp/value pairs, every required period-start
timestamp appears exactly once with no outside timestamp, every value is finite
numeric, and every value is strictly below `1.0`.

Any other successful response is non-affirmative and yields no Evidence. A
request-level AWS SDK failure is a collection failure and propagates; it is not
converted into missing or non-qualifying Evidence.

Affirmative output is limited to canonical Evidence and one
`OPERATIONAL_INACTIVITY` Evidence classification association. The collector does
not create dimension associations, relevance results, assertion projections,
standing or establishment results, readiness, verdicts, execution artifacts, or
Environment-wide outputs.

Network collection for other metrics, retries, polling, workflow orchestration,
persistence, APIs, Terraform, downstream assertion, establishment, dimension
behavior, admission behavior, and execution behavior remain deferred.
