#!/bin/bash -e
echo "==== Setting SSH Authorized Key ===="
if [ -n "${HERMES_SANDBOX_SSH_PUBLIC_KEY:-}" ]; then
  key="${HERMES_SANDBOX_SSH_PUBLIC_KEY}"
elif [ -r /run/secrets/hermes_sandbox_ssh_public_key ]; then
  key="$(cat /run/secrets/hermes_sandbox_ssh_public_key)"
else
  key=""
fi
if [ -z "$key" ]; then
  echo "ERROR: No SSH public key provided for sandbox. Please set HERMES_SANDBOX_SSH_PUBLIC_KEY variable or provide a secret named hermes_sandbox_ssh_public_key." >&2
  exit 1
fi
[ -d "${RUN_HOME}/.ssh" ] || mkdir -p "${RUN_HOME}/.ssh"
echo "$key" > "${RUN_HOME}/.ssh/authorized_keys"
echo "==== Installing Skills ===="
# Pre-populate ~/.hermes/skills/ so the Hermes SSH backend finds them on first connect.
# Hermes also syncs skills from the gateway to this directory automatically.
mkdir -p "${RUN_HOME}/.hermes/skills"
for source_dir in /opt/hermes/skills/*; do
  [ -d "$source_dir" ] || continue
  skill_name="$(basename "$source_dir")"
  target_dir="${RUN_HOME}/.hermes/skills/${skill_name}"
  rm -rf "$target_dir"
  cp -a "$source_dir" "${RUN_HOME}/.hermes/skills/"
  chown -R "${RUN_USER}:${RUN_GROUP}" "$target_dir"
done
if [ -n "${DOCKER_HOST:-}" ]; then
  echo "==== Enabling Docker Host ===="
  echo "DOCKER_HOST=${DOCKER_HOST}" >> /etc/environment
fi
if [ -n "${MCP_GITHUB_URL:-}" ]; then
  echo "==== Setting MCP GitHub URL ===="
  echo "MCP_GITHUB_URL=${MCP_GITHUB_URL}" >> /etc/environment
fi
if [ -n "${MCP_GITEA_URL:-}" ]; then
  echo "==== Setting MCP Gitea URL ===="
  echo "MCP_GITEA_URL=${MCP_GITEA_URL}" >> /etc/environment
fi
chown -R "${RUN_USER}:${RUN_GROUP}" "${RUN_HOME}"
chmod 750 "${RUN_HOME}"
chmod 700 "${RUN_HOME}/.ssh"
chmod 600 "${RUN_HOME}/.ssh/authorized_keys"
echo "==== Starting SSH Daemon ===="
exec /usr/sbin/sshd -D -e
