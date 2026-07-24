output "active_registration_table_name" {
  value       = aws_dynamodb_table.active_registration.name
  description = "The name of the provisioned development DynamoDB table."
}

output "aws_region" {
  value       = var.aws_region
  description = "The AWS region where the table is provisioned."
}
