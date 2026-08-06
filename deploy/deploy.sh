#!/bin/bash
# Deploy script executed ON the EC2 instance via SSM Run Command
# (AWS-RunShellScript). Expects this file and docker-compose.prod.yml to be
# present in /opt/vehicle-sales-service (the CD workflow puts them there).
#
# Usage: deploy.sh <full-image-ref>
#   e.g. deploy.sh <account>.dkr.ecr.<region>.amazonaws.com/vehicle-sales-service:<sha>
#
# Contract with cd.yml: this file lives at /opt/vehicle-sales-service/deploy.sh
# on the instance and takes the FULL ECR image ref (registry/repo:sha) as $1.
#
# Security notes (items 6/7 of the plan):
# - .env is materialized here from SSM Parameter Store (non-secret config)
#   using the instance profile — values are NEVER passed through SendCommand
#   parameters and NEVER echoed (no set -x).
# - The three SECRETS (DATABASE_PASSWORD, INTERNAL_API_TOKEN,
#   PAYMENT_WEBHOOK_TOKEN) never touch disk: they are exported into this
#   shell and picked up by the valueless `environment:` entries in
#   docker-compose.prod.yml (see step 2).
# - ECR login uses the instance role (get-login-password piped straight to
#   docker login) — no registry credentials via SSM parameters or SendCommand
#   (resolves security item 6).
# - Seed NEVER runs in production: docker-compose.prod.yml has migrations +
#   app only.
set -euo pipefail

APP_IMAGE="${1:?usage: deploy.sh <full-image-ref>}"
APP_DIR="/opt/vehicle-sales-service"
SSM_PREFIX="/vehicle-sales-service"
# Docker Compose plugin pin — MUST stay in sync with infra/stack/user_data.sh.
# That script installs the plugin, but user_data only runs on the instance's
# FIRST boot: an instance created before it existed (or before it was fixed)
# never gets the plugin, and `docker compose -f ...` then fails with
# "unknown shorthand flag: 'f' in -f". Step 0 below repairs that in place.
COMPOSE_VERSION="v2.32.4"
COMPOSE_RELEASE_URL="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}"
# Non-secret config written to .env. DATABASE_PASSWORD, INTERNAL_API_TOKEN and
# PAYMENT_WEBHOOK_TOKEN are deliberately ABSENT here — see step 2.
ENV_KEYS=(
  DATABASE_HOST
  DATABASE_PORT
  DATABASE_USER
  DATABASE_NAME
  CORE_SERVICE_BASE_URL
  CORE_SERVICE_TIMEOUT_SECONDS
  SERVICE_NAME
  DEBUG
  LOG_LEVEL
)

# Dump container state and recent output to stderr so the CD job's
# StandardErrorContent tail explains WHY a deploy failed. Used on both failure
# paths (compose up and health check). Never fails the script itself — it only
# runs when something has already gone wrong. Prints app output only; no env.
dump_diagnostics() {
  docker compose -f docker-compose.prod.yml ps >&2 || true
  docker compose -f docker-compose.prod.yml logs --tail=100 >&2 || true
}

cd "$APP_DIR"

# 0. Preflight — runs BEFORE any secret is materialized so a broken host
#    fails fast, and BEFORE `umask 077` so the installed plugin stays 0755.
#    The script runs as root via SSM Run Command.
if ! systemctl is-active --quiet docker; then
  echo "[deploy] docker daemon inactive — starting it"
  systemctl start docker || true
fi
if ! docker info >/dev/null 2>&1; then
  echo "[deploy] ERROR: docker daemon is not usable (is docker installed?)" >&2
  exit 1
fi

# 0b. Ensure the compose plugin exists (idempotent: the fast path is a single
#     local exec, nothing is downloaded on a healthy instance). Mirrors
#     infra/stack/user_data.sh, including the checksum verification against
#     the official checksums.txt of the SAME pinned release (security L6).
if docker compose version >/dev/null 2>&1; then
  echo "[deploy] docker compose plugin present"
