# PRODUCTION root — HCP Terraform (CLI-driven: remote execution + state).
# This is what .github/workflows/infra.yml runs.
#
# The `cloud` block does not accept Terraform variables; organization and
# workspace come from environment variables (set locally and in CI):
#
#   TF_CLOUD_ORGANIZATION = <your HCP Terraform organization>
#   TF_WORKSPACE          = vehicle-sales-infra
terraform {
  required_version = ">= 1.6.0"

  cloud {}
}

variable "github_org" {
  description = "GitHub organization/user that owns the vehicle-sales-service repository."
  type        = string
}

variable "github_owner_id" {
  description = "GitHub numeric immutable id of the owner, used in the OIDC `sub` claim. Defaults to this project's account; override only if the repository moves. See https://api.github.com/users/<owner>."
  type        = string
  default     = "93926603"
}

variable "github_repository_id" {
  description = "GitHub numeric immutable id of the vehicle-sales-service repository, used in the OIDC `sub` claim. REQUIRED — no default on purpose: a stale/borrowed id fails only at deploy time, as an opaque `Not authorized to perform sts:AssumeRoleWithWebIdentity`. Read the `id` field of https://api.github.com/repos/<owner>/vehicle-sales-service and set it as a workspace variable."
  type        = string
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type for the application host."
  type        = string
  default     = "t3.micro"
}

variable "create_github_oidc_provider" {
  description = "Create the account-wide GitHub OIDC provider instead of reading the one owned by vehicle-core-service. Keep false while Core exists in the same AWS account (AWS allows one provider per URL per account)."
  type        = bool
  default     = false
}

module "stack" {
  source = "../stack"

  github_org                  = var.github_org
  github_owner_id             = var.github_owner_id
  github_repository_id        = var.github_repository_id
  aws_region                  = var.aws_region
  instance_type               = var.instance_type
  create_github_oidc_provider = var.create_github_oidc_provider
}

output "instance_id" {
  description = "EC2 instance id of the application host."
  value       = module.stack.instance_id
}

output "elastic_ip" {
  description = "Public Elastic IP of the application host."
  value       = module.stack.elastic_ip
}

output "deploy_role_arn" {
  description = "ARN of the GitHub Actions OIDC deploy role (save as AWS_ROLE_ARN repo secret)."
  value       = module.stack.deploy_role_arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider trusted by the deploy role (owned by vehicle-core-service unless create_github_oidc_provider = true)."
  value       = module.stack.github_oidc_provider_arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository holding the app images."
  value       = module.stack.ecr_repository_url
}

output "db_endpoint" {
  description = "RDS PostgreSQL endpoint address."
  value       = module.stack.db_endpoint
}

output "db_port" {
  description = "RDS PostgreSQL port."
  value       = module.stack.db_port
}

output "db_master_secret_arn" {
  description = "ARN of the RDS-managed master password secret in Secrets Manager."
  value       = module.stack.db_master_secret_arn
}

output "ssm_parameter_prefix" {
  description = "SSM Parameter Store prefix holding the app runtime env."
  value       = module.stack.ssm_parameter_prefix
}
