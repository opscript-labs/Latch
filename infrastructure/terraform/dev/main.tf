provider "aws" {
  region = var.aws_region
}

resource "aws_dynamodb_table" "active_registration" {
  name         = var.active_registration_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "identifier"

  attribute {
    name = "identifier"
    type = "S"
  }

  tags = {
    Environment = "development"
    Project     = "Latch"
  }
}
