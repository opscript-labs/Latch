# Post-Invocation EC2 Destruction Confirmation

Status: Accepted

Post-invocation EC2 destruction confirmation is a narrow infrastructure coordinator for one
`RetirementEvaluationClaim` and one existing `EC2TerminationInvocation`.

The invocation must trace to the claim's exact immutable Environment. Its authorization path must
also trace to an `AdmissionEvaluationContext` containing that Environment, the RETIREMENT request,
and `evaluated_at` equal to the claim time. Any trace mismatch returns no confirmation result and
does not construct or call the EC2 confirmation adapter.

After successful trace validation, both existing invocation outcomes are eligible for one
confirmation read:

- `EC2_TERMINATION_REQUEST_ACCEPTED`
- `EC2_TERMINATION_REQUEST_NOT_ACCEPTED`

The coordinator calls the existing EC2 destruction-confirmation adapter exactly once and returns
the adapter's existing `EC2DestructionConfirmation`. A confirmation-request failure propagates
unchanged.

`DESTRUCTION_NOT_CONFIRMED` means only that this one read did not observe complete destruction.
`DESTRUCTION_CONFIRMED` means only that every exact registered EC2 target was explicitly reported
as `terminated`; it does not deregister the Environment.

This coordinator does not revalidate claim state, retry, poll, persist state, compensate, deregister
an Environment, coordinate execution state, alter APIs, Terraform, or IAM, or introduce a workflow
abstraction.
