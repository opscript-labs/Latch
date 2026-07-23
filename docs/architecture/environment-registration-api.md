# Environment Registration API

`POST /environments` creates only an active immutable Environment registration.
It accepts the approved Environment content and constructs the existing
Environment domain artifact directly.

The control plane uses DynamoDB as the active-registration store and ECS
task-role credentials as the only credential source. Startup validates required
configuration:

- `LATCH_DYNAMODB_REGION`
- `LATCH_ACTIVE_REGISTRATION_TABLE`
- approved ECS task-role credential source configuration

Startup composes a regional DynamoDB client and the existing active-registration
adapter, but it does not probe DynamoDB, make a DynamoDB request, retry, or
require a live AWS service.

DynamoDB failures are request-time responses. Duplicate conditional registration
failures return `409`; DynamoDB SDK, service, or transport persistence failures
return `503` without exposing AWS exception details.

A successful response means only that the immutable Environment was actively
registered. The endpoint does not authenticate callers, evaluate admission,
schedule TTL work, invoke EC2, retire an Environment, replace registrations,
update registrations, read registrations, paginate, emit events, orchestrate
workflows, configure Terraform, or define IAM policies.
