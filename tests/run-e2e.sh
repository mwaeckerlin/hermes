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

"${COMPOSE[@]}" up --build --abort-on-container-exit --exit-code-from hindsight-e2e \
    hindsight-e2e hindsight-proxy hindsight || exit 1

echo "==> Hindsight key held by the gateway"
"${COMPOSE[@]}" up -d hindsight || exit 1
"${COMPOSE[@]}" run --rm hindsight-e2e-key
