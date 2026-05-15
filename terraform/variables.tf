variable "aws_region" {
  description = "AWS region for ECR and other resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
  default     = "development"
}
