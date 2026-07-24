variable "aws_region" {
  type        = string
  description = "The target AWS Region for local development resources."
  default     = "us-east-1"
}

variable "active_registration_table_name" {
  type        = string
  description = "The name of the development DynamoDB active registration table."
  default     = "latch-active-registrations-dev"
}
