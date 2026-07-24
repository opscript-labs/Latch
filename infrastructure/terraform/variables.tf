variable "aws_region" {
  type        = string
  description = "The target AWS Region for resource deployment."
}

variable "lambda_function_name" {
  type        = string
  description = "The name of the retirement admission Lambda function."
  default     = "latch-retirement-admission"
}

variable "active_registration_table_name" {
  type        = string
  description = "The name of the pre-existing, externally supplied DynamoDB active registration table."
}

variable "active_registration_table_arn" {
  type        = string
  description = "The ARN of the pre-existing, externally supplied DynamoDB active registration table."
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "The timeout limit for the Lambda function."
  default     = 30
}

variable "lambda_memory_size" {
  type        = number
  description = "The memory allocation size for the Lambda function."
  default     = 256
}

variable "state_machine_name" {
  type        = string
  description = "The name of the Step Functions state machine."
  default     = "latch-retirement-admission-workflow"
}
