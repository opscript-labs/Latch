# Retirement Admission Verdict

Retirement Admission Verdict is an immutable artifact derived from exactly one
Retirement Lock Participation.

It reuses the existing closed Admission Verdict vocabulary:

- SAFE
- UNSAFE
- INSUFFICIENT

The deterministic mapping is:

- PERMIT_FURTHER_ADMISSION maps to SAFE.
- BLOCK_FURTHER_ADMISSION maps to UNSAFE.
- FURTHER_ADMISSION_UNRESOLVED maps to INSUFFICIENT.

SAFE means all currently approved Capability 1 prerequisites have passed:
operational readiness, TTL timing, mandatory owner approval, and absence of a
supplied lock.

UNSAFE means at least one approved prerequisite is known not to be satisfied, or
a supplied lock prohibits retirement.

INSUFFICIENT means no approved prerequisite is known to block retirement, but one
or more required conditions remain unresolved.

SAFE makes no global lock-collection or evidence-completeness claim. This
artifact does not perform retirement execution, generate Bedrock explanations,
collect provider data, expose APIs, persist decisions, serialize public schemas,
integrate with AWS, add Terraform resources, or introduce new verdict values.
