#!/usr/bin/env bash
# Local validation of the Terraform stack against the Floci AWS emulator
# (floci/floci:latest, port 4566). Runs from the infra/local root.
#
# Usage:
#   ./floci-validate.sh          # fmt-check + init + validate + plan
#   ./floci-validate.sh --apply  # ... + FULL apply + state list + destroy
#
# Emulation notes (verified 2026-08):
# - Floci MUST run with the host docker socket mounted: it backs EC2
#   instances and RDS databases with real containers (amazonlinux/postgres).
#   Without the socket, EC2 goes pending->terminated and RDS errors out.
# - Neither CreateOpenIDConnectProvider nor GetOpenIDConnectProvider is
#   supported; the local root sets enable_github_oidc = false (the only
#   difference from production).
#   Everything else — EC2, SG, EIP, RDS (incl. managed master password in
#   Secrets Manager), ECR, IAM roles/profiles, SSM parameters — applies for
#   real against the emulator.
set -euo pipefail

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$LOCAL_DIR"

FLOCI_CONTAINER="floci-tf-validate"
STARTED_FLOCI=0
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

# Dummy credentials — Floci does not verify them.
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"

cleanup() {
  # Emulator state is ephemeral — never keep it around.
  rm -f terraform.tfstate terraform.tfstate.backup
  if [ "$STARTED_FLOCI" = "1" ]; then
    docker rm -f "$FLOCI_CONTAINER" >/dev/null 2>&1 || true
    echo "[floci-validate] stopped Floci container"
  fi
  # Best-effort: remove containers Floci spawned for EC2/RDS resources.
  leftovers="$(docker ps -aq --filter 'name=floci-ec2-' --filter 'name=floci-rds-' --filter 'name=floci-ecr-' 2>/dev/null || true)"
  if [ -n "$leftovers" ]; then
    # shellcheck disable=SC2086
    docker rm -f $leftovers >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# 1. fmt check on both roots and the shared module
terraform fmt -check -recursive ..

# 2. ensure Floci is up (docker socket mount is REQUIRED — see header)
if ! curl -s -o /dev/null --max-time 2 "http://localhost:4566"; then
  echo "[floci-validate] starting Floci (floci/floci:latest)..."
  MSYS_NO_PATHCONV=1 docker run -d --name "$FLOCI_CONTAINER" -p 4566:4566 \
    -v /var/run/docker.sock:/var/run/docker.sock floci/floci:latest >/dev/null
  STARTED_FLOCI=1
  for _ in $(seq 1 30); do
    curl -s -o /dev/null --max-time 2 "http://localhost:4566" && break
    sleep 1
  done
fi

# 3. init (local backend) + validate + plan
terraform init -input=false >/dev/null
terraform validate
terraform plan -input=false

if [ "$APPLY" = "1" ]; then
  terraform apply -input=false -auto-approve
  terraform state list
  terraform destroy -input=false -auto-approve
fi

echo "[floci-validate] OK"
