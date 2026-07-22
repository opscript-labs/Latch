# Evidence Boundary

Evidence is a governed engineering proposition derived from one or more operational
observations and suitable for product reasoning.

Latch reasons about Evidence, not directly about provider observations. Operational
observations belong to external systems; Evidence belongs to Latch's product domain.

Evidence is not raw provider observations, telemetry, logs, events, API responses,
provider resource descriptions, conclusions, verdicts, explanations, recommendations,
thresholds, rules, or algorithms.

Evidence sits between operational observation and later product conclusions.

The current internal domain artifact embodies Evidence using four approved semantic
propositions: proposition, referent, source provenance, and temporal context.
Canonical external representation remains deferred.

Source provenance is structured as exactly one source system and one source
occurrence. Both are required, identity-bearing Evidence content. Source provenance
does not add authentication, credentials, ingestion behavior, provider adapters,
serialization, or source metadata.

Canonical Evidence temporal context is closed to exactly one of: an INSTANT with one
timezone-aware instant, an INTERVAL with closed bounded timezone-aware `[start, end]`
values, or an explicit TIMELESS condition. Accepted datetimes are normalized to UTC.
Interval start must be earlier than or equal to interval end.

Canonical Evidence equality is exact over only the four identity-bearing contents:
proposition, referent, source provenance, and temporal context. Proposition and
referent equality require exact string content; similar wording or differently
expressed references are distinct. Source provenance equality requires both source
system and source occurrence to match. Temporal-context equality requires the same
temporal form and normalized value. Equivalent timezone-aware instants normalize to
equal UTC instants. Closed intervals permit equal bounds; different bounds are
distinct.

TIMELESS is an explicit condition. It is distinct from `None`, empty data, an unknown
timestamp, or any other absence of temporal knowledge.

Evidence has no non-identity-bearing canonical content. Changing proposition,
referent, source provenance, or temporal context creates distinct Evidence. Evidence
is immutable; updates are represented by replacement with a new Evidence artifact,
not mutation.

Authority, authentication, credentials, ingestion, freshness, TTL, staleness,
sufficiency, conflicts, verdict semantics, evaluation, and provider mappings remain
deferred.
