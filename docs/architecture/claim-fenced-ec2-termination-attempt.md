# Claim-Fenced EC2 Termination Attempt

Status: Accepted

The claim-fenced EC2 termination attempt is a narrow infrastructure coordinator for one
`RetirementEvaluationClaim` and one existing `RetirementAdmissionVerdict`.

Before deriving execution authorization, the verdict must trace to an
`AdmissionEvaluationContext` containing exactly the claim Environment, the RETIREMENT request, and
`evaluated_at` equal to the claim time. A trace mismatch is invalid input and produces no
authorization, no active-claim validation, and no EC2 adapter call.

The coordinator derives the existing `RetirementExecutionAuthorization` solely from the supplied
verdict. Refusal authorizations for UNSAFE or INSUFFICIENT verdicts are returned unchanged and do
not reach the active-claim validator or EC2 termination adapter.

Only an authorized retirement execution performs one final read-only active-claim validation. An
invalid active claim returns no invocation result. A valid active claim invokes the existing EC2
termination adapter at most once within that coordinator invocation and returns the adapter's
existing `EC2TerminationInvocation`.

The final claim validation is a safety fence, not atomic claim-to-AWS coordination. The coordinator
does not claim global exactly-once behavior across repeated calls. It does not retry, poll, confirm
destruction, persist state, compensate, deregister an Environment, alter Terraform or IAM, or add a
workflow abstraction.
