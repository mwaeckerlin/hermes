#!/bin/bash -e
echo "==== Setting SSH Authorized Key ===="
key="${HERMES_SANDBOX_SSH_PUBLIC_KEY:-$(</run/secrets/hermes_sandbox_ssh_public_key)}"
if [ -z "$key" ]; then
  echo "ERROR: No SSH public key provided for sandbox. Please set HERMES_SANDBOX_SSH_PUBLIC_KEY variable or provide a secret named hermes_sandbox_ssh_public_key." >&2
  exit 1
fi
[ -d ${RUN_HOME}/.ssh ] || mkdir -p ${RUN_HOME}/.ssh
echo "$key" > ${RUN_HOME}/.ssh/authorized_keys
echo "==== Installing Skills ===="
# Pre-populate ~/.hermes/skills/ so the Hermes SSH backend finds them on first connect.
# Hermes also syncs skills from the gateway to this directory automatically.
mkdir -p "${RUN_HOME}/.hermes/skills"
for source_file in /opt/hermes/skills/*/SKILL.md; do
  [ -f "$source_file" ] || continue
  skill_name="$(basename "$(dirname "$source_file")")"
  install -D -m 644 -o "${RUN_USER}" -g "${RUN_GROUP}" \
    "$source_file" "${RUN_HOME}/.hermes/skills/${skill_name}/SKILL.md"
done
if [ -n "${DOCKER_HOST}" ]; then
  echo "==== Enabling Docker Host ===="
  echo "DOCKER_HOST=${DOCKER_HOST}" >> /etc/environment
fi
chown -R ${RUN_USER}:${RUN_GROUP} ${RUN_HOME}
chmod 755 ${RUN_HOME}
chmod 700 ${RUN_HOME}/.ssh
chmod 600 ${RUN_HOME}/.ssh/authorized_keys
echo "==== Starting SSH Daemon ===="
exec /usr/sbin/sshd -D -e