else
  echo "[deploy] docker compose plugin missing — installing $COMPOSE_VERSION"
  mkdir -p /usr/local/lib/docker/cli-plugins
  workdir="$(mktemp -d)"
  curl -fsSL "${COMPOSE_RELEASE_URL}/docker-compose-linux-x86_64" \
    -o "${workdir}/docker-compose-linux-x86_64"
  curl -fsSL "${COMPOSE_RELEASE_URL}/checksums.txt" -o "${workdir}/checksums.txt"
  # Docker publishes checksums.txt in sha256sum BINARY mode ("<hash> *<file>"),
  # so the asset line is matched as a FIXED string including the leading " *".
  # The empty-match guard matters: piping an empty match into `sha256sum -c -`
  # fails with the misleading "no properly formatted SHA256 checksum lines
  # found", which points at sha256sum instead of at this pattern.
  checksum_line="$(grep -F ' *docker-compose-linux-x86_64' "${workdir}/checksums.txt" || true)"
  if [ -z "${checksum_line}" ]; then
    echo "ERROR: docker-compose-linux-x86_64 is not listed in checksums.txt for compose ${COMPOSE_VERSION}" >&2
    echo "       (${COMPOSE_RELEASE_URL}/checksums.txt) — refusing to install an unverified binary" >&2
    exit 1
  fi
  (cd "${workdir}" && printf '%s\n' "${checksum_line}" | sha256sum -c -)
  mv "${workdir}/docker-compose-linux-x86_64" /usr/local/lib/docker/cli-plugins/docker-compose
  rm -rf "${workdir}"
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  docker compose version
fi

# 1. Materialize .env from SSM (decrypted via instance profile). Region is
#    auto-detected by the AWS CLI through IMDSv2.
echo "[deploy] materializing .env from SSM ($SSM_PREFIX/*)"
umask 077
# Never leave a partially-written secrets file behind if a get-parameter /
# get-secret-value call aborts the script mid-loop.
trap 'rm -f "$APP_DIR/.env.tmp"' EXIT
: >.env.tmp
for key in "${ENV_KEYS[@]}"; do
  value="$(aws ssm get-parameter --name "$SSM_PREFIX/$key" \
    --with-decryption --query 'Parameter.Value' --output text)"
  printf '%s=%s\n' "$key" "$value" >>.env.tmp
done

# 2. SECRETS — passed through the PROCESS ENVIRONMENT, never written to .env.
#    Compose interpolates env_file values, so a `$` or `{` in the
#    RDS-generated password would be silently truncated (`aB3$xY9` -> `aB3`)
#    or abort the deploy with `Invalid template`. Exporting them instead
#    involves no dotenv parsing and no template interpolation on any Compose
#    version; docker-compose.prod.yml declares them with the valueless list
#    form so the daemon copies them verbatim from this shell.
#    Bonus: no secret is ever persisted to disk.
#
# 2a. DATABASE_PASSWORD from the RDS-managed Secrets Manager secret
#     (secret ARN published by Terraform as an SSM parameter).
secret_arn="$(aws ssm get-parameter --name "$SSM_PREFIX/DATABASE_PASSWORD_SECRET_ARN" \
  --query 'Parameter.Value' --output text)"
DATABASE_PASSWORD="$(aws secretsmanager get-secret-value --secret-id "$secret_arn" \
  --query 'SecretString' --output text |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["password"])')"
export DATABASE_PASSWORD

# 2b. INTERNAL_API_TOKEN from SSM (SecureString), same rationale as 2a.
INTERNAL_API_TOKEN="$(aws ssm get-parameter --name "$SSM_PREFIX/INTERNAL_API_TOKEN" \
  --with-decryption --query 'Parameter.Value' --output text)"
export INTERNAL_API_TOKEN

