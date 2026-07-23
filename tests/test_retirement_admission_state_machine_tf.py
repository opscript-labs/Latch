import os


def test_terraform_defines_exactly_one_sfn_state_machine() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tf_path = os.path.join(repo_root, "infrastructure", "terraform", "step_functions.tf")
    assert os.path.exists(tf_path)

    with open(tf_path) as f:
        content = f.read()

    assert 'resource "aws_sfn_state_machine"' in content
    assert 'type     = "STANDARD"' in content
    assert "templatefile(" in content
    assert "retirement_admission.asl.json" in content


def test_terraform_sfn_iam_policy_permissions() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tf_path = os.path.join(repo_root, "infrastructure", "terraform", "step_functions.tf")

    with open(tf_path) as f:
        content = f.read()

    assert "states.amazonaws.com" in content
    assert "lambda:InvokeFunction" in content
    assert "Resource = aws_lambda_function.retirement_admission.arn" in content


def test_terraform_outputs_are_present() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outputs_path = os.path.join(repo_root, "infrastructure", "terraform", "outputs.tf")
    
    with open(outputs_path) as f:
        content = f.read()

    assert "retirement_admission_state_machine_name" in content
    assert "retirement_admission_state_machine_arn" in content
    assert "retirement_admission_state_machine_role_arn" in content
