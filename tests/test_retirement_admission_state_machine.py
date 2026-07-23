import json
from pathlib import Path


def load_asl() -> dict:
    asl_path = (
        Path(__file__).parent.parent
        / "infrastructure"
        / "terraform"
        / "retirement_admission.asl.json"
    )
    with open(asl_path) as f:
        return json.load(f)


def test_asl_is_valid_json_and_has_required_keys() -> None:
    asl = load_asl()
    assert isinstance(asl, dict)
    assert "StartAt" in asl
    assert "States" in asl
    assert asl["StartAt"] == "InvokeRetirementAdmissionLambda"


def test_asl_contains_only_expected_states() -> None:
    asl = load_asl()
    states = asl["States"]
    expected_states = {
        "InvokeRetirementAdmissionLambda",
        "EvaluateLambdaResult",
        "HandleExplicitError",
        "HandleInvocationFailure",
        "HandleMalformedResult",
        "TerminalSafe",
        "TerminalUnsafe",
        "TerminalInsufficient",
        "TerminalEvaluationRejected",
        "TerminalInvocationFailed",
    }
    assert set(states.keys()) == expected_states


def test_no_choice_state_has_safe_as_default() -> None:
    asl = load_asl()
    evaluate_state = asl["States"]["EvaluateLambdaResult"]
    assert evaluate_state["Type"] == "Choice"
    assert evaluate_state["Default"] != "TerminalSafe"
    assert evaluate_state["Default"] == "HandleMalformedResult"


def test_lambda_invocation_task_resource() -> None:
    asl = load_asl()
    invoke_state = asl["States"]["InvokeRetirementAdmissionLambda"]
    assert invoke_state["Type"] == "Task"
    assert invoke_state["Resource"] == "${RetirementAdmissionLambdaArn}"


def test_choice_state_routes_correctly_to_terminals() -> None:
    asl = load_asl()
    choices = asl["States"]["EvaluateLambdaResult"]["Choices"]

    # Locate choices based on transition target
    safe_choice = None
    unsafe_choice = None
    insufficient_choice = None
    rejected_choice = None
    explicit_error_choice = None

    for choice in choices:
        target = choice["Next"]
        if target == "TerminalSafe":
            safe_choice = choice
        elif target == "TerminalUnsafe":
            unsafe_choice = choice
        elif target == "TerminalInsufficient":
            insufficient_choice = choice
        elif target == "TerminalEvaluationRejected":
            rejected_choice = choice
        elif target == "HandleExplicitError":
            explicit_error_choice = choice

    # Validate safe choice condition
    assert safe_choice is not None
    conditions = safe_choice["And"]
    assert {"Variable": "$.verdict", "IsPresent": True} in conditions
    assert {"Variable": "$.verdict", "StringEquals": "safe"} in conditions

    # Validate unsafe choice condition
    assert unsafe_choice is not None
    conditions = unsafe_choice["And"]
    assert {"Variable": "$.verdict", "IsPresent": True} in conditions
    assert {"Variable": "$.verdict", "StringEquals": "unsafe"} in conditions

    # Validate insufficient choice condition
    assert insufficient_choice is not None
    conditions = insufficient_choice["And"]
    assert {"Variable": "$.verdict", "IsPresent": True} in conditions
    assert {"Variable": "$.verdict", "StringEquals": "insufficient"} in conditions

    # Validate rejected choice condition
    assert rejected_choice is not None
    conditions = rejected_choice["And"]
    assert {"Variable": "$.claim_token", "IsPresent": True} in conditions
    assert {"Variable": "$.verdict", "IsPresent": False} in conditions

    # Validate explicit error choice condition
    assert explicit_error_choice is not None
    conditions = explicit_error_choice["And"]
    assert {"Variable": "$.error", "IsPresent": True} in conditions


def test_every_state_routes_to_end_or_next_correctly() -> None:
    asl = load_asl()
    states = asl["States"]
    for state in states.values():
        if state.get("End") is True:
            continue
        if state["Type"] == "Choice":
            # Choice states transition to next states defined in choices or default
            targets = [c["Next"] for c in state["Choices"]] + [state["Default"]]
            for target in targets:
                assert target in states
        elif state["Type"] == "Fail":
            # Fail states are terminal
            continue
        else:
            assert "Next" in state
            assert state["Next"] in states


def test_no_destructive_or_external_actions_are_invoked() -> None:
    # Statically confirm that only the Lambda task is defined and no other API/resource is hit
    asl = load_asl()
    for name, state in asl["States"].items():
        if state["Type"] == "Task":
            assert state["Resource"] == "${RetirementAdmissionLambdaArn}"
            assert name == "InvokeRetirementAdmissionLambda"
