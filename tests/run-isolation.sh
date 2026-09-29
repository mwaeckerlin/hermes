#!/usr/bin/env bash
# Isolation end to end (test/docker-compose.yml, services isolation-*): the
# real gateway, holding a canary value in every secret variable it knows and a
# freshly generated SSH key, drives the real sandbox through a scripted model
# (tests/isolation/scripted_model.py); tests/isolation then reads what the
# model recorded and fails on any secret the agent could see.
# Usage: run-isolation.sh [gateway image] [terminal section as JSON]
#   the image defaults to mwaeckerlin/hermes:gateway; the terminal section
#   replaces the rendered one (HERMES_TERMINAL_YAML), to try a configuration
#   that hands files or variables to the sandbox
set -uo pipefail
cd "$(dirname "$0")/.."
export ISOLATION_GATEWAY_IMAGE="${1:-mwaeckerlin/hermes:gateway}"
export ISOLATION_TERMINAL_YAML="${2:-}"
echo "==> isolation of ${ISOLATION_GATEWAY_IMAGE} ${ISOLATION_TERMINAL_YAML:+with terminal ${ISOLATION_TERMINAL_YAML}}"

COMPOSE=(docker compose -f test/docker-compose.yml)
trap '"${COMPOSE[@]}" logs --no-color isolation-model isolation-dashboard isolation-sandbox | tail -n 80; "${COMPOSE[@]}" down --volumes --remove-orphans' EXIT

# hermes-test: the test image built from the gateway image, with tests/
"${COMPOSE[@]}" build python-tests || exit 1

# a key pair for this run only, made with the gateway image's ssh-keygen
KEYS=$("${COMPOSE[@]}" run --rm --no-deps --entrypoint /bin/sh isolation-gateway -c \
    'ssh-keygen -q -t ed25519 -N "" -C isolation-test -f /tmp/k && cat /tmp/k.pub && echo ==== && cat /tmp/k') || exit 1
export PROBE_PUBLIC_KEY=$(sed -n '1p' <<<"${KEYS}")
PRIVATE=$(sed '1,/^====$/d' <<<"${KEYS}")
export PROBE_PRIVATE_KEY=$(sed -z 's/\n/\\n/g' <<<"${PRIVATE}")
export PROBE_KEY_MARKER=$(sed -n '2p' <<<"${PRIVATE}" | cut -c1-40)

# fresh volumes belong to root; hermes runs as uid 10000, as the
# allow-write-access service of docker-compose.yml arranges in production
"${COMPOSE[@]}" run --rm --no-deps --entrypoint /bin/sh -v hermes-test_isolation-records:/records \
    isolation-gateway -c 'chown -R 10000:10000 /opt/data /records' || exit 1

# a skill in the gateway that asks for every secret, as a hostile skill from
# any source would
"${COMPOSE[@]}" run --rm --no-deps -v hermes-test_isolation-data:/opt/data \
    --entrypoint /opt/hermes/.venv/bin/python3 isolation-model \
    tests/isolation/probe_skill.py /opt/data/skills/isolation-probe/SKILL.md || exit 1

"${COMPOSE[@]}" up -d isolation-model isolation-sandbox isolation-dashboard || exit 1

# hermes sends passthrough variables with ssh SendEnv; the sandbox's sshd
# drops every name it does not AcceptEnv, whatever the gateway asks for
ACCEPTED=$("${COMPOSE[@]}" exec -T isolation-sandbox sshd -T | grep -i '^acceptenv ' | cut -d' ' -f2- | tr '\n' ' ')
echo "==> sandbox sshd AcceptEnv: ${ACCEPTED:-(none)}"
for name in ${ACCEPTED}; do
    case "${name}" in
        LANG|LC_\*|LANGUAGE|COLORTERM|NO_COLOR) ;;
        *) echo "FAIL  sandbox_accepts_no_secret_variable: sshd accepts ${name}"; exit 1 ;;
    esac
done
echo "PASS  sandbox_accepts_no_secret_variable"
"${COMPOSE[@]}" run --rm isolation-gateway
GATEWAY=$?
echo "==> gateway exit code ${GATEWAY}"

"${COMPOSE[@]}" run --rm isolation-check || exit 1

# the dashboard shares the data volume with the gateway: its key page needs
# a login and, logged in, shows no secret of the gateway
"${COMPOSE[@]}" exec -T isolation-dashboard /opt/hermes/.venv/bin/python3 - \
    isolation-admin isolation-dashboard-password hermes-canary "${PROBE_KEY_MARKER}" \
    < tests/isolation/dashboard_check.py
