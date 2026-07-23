resource "aws_iam_role" "sfn_exec" {
  name = "${var.state_machine_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "sfn_policy" {
  name        = "${var.state_machine_name}-policy"
  description = "IAM policy for Latch Retirement Admission Step Functions state machine"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.retirement_admission.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sfn_policy_attach" {
  role       = aws_iam_role.sfn_exec.name
  policy_arn = aws_iam_policy.sfn_policy.arn
}

resource "aws_sfn_state_machine" "retirement_admission" {
  name     = var.state_machine_name
  role_arn = aws_iam_role.sfn_exec.arn
  type     = "STANDARD"

  definition = templatefile(
    "${path.module}/retirement_admission.asl.json",
    {
      RetirementAdmissionLambdaArn = aws_lambda_function.retirement_admission.arn
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.sfn_policy_attach
  ]
}
