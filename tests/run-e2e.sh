#!/usr/bin/env bash
# Hindsight memory end to end (test/docker-compose.yml):
#  1. the gateway image, started through its real entrypoint with
#     HERMES_MEMORY_PROVIDER=hindsight, reports the provider as installed and
#     available (`hermes memory status`)
#  2. the Hindsight server, the key-adding proxy and the hermes test container
#     run tests/e2e; the exit code of the test container is the result
#  3. the hermes test container holds the key itself (HINDSIGHT_API_KEY) and
#     runs tests/e2e_key against the server without the proxy
# The stack is removed in every case.
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f test/docker-compose.yml)
# the dashboard login of the first-start stack, for this run only
export ISOLATION_DASHBOARD_PASSWORD="e2e-dashboard-password-$$"
export ISOLATION_DASHBOARD_SECRET="e2e-dashboard-secret-$$-$RANDOM"
trap '"${COMPOSE[@]}" down --volumes --remove-orphans' EXIT

echo "==> gateway entrypoint: hermes memory status"
STATUS=$("${COMPOSE[@]}" run --rm gateway-memory-status 2>&1)
echo "${STATUS}"
for expected in "Hindsight: local_external at http://hindsight-proxy:8888, bank hermes-start, mode hybrid" \
                "Provider:  hindsight" "Plugin:    installed ✓" "Status:    available ✓"; do
    if ! grep -qF "${expected}" <<<"${STATUS}"; then
        echo "FAIL  gateway_memory_status: missing «${expected}»"
        exit 1
    fi
done
if grep -qi "warning" <<<"${STATUS}"; then
    echo "FAIL  gateway_memory_status: the gateway start printed a warning"
    exit 1
fi
echo "PASS  gateway_memory_status"

# waits until the gateway service $1 prints its start banner, exits, or the
# deadline in seconds ($2) passes; prints why it stopped waiting
_wait_gateway_start() {
    local service="$1" deadline=$((SECONDS + $2)) id state
    while [[ ${SECONDS} -lt ${deadline} ]]; do
        if "${COMPOSE[@]}" logs --no-color "${service}" 2>&1 | grep -qF "Hermes Gateway Starting"; then
            echo "started"
            return 0
        fi
        id=$("${COMPOSE[@]}" ps -aq "${service}")
        state=$(docker inspect --format '{{.State.Status}}' "${id}" 2>/dev/null)
        if [[ "${state}" == "exited" ]]; then
            echo "exited"
            return 1
        fi
        sleep 5
    done
    echo "deadline"
    return 1
}

# the first start on an empty volume with the dashboard on the same volume
# reaches the start banner and keeps running (regression: «Plugin 'hindsight'
# was not published: Plugin enablement changed while preparing the update;
# retry.» stopped the gateway, because the dashboard's init rewrote
# config.yaml during the install)
echo "==> first start on an empty volume shared with the dashboard"
"${COMPOSE[@]}" up -d first-start-gateway first-start-dashboard first-start-config-rewriter || exit 1
RESULT=$(_wait_gateway_start first-start-gateway 1800)
sleep 30
STATE=$(docker inspect --format '{{.State.Status}}' "$("${COMPOSE[@]}" ps -aq first-start-gateway)" 2>/dev/null)
REWRITTEN=$("${COMPOSE[@]}" logs --no-color first-start-config-rewriter 2>&1)
if [[ "${REWRITTEN}" != *"config.yaml rewritten while the dependency lock is held"* ]]; then
    echo "FAIL  first_start_with_dashboard_on_the_volume: config.yaml was not rewritten during the install: ${REWRITTEN}"
    exit 1
fi
if [[ "${RESULT}" == "started" && "${STATE}" == "running" ]]; then
    echo "PASS  first_start_with_dashboard_on_the_volume"
else
    echo "FAIL  first_start_with_dashboard_on_the_volume: ${RESULT}, ${STATE}"
    "${COMPOSE[@]}" logs --no-color --tail 40 first-start-gateway
    exit 1
