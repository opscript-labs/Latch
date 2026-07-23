resource "aws_lambda_function" "retirement_admission" {
  function_name = var.lambda_function_name
  role          = aws_iam_role.lambda_exec.arn
  handler       = "latch.infrastructure.retirement_admission_lambda_entrypoint.handle_event"
  runtime       = "python3.13"
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_size

  filename         = "${path.module}/../../dist/retirement_admission_lambda.zip"
  source_code_hash = fileexists("${path.module}/../../dist/retirement_admission_lambda.zip") ? filebase64sha256("${path.module}/../../dist/retirement_admission_lambda.zip") : null

  environment {
    variables = {
      LATCH_DYNAMODB_REGION           = var.aws_region
      LATCH_ACTIVE_REGISTRATION_TABLE = var.active_registration_table_name
    }
  }
}
