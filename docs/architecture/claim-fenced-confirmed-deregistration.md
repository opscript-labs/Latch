# Claim-Fenced Confirmed Deregistration

Status: Accepted

Claim-fenced confirmed deregistration removes an active registration only after an existing
`EC2DestructionConfirmation` reports `DESTRUCTION_CONFIRMED` for the exact Environment in a
`RetirementEvaluationClaim`.

The final active-claim validation is a read-only safety fence. It prevents a known-invalid claim
from reaching the deregistration transaction, but it is not atomic with DynamoDB deletion.

The atomic DynamoDB transaction provides the stale-claim protection. The active-registration delete
condition requires exact correspondence on Environment identifier, immutable registration
fingerprint, active claim token, and active claim time. Identifier plus fingerprint is not
sufficient. Target-ownership reservation deletes remain in the same transaction and retain their
exact owning Environment and immutable fingerprint conditions.

`DESTRUCTION_NOT_CONFIRMED` performs no active-claim validation and no mutation. A confirmation for
a different Environment also performs no validation and no mutation. Conditional transaction failure
propagates unchanged and removes nothing.

Successful completion means only that the exact Environment is no longer actively registered in
Latch. This boundary does not add retries, recovery, claim release, claim reassignment, history,
event publication, APIs, polling, compensation, Terraform, IAM, or workflow orchestration.
