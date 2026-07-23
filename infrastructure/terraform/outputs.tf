output "lambda_function_name" {
  value       = aws_lambda_function.retirement_admission.function_name
  description = "The name of the Lambda function."
}

output "lambda_function_arn" {
  value       = aws_lambda_function.retirement_admission.arn
  description = "The ARN of the Lambda function."
}

output "lambda_invoke_arn" {
  value       = aws_lambda_function.retirement_admission.invoke_arn
  description = "The invocation ARN of the Lambda function."
}

output "lambda_role_arn" {
  value       = aws_iam_role.lambda_exec.arn
  description = "The ARN of the Lambda IAM execution role."
}

output "retirement_admission_state_machine_name" {
  value       = aws_sfn_state_machine.retirement_admission.name
  description = "The name of the Step Functions state machine."
}

output "retirement_admission_state_machine_arn" {
  value       = aws_sfn_state_machine.retirement_admission.arn
  description = "The ARN of the Step Functions state machine."
}

output "retirement_admission_state_machine_role_arn" {
  value       = aws_iam_role.sfn_exec.arn
  description = "The ARN of the Step Functions IAM execution role."
}