# 2c. PAYMENT_WEBHOOK_TOKEN from SSM (SecureString), same rationale as 2a.
#     It MUST take this path and not .env: alembic/env.py calls
#     get_settings() at import time and the token is a required field with no
#     default, so the migrations container dies with a pydantic
#     ValidationError before it ever reaches the database if the value is
#     missing — and putting it in .env would expose it to Compose's
#     interpolation of env_file values.
PAYMENT_WEBHOOK_TOKEN="$(aws ssm get-parameter --name "$SSM_PREFIX/PAYMENT_WEBHOOK_TOKEN" \
  --with-decryption --query 'Parameter.Value' --output text)"
export PAYMENT_WEBHOOK_TOKEN

# 2d. Guard: refuse to deploy if any parameter is still the CHANGE_ME
#     placeholder (would silently break the service). Covers the keys in
#     .env AND the three pass-through secrets. Only KEY names are printed —
#     never values.
placeholder_keys="$(grep -E '=CHANGE_ME$' .env.tmp | cut -d= -f1 || true)"
if [ "$DATABASE_PASSWORD" = "CHANGE_ME" ]; then
  placeholder_keys="$placeholder_keys DATABASE_PASSWORD"
fi
if [ "$INTERNAL_API_TOKEN" = "CHANGE_ME" ]; then
  placeholder_keys="$placeholder_keys INTERNAL_API_TOKEN"
fi
if [ "$PAYMENT_WEBHOOK_TOKEN" = "CHANGE_ME" ]; then
  placeholder_keys="$placeholder_keys PAYMENT_WEBHOOK_TOKEN"
fi
if [ -n "${placeholder_keys//[[:space:]]/}" ]; then
  echo "[deploy] ERROR: SSM parameter(s) still set to the CHANGE_ME placeholder:" >&2
  echo "$placeholder_keys" >&2
  echo "[deploy] set real values out-of-band (aws ssm put-parameter --overwrite, see infra/README.md)" >&2
  rm -f .env.tmp
  exit 1
fi
mv -f .env.tmp .env

# 3. ECR login via instance role, pull the requested image and roll the
#    stack (migrations -> app, per compose depends_on; NO seed in production).
registry="${APP_IMAGE%%/*}"
echo "[deploy] logging in to ECR ($registry)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"
echo "[deploy] pulling $APP_IMAGE"
docker pull "$APP_IMAGE"
export APP_IMAGE

# 3b. Last gate before starting: a pass-through secret that resolved to an
#     empty string would reach the container as "" and surface as an opaque
#     pydantic ValidationError instead of a deploy failure. Names only.
for secret_key in DATABASE_PASSWORD INTERNAL_API_TOKEN PAYMENT_WEBHOOK_TOKEN; do
  if [ -z "${!secret_key}" ]; then
    echo "[deploy] ERROR: $secret_key resolved to an empty value — refusing to start" >&2
    exit 1
  fi
done

# `up` exits non-zero if a dependency (migrations) fails, and set -e would
# otherwise abort here with only compose's progress lines on stderr — the
# container's own error would never be shown.
if ! docker compose -f docker-compose.prod.yml up -d --remove-orphans; then
  echo "[deploy] ERROR: compose up failed" >&2
  dump_diagnostics
  exit 1
fi

# 4. Health check — fail the SSM command (and the CD job) if not healthy.
echo "[deploy] waiting for /health"
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null --max-time 3 "http://localhost:8000/health"; then
    echo "[deploy] healthy — deploy OK ($APP_IMAGE)"
    # Reclaim disk on the small root volume: every deploy pulls a new
    # SHA-tagged image. Dangling layers ONLY — never `-a`, which would drop
    # the previous tagged image still needed for a quick rollback.
    docker image prune -f || echo "[deploy] warning: image prune failed" >&2
    exit 0
  fi
  sleep 3
done

echo "[deploy] ERROR: service did not become healthy" >&2
dump_diagnostics
exit 1
