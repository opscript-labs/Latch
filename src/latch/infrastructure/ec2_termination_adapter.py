from typing import Any

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from latch.domain.environment.environment import EC2_INSTANCE_ARN_PATTERN, Environment
from latch.domain.execution import (
    EC2TerminationInvocation,
    EC2TerminationInvocationResult,
    RetirementExecutionAuthorization,
    RetirementExecutionAuthorizationOutcome,
)
from latch.infrastructure.ecs_task_role_credentials import create_ecs_task_role_session


class EC2TerminationAdapter:
    def terminate(
        self,
        authorization: RetirementExecutionAuthorization,
    ) -> EC2TerminationInvocation:
        if (
            authorization.outcome
            is not RetirementExecutionAuthorizationOutcome.RETIREMENT_EXECUTION_AUTHORIZED
        ):
            raise ValueError("authorization must authorize retirement execution")

        environment = _environment_from_authorization(authorization)
        parsed_targets = _parse_environment_targets(environment)
        region = _single_value({target["region"] for target in parsed_targets})
        instance_ids_by_target = {
            target["arn"]: target["instance_id"] for target in parsed_targets
        }
        target_by_instance_id = {
            target["instance_id"]: target["arn"] for target in parsed_targets
        }

        session = create_ecs_task_role_session()
        ec2_client = session.client("ec2", region_name=region)

        try:
            response = ec2_client.terminate_instances(
                InstanceIds=list(instance_ids_by_target.values())
            )
        except (BotoCoreError, ClientError):
            return _not_accepted_for_all(authorization, environment.resource_target_arns)

        results = _results_from_response(
            response,
            instance_ids_by_target,
            target_by_instance_id,
        )
        return EC2TerminationInvocation(authorization, results)


def _environment_from_authorization(
    authorization: RetirementExecutionAuthorization,
) -> Environment:
    return (
        authorization.verdict.lock_participation.owner_approval_participation
        .prerequisite_status.readiness.association_set.context.environment
    )


def _parse_environment_targets(environment: Environment) -> tuple[dict[str, str], ...]:
    parsed_targets = []
    account_ids: set[str] = set()
    regions: set[str] = set()
    for target_arn in environment.resource_target_arns:
        match = EC2_INSTANCE_ARN_PATTERN.fullmatch(target_arn)
        if match is None:
            raise ValueError("registered targets must be valid EC2 instance ARNs")

        account_ids.add(match.group("account_id"))
        regions.add(match.group("region"))
        parsed_targets.append(
            {
                "arn": target_arn,
                "account_id": match.group("account_id"),
                "region": match.group("region"),
                "instance_id": match.group("instance_id"),
            }
        )

    _single_value(account_ids)
    _single_value(regions)
    return tuple(parsed_targets)


def _single_value(values: set[str]) -> str:
    if len(values) != 1:
        raise ValueError("registered targets must share one account and Region")

    return next(iter(values))


def _results_from_response(
    response: dict[str, Any],
    instance_ids_by_target: dict[str, str],
    target_by_instance_id: dict[str, str],
) -> tuple[EC2TerminationInvocationResult, ...]:
    terminating_instances = response.get("TerminatingInstances")
    if not isinstance(terminating_instances, list):
        return _not_accepted_results(instance_ids_by_target)

    seen_instance_ids: set[str] = set()
    accepted_targets: set[str] = set()
    malformed_response = False
    for entry in terminating_instances:
        if not isinstance(entry, dict):
            malformed_response = True
            continue

        instance_id = entry.get("InstanceId")
        if not isinstance(instance_id, str):
            malformed_response = True
            continue

        if instance_id in seen_instance_ids or instance_id not in target_by_instance_id:
            malformed_response = True
            continue

        seen_instance_ids.add(instance_id)
        accepted_targets.add(target_by_instance_id[instance_id])

    if malformed_response or seen_instance_ids != set(target_by_instance_id):
        return _not_accepted_results(instance_ids_by_target)

    return tuple(
        EC2TerminationInvocationResult(target_arn=target_arn, accepted=True)
        for target_arn in instance_ids_by_target
    )


def _not_accepted_for_all(
    authorization: RetirementExecutionAuthorization,
    target_arns: frozenset[str],
) -> EC2TerminationInvocation:
    return EC2TerminationInvocation(
        authorization,
        _not_accepted_results({target_arn: "" for target_arn in target_arns}),
    )


def _not_accepted_results(
    instance_ids_by_target: dict[str, str],
) -> tuple[EC2TerminationInvocationResult, ...]:
    return tuple(
        EC2TerminationInvocationResult(target_arn=target_arn, accepted=False)
        for target_arn in instance_ids_by_target
    )
