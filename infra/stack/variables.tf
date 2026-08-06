variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "github_org" {
  description = "GitHub organization/user that owns the vehicle-sales-service repository. Used to pin the OIDC trust policy (no wildcards)."
  type        = string
}

variable "github_owner_id" {
  description = <<-EOT
    GitHub numeric immutable identifier of the owner (user/org), used in the OIDC `sub` claim
    (form `repo:<owner>@<owner_id>/<repo>@<repo_id>:ref:...`). ACCOUNT-SPECIFIC: the default is the
    id of this project's GitHub account. Find it at https://api.github.com/users/<owner>, field `id`.
  EOT
  type        = string
  default     = "93926603"
}

variable "github_repository_id" {
  description = <<-EOT
    GitHub numeric immutable identifier of the vehicle-sales-service repository, used in the OIDC
    `sub` claim (form `repo:<owner>@<owner_id>/<repo>@<repo_id>:ref:...`). REPOSITORY-SPECIFIC: the
    default below is THIS repository's id, read from
    https://api.github.com/repos/<owner>/vehicle-sales-service (field `id`). Override only if the
    repository is recreated or moved — the id is immutable across renames, which is the whole point
    of the claim format. A WRONG id fails only at deploy time, as an opaque
    `Not authorized to perform sts:AssumeRoleWithWebIdentity` with nothing wrong in the logs, so
    never copy this value from another service's stack.
  EOT
  type        = string
  default     = "1319407629"
}

variable "instance_type" {
  description = "EC2 instance type for the application host."
  type        = string
  default     = "t3.micro"
}

variable "create_github_oidc_provider" {
  description = <<-EOT
    Create the account-wide GitHub OIDC provider (`token.actions.githubusercontent.com`).
    DEFAULT false: AWS allows only ONE provider per URL per account and vehicle-core-service
    already owns it. This stack looks it up with a data source instead.
  EOT
  type        = bool
  default     = false
}

variable "enable_github_oidc" {
  description = <<-EOT
    Create the GitHub Actions deploy role (and read or create the OIDC provider it trusts).
    Set to false ONLY in the Floci local root: the emulator supports neither
    CreateOpenIDConnectProvider nor GetOpenIDConnectProvider, so both the resource and the data
    source must be counted out there.
  EOT
  type        = bool
  default     = true
}

variable "aws_endpoint_url" {
  description = "Custom AWS API endpoint (Floci local emulator, e.g. http://localhost:4566). Leave null for real AWS."
  type        = string
  default     = null
}
