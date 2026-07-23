# Retirement Admission Coordination

Status: Accepted

The retirement admission coordinator is a narrow infrastructure composition boundary for one
`RetirementEvaluationClaim`.

It validates the active claim before any collection or retrieval work. An invalid active claim
returns no admission result and does not imply an admission verdict.

For a valid active claim, the coordinator uses the existing claim-scoped operational evidence
collection boundary. It reuses the exact `AdmissionEvaluationContext` traceable from the returned
`OperationalRetirementReadiness`. That Context must contain the claim Environment, the RETIREMENT
request, and `evaluated_at` equal to the claim time.

Timing remains mandatory. `RetirementPrerequisiteStatus` is derived from the returned readiness,
which derives `RetirementTimingEligibility` from the same Context. A timing-ineligible Context is
not satisfied through the existing prerequisite precedence, even when readiness is unresolved.

Durable owner approval and retirement lock state are retrieved through their existing
exact-registration boundaries. Collection failure, approval-retrieval failure, and lock-retrieval
failure propagate unchanged.

The coordinator returns exactly one `RetirementAdmissionVerdict` for a valid claim whose collection
and durable-state retrieval complete. It does not create execution authorization, perform a final
pre-action claim recheck, mutate persistence, retry, schedule work, orchestrate workflows, or invoke
infrastructure retirement.
