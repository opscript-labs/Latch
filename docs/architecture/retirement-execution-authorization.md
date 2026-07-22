# Retirement Execution Authorization

Retirement Execution Authorization is an immutable execution-domain artifact
derived from exactly one Retirement Admission Verdict.

The closed outcome vocabulary is:

- RETIREMENT_EXECUTION_AUTHORIZED
- RETIREMENT_EXECUTION_REFUSED_UNSAFE
- RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT

The deterministic mapping is:

- SAFE maps to RETIREMENT_EXECUTION_AUTHORIZED.
- UNSAFE maps to RETIREMENT_EXECUTION_REFUSED_UNSAFE.
- INSUFFICIENT maps to RETIREMENT_EXECUTION_REFUSED_INSUFFICIENT.

Authorization permits only the retirement action already requested by the
Admission Evaluation Context. It is a Latch product authorization, not proof of
external authority.

This artifact does not discover targets, authenticate externally, invoke
infrastructure, begin workflows, enqueue work, retry, compensate, execute
retirement, expose APIs, persist decisions, serialize public schemas, integrate
with AWS, add Terraform resources, dependencies, registries, plugins, or generic
execution abstractions.
