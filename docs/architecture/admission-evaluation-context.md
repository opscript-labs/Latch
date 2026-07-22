# Admission Evaluation Context

An Admission Evaluation Context is an immutable request-scoped product artifact asking
whether one registered Environment may be retired from Latch as of one declared
evaluation time.

The context contains exactly one Environment, one requested retirement, and one
evaluation time. Its identity is exclusively the tuple of those three contents;
changing any one of them creates a distinct context.

Retirement is the only recognized admission request in this slice. Evaluation time is
preserved exactly as supplied and has no freshness, TTL, normalization, or temporal
relevance behavior here.

Evidence participation, Evidence eligibility, authority, sufficiency, conflicts,
verdict behavior, and admission evaluation remain deferred.
