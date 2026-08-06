# LOCAL TEST root — same stack pointed at the Floci emulator
# (floci/floci:latest, port 4566). Local backend, dummy credentials,
# throwaway state. Run through ./floci-validate.sh, never against real AWS.
terraform {
  required_version = ">= 1.6.0"
}

module "stack" {
  source = "../stack"

  aws_region       = "us-east-1"
  github_org       = "floci-local"
  aws_endpoint_url = "http://localhost:4566"

  # Unused here (enable_github_oidc = false switches off everything that
  # reads it), but the stack variable has no default on purpose — see
  # infra/stack/variables.tf.
  github_repository_id = "0"

  # Floci gap: it implements neither CreateOpenIDConnectProvider NOR
  # GetOpenIDConnectProvider, so the OIDC provider resource, the data source
  # that reads the shared provider, and the deploy role are ALL skipped
  # locally. Production (infra/main) keeps the default (true); the stack
  # itself is otherwise UNMODIFIED between environments.
  enable_github_oidc = false
}
