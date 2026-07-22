# Owner Retirement Approval

Owner Retirement Approval is an immutable declared-approval artifact for one
Admission Evaluation Context.

It contains exactly:

- one Admission Evaluation Context;
- one non-empty `approved_by` owner identifier.

Construction is valid only when `approved_by` exactly matches the Context
Environment's recorded owner. The artifact represents the declared approval of
that recorded owner for that specific Context.

Identity consists exclusively of the Admission Evaluation Context. `approved_by`
is required asserted content, but it is not independently identity-bearing.

This artifact does not establish authentication, admission participation, whether
approval is required, validity over time, expiry, revocation, override behavior,
an Admission verdict, retirement authorization, or execution authority.

Approval-status evaluation, optional approval handling, owner directories,
authentication, signatures, workflows, APIs, persistence, serialization, AWS
integration, Terraform resources, dependencies, registries, plugins, and generic
authorization abstractions remain deferred.
