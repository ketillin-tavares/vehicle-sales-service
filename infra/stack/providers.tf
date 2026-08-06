locals {
  # True when pointing at the Floci local emulator instead of real AWS.
  use_local_endpoint = var.aws_endpoint_url != null

  service_name = "vehicle-sales-service"

  # The OTHER service in the platform. Used only to deny this instance role
  # read access to that service's SSM tree (see main.tf).
  peer_service_name = "vehicle-core-service"

  # Applied account-wide via default_tags AND explicitly on every resource
  # that is the target of a tag-based (ABAC) IAM condition — default_tags
  # has a history of not propagating to some resource types (notably
  # aws_kms_key), which silently breaks those conditions.
  standard_tags = {
    Project   = "tech-challenge-4"
    Service   = local.service_name
    ManagedBy = "terraform"
  }
}

# Provider lives inside the module so the SAME stack runs against real AWS
# (infra/main) and Floci (infra/local) just by toggling aws_endpoint_url.
#
# Credentials: NEVER static keys.
# - HCP Terraform runs: dynamic provider credentials (TFC native OIDC to AWS)
#   injected via workspace env vars TFC_AWS_PROVIDER_AUTH / TFC_AWS_RUN_ROLE_ARN.
# - Floci runs: dummy credentials via AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY env vars.
provider "aws" {
  region = var.aws_region

  # Floci wiring — all of this is inert (null/false) against real AWS.
  skip_credentials_validation = local.use_local_endpoint
  skip_metadata_api_check     = local.use_local_endpoint
  skip_region_validation      = local.use_local_endpoint

  endpoints {
    ec2 = var.aws_endpoint_url
    ecr = var.aws_endpoint_url
    iam = var.aws_endpoint_url
    kms = var.aws_endpoint_url
    rds = var.aws_endpoint_url
    ssm = var.aws_endpoint_url
    sts = var.aws_endpoint_url
  }

  default_tags {
    tags = local.standard_tags
  }
}
