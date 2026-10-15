#!/bin/sh
# Docker secrets for the dashboard: every file in /run/secrets becomes the
# variable of its upper-cased name, the same rule as the gateway entrypoint:
# hermes_dashboard_basic_auth_password → HERMES_DASHBOARD_BASIC_AUTH_PASSWORD.
#
# s6 runs /etc/cont-init.d as root before the dashboard starts, and its
# with-contenv hands /run/s6/container_environment to the dashboard, the way
# the upstream stage2 hook passes AGENT_BROWSER_EXECUTABLE_PATH. So s6 stays
# PID 1, and the login never stands in the container's configuration, where
# `docker service inspect` would show it.
set -eu
[ -d /run/secrets ] || exit 0
umask 077
mkdir -p /run/s6/container_environment
for secret in /run/secrets/*; do
  [ -f "$secret" ] || continue
  varname=$(basename "$secret" | tr '[:lower:]-' '[:upper:]_')
  case "$varname" in
    [!A-Z_]*|*[!A-Z0-9_]*)
      echo "[secrets] skipping $secret: its name is no variable name" >&2
      continue
      ;;
  esac
  # the command substitution drops the trailing newline a secret file
  # usually ends with
  printf '%s' "$(cat "$secret")" > "/run/s6/container_environment/$varname"
  echo "[secrets] $varname from secret"
done
