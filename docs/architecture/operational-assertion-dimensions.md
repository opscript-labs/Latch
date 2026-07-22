# Operational Assertion Dimensions

Operational assertion dimensions are a closed vocabulary:

- CPU_ACTIVITY
- NETWORK_ACTIVITY
- DEPLOYMENT_ACTIVITY

A dimension is represented as a separate immutable association between one established
operational outcome and one approved dimension. Association identity is exactly the
established outcome and the dimension.

An established outcome may have no dimension association, one association, or multiple
associations. Multiple dimensions are represented as separate associations and are
never collapsed into a synthetic combined dimension.

Unsupported assertions receive no dimension association. There is no unsupported
dimension value, filter, evaluator, or automatic mapping in this slice.

Temporal comparison, compatibility, conflict handling, source-standing changes,
sufficiency, weighting, freshness, verdicts, retirement behavior, provider mappings,
APIs, persistence, AWS integration, Terraform resources, dependencies, serialization,
registries, plugins, and generic association frameworks remain deferred.
