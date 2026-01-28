variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "service_role_arns" {
  description = "List of IAM role ARNs that can use the KMS keys"
  type        = list(string)
  default     = []
}