fi
# the running gateway turns healthy from the HEALTHCHECK of the image, which
# Swarm acts on (regression: Swarm stopped the gateway again and again with
# «dockerexec: unhealthy container»)
GATEWAY_ID=$("${COMPOSE[@]}" ps -aq first-start-gateway)
HEALTH=""
DEADLINE=$((SECONDS + 400))
while [[ ${SECONDS} -lt ${DEADLINE} ]]; do
    HEALTH=$(docker inspect --format '{{.State.Health.Status}}' "${GATEWAY_ID}" 2>/dev/null)
    [[ "${HEALTH}" == "healthy" ]] && break
    sleep 10
done
if [[ "${HEALTH}" == "healthy" ]]; then
    echo "PASS  gateway_turns_healthy"
else
    echo "FAIL  gateway_turns_healthy: «${HEALTH}», last check: $(docker inspect --format '{{range .State.Health.Log}}{{.Output}}{{end}}' "${GATEWAY_ID}" 2>&1 | tail -n 3)"
    exit 1
fi

# the shared bank answers the MCP connect with the gateway's key (regression:
# the MCP entry went out without the bearer, Hindsight answered 401, and
# hermes fell back to SSE, which Hindsight does not speak there)
GATEWAY_LOG=$("${COMPOSE[@]}" logs --no-color first-start-gateway 2>&1)
if [[ "${GATEWAY_LOG}" != *"hindsight-shared"*"HTTP 401"* && "${GATEWAY_LOG}" != *"SSEError"* ]]; then
    echo "PASS  shared_bank_mcp_with_the_key"
else
    echo "FAIL  shared_bank_mcp_with_the_key: $(grep -i "hindsight-shared\|SSEError" <<<"${GATEWAY_LOG}" | tail -n 3)"
    exit 1
fi
"${COMPOSE[@]}" rm -sf first-start-gateway first-start-dashboard first-start-config-rewriter > /dev/null 2>&1

# a gateway stopped in the middle of its first install and started again on
# the half-written volume gets through, as a restart by Swarm must
echo "==> restart in the middle of the first install"
"${COMPOSE[@]}" up -d restart-gateway || exit 1
DEADLINE=$((SECONDS + 600))
until "${COMPOSE[@]}" logs --no-color restart-gateway 2>&1 | grep -qF "Installing the Hindsight memory provider" \
        || [[ ${SECONDS} -ge ${DEADLINE} ]]; do
    sleep 2
done
sleep 20
"${COMPOSE[@]}" kill restart-gateway > /dev/null 2>&1
"${COMPOSE[@]}" start restart-gateway > /dev/null 2>&1
RESULT=$(_wait_gateway_start restart-gateway 1800)
if [[ "${RESULT}" == "started" ]]; then
    echo "PASS  restart_during_first_install"
else
    echo "FAIL  restart_during_first_install: ${RESULT}"
    "${COMPOSE[@]}" logs --no-color --tail 40 restart-gateway
    exit 1
fi
# without a dashboard on the volume, whose init would write API_SERVER_KEY,
# the gateway creates the key of its API server itself and turns healthy
GATEWAY_ID=$("${COMPOSE[@]}" ps -aq restart-gateway)
HEALTH=""
DEADLINE=$((SECONDS + 400))
while [[ ${SECONDS} -lt ${DEADLINE} ]]; do
    HEALTH=$(docker inspect --format '{{.State.Health.Status}}' "${GATEWAY_ID}" 2>/dev/null)
    [[ "${HEALTH}" == "healthy" ]] && break
    sleep 10
done
if [[ "${HEALTH}" == "healthy" ]]; then
    echo "PASS  gateway_healthy_without_dashboard"
else
    echo "FAIL  gateway_healthy_without_dashboard: «${HEALTH}», last check: $(docker inspect --format '{{range .State.Health.Log}}{{.Output}}{{end}}' "${GATEWAY_ID}" 2>&1 | tail -n 3)"
    exit 1
fi
"${COMPOSE[@]}" rm -sf restart-gateway > /dev/null 2>&1

"${COMPOSE[@]}" up --build --abort-on-container-exit --exit-code-from hindsight-e2e \
    hindsight-e2e hindsight-proxy hindsight || exit 1

echo "==> Hindsight key held by the gateway"
"${COMPOSE[@]}" up -d hindsight || exit 1
"${COMPOSE[@]}" run --rm hindsight-e2e-key
