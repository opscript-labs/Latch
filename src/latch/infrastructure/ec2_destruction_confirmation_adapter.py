from typing import Any

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from latch.domain.environment.environment import EC2_INSTANCE_ARN_PATTERN, Environment
from latch.domain.execution import EC2DestructionConfirmation, EC2InstanceLifecycleState
from latch.infrastructure.ecs_task_role_credentials import create_ecs_task_role_session


class EC2DestructionConfirmationAdapter:
    def confirm(self, environment: Environment) -> EC2DestructionConfirmation:
        if not isinstance(environment, Environment):
            raise ValueError("environment must be an Environment")

        parsed_targets = _parse_environment_targets(environment)
        region = _single_value({target["region"] for target in parsed_targets})
        instance_ids_by_target = {target["arn"]: target["instance_id"] for target in parsed_targets}
        target_by_instance_id = {target["instance_id"]: target["arn"] for target in parsed_targets}

        session = create_ecs_task_role_session()
        ec2_client = session.client("ec2", region_name=region)

        try:
            response = ec2_client.describe_instances(
                InstanceIds=list(instance_ids_by_target.values())
            )
        except (BotoCoreError, ClientError):
            return EC2DestructionConfirmation(environment, [])

        reported_states = _states_from_response(response, target_by_instance_id)
        return EC2DestructionConfirmation(environment, reported_states)


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


def _states_from_response(
    response: dict[str, Any],
    target_by_instance_id: dict[str, str],
) -> tuple[EC2InstanceLifecycleState, ...]:
    reservations = response.get("Reservations")
    if not isinstance(reservations, list):
        return ()

    seen_instance_ids: set[str] = set()
    reported_states = []
    malformed_response = False
    for reservation in reservations:
        if not isinstance(reservation, dict):
            malformed_response = True
            continue

        instances = reservation.get("Instances")
        if not isinstance(instances, list):
            malformed_response = True
            continue

        for instance in instances:
            if not isinstance(instance, dict):
                malformed_response = True
                continue

            instance_id = instance.get("InstanceId")
            state = instance.get("State")
            if not isinstance(instance_id, str) or not isinstance(state, dict):
                malformed_response = True
                continue

            lifecycle_state = state.get("Name")
            if not isinstance(lifecycle_state, str):
                malformed_response = True
                continue

            if instance_id in seen_instance_ids or instance_id not in target_by_instance_id:
                malformed_response = True
                continue

            seen_instance_ids.add(instance_id)
            reported_states.append(
                EC2InstanceLifecycleState(
                    target_arn=target_by_instance_id[instance_id],
                    lifecycle_state=lifecycle_state,
                )
            )

    if malformed_response or seen_instance_ids != set(target_by_instance_id):
        return ()

    return tuple(reported_states)
