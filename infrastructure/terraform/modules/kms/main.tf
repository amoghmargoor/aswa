# KMS key for ASWA data encryption

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "aswa_data" {
  description             = "ASWA data encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow service access"
        Effect = "Allow"
        Principal = {
          AWS = var.service_role_arns
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyWithoutPlaintext",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "aswa-data-encryption"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "aswa_data" {
  name          = "alias/aswa-data-${var.environment}"
  target_key_id = aws_kms_key.aswa_data.key_id
}

# RDS encryption key
resource "aws_kms_key" "rds" {
  description             = "ASWA RDS encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "aswa-rds-encryption"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/aswa-rds-${var.environment}"
  target_key_id = aws_kms_key.rds.key_id
}

# S3 encryption key
resource "aws_kms_key" "s3" {
  description             = "ASWA S3 encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "aswa-s3-encryption"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "s3" {
  name          = "alias/aswa-s3-${var.environment}"
  target_key_id = aws_kms_key.s3.key_id
}

output "data_key_id" {
  value = aws_kms_key.aswa_data.key_id
}

output "data_key_arn" {
  value = aws_kms_key.aswa_data.arn
}

output "rds_key_arn" {
  value = aws_kms_key.rds.arn
}

output "s3_key_arn" {
  value = aws_kms_key.s3.arn
}
