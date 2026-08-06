#!/bin/bash
# Bootstrap for the vehicle-sales-service host (Amazon Linux 2023).
# Installs docker + compose plugin and prepares the app directory.
# The deploy itself (image pull, .env materialization from SSM, compose up,
# health check) is done by deploy/deploy.sh via SSM Run Command.
set -euxo pipefail

COMPOSE_VERSION="v2.32.4"
COMPOSE_RELEASE_URL="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}"

dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

# Download pinned compose binary and verify it against the official
# checksums.txt of the SAME pinned release (security item L6 — rejects a
# corrupted/tampered binary before it is ever installed).
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

mkdir -p /opt/vehicle-sales-service
chown ec2-user:ec2-user /opt/vehicle-sales-service
