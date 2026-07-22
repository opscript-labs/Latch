# Retirement Lock Participation

Retirement Lock is an immutable artifact scoped to one registered Environment. It
represents that retirement of the Environment is locked. Its identity consists
only of that Environment.

Retirement Lock Participation is an immutable result derived from one Owner
Approval Participation and an optional Retirement Lock. When a lock is present,
it must concern the Owner Approval Participation Context's Environment.

The existing participation outcomes are reused:

- PERMIT_FURTHER_ADMISSION
- BLOCK_FURTHER_ADMISSION
- FURTHER_ADMISSION_UNRESOLVED

The deterministic mapping is:

- Lock present with any owner-approval outcome blocks further admission.
- Lock absent with PERMIT_FURTHER_ADMISSION permits further admission.
- Lock absent with FURTHER_ADMISSION_UNRESOLVED remains unresolved.
- Lock absent with BLOCK_FURTHER_ADMISSION blocks further admission.

A present lock takes precedence. Lock absence means only that no lock was
supplied; it does not claim global lock completeness. Inputs and upstream
artifacts are preserved unchanged.

This artifact does not model lock creation, release, expiry, authority,
overrides, approval changes, APIs, persistence, serialization, AWS integration,
Terraform resources, dependencies, registries, plugins, generic authorization
abstractions, Admission verdicts, or retirement execution authority.
