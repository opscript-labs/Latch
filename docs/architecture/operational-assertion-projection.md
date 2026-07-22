# Operational Assertion Projection

An Operational Assertion Projection is an immutable, context-bound projection from one
Evidence proposition classification association and one Admission Evaluation Context.

The closed outcome vocabulary is:

- ASSERTS_OPERATIONAL_ACTIVITY
- ASSERTS_OPERATIONAL_INACTIVITY
- NO_OPERATIONAL_ASSERTION

The deterministic mapping is:

- relevant Evidence classified as OPERATIONAL_ACTIVITY maps to
  ASSERTS_OPERATIONAL_ACTIVITY.
- relevant Evidence classified as OPERATIONAL_INACTIVITY maps to
  ASSERTS_OPERATIONAL_INACTIVITY.
- irrelevant Evidence maps to NO_OPERATIONAL_ASSERTION.
- UNCLASSIFIED Evidence maps to NO_OPERATIONAL_ASSERTION.

Projection identity is based only on the classification association and Admission
Evaluation Context. The outcome is derived from those inputs and does not independently
participate in identity.

Operational assertions are not facts, source authority, authenticity, reliability,
sufficiency, conflict resolution, verdicts, or retirement outcomes.

Source standing is closed to STANDING and NO_STANDING. Standing is determined only by
one `(source_system, proposition_classification)` pair. The approved standing pairs are:

- `aws.cloudwatch.metrics` with OPERATIONAL_INACTIVITY
- `aws.cloudtrail.event` with OPERATIONAL_ACTIVITY

Operational establishment is closed to ESTABLISHES_OPERATIONAL_ACTIVITY,
ESTABLISHES_OPERATIONAL_INACTIVITY, and ESTABLISHES_NOTHING. A relevant activity
assertion with STANDING establishes operational activity; a relevant inactivity
assertion with STANDING establishes operational inactivity; every other combination
establishes nothing.

Established remains limited to the approved source account establishing that one
operational proposition. It does not imply conflict resolution, sufficiency, or a
retirement verdict.

Authentication, credentials, ingestion, source ranking, aggregation, sufficiency,
conflict handling, verdicts, retirement execution, provider mappings, APIs,
persistence, AWS integration, Terraform resources, dependencies, and serialization
remain deferred.
