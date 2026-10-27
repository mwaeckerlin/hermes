#!/usr/bin/env bash
# Base path end to end (tests/base-path/docker-compose.yml): the built
# dashboard image without internet access, once below HERMES_BASE_PATH=/hermes
# behind Traefik with PathPrefix(`/hermes`) and without StripPrefix, once at
# the root; Chromium signs in and works in both, and every request of the page
# below the base path stays below it. A wrong HERMES_BASE_PATH stops the start.
#
# Usage: tests/run-base-path.sh   (after `npm run build`)

set -uo pipefail
cd "$(dirname "$0")/base-path"

# the dashboard's login, handed to it as Docker secrets for this run only
export BASE_PATH_DASHBOARD_PASSWORD="base-path-dashboard-password-$$"
export BASE_PATH_DASHBOARD_SECRET="base-path-dashboard-session-secret-$$"
COMPOSE=(docker compose -f docker-compose.yml)
FAIL=0

cleanup() { "${COMPOSE[@]}" down -v --remove-orphans > /dev/null 2>&1; }
trap cleanup EXIT
cleanup

echo "==> Dashboard below a base path"
"${COMPOSE[@]}" build proxy browser || exit 1
"${COMPOSE[@]}" up -d dashboard dashboard-root proxy || exit 1

# the whole log first: grep -q stops at the first line, the logs command then
# dies on a closed pipe, and pipefail would count the match as a failure
STARTED=""
for _ in $(seq 1 150); do
    LOG=$("${COMPOSE[@]}" logs dashboard 2>&1)
    if grep -q "hermes-dashboard: serving below /hermes/" <<< "${LOG}"; then
        STARTED=yes
        break
    fi
    sleep 2
done
if [[ -n "${STARTED}" ]]; then
    echo "  PASS  serves_below_the_base_path"
else
    echo "  FAIL  serves_below_the_base_path: the start did not report the base path"
    FAIL=1
fi

# inside the container, the dashboard answers at the root as before, for its
# own self-test and every client there, and below the base path as well
for path in /login /hermes/login; do
    STATUS=""
    for _ in $(seq 1 60); do
        STATUS=$("${COMPOSE[@]}" exec -T dashboard /opt/hermes/.venv/bin/python3 -c \
            "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9119${path}', timeout=5).status)" 2>&1)
        [[ "${STATUS}" == "200" ]] && break
        sleep 2
    done
    if [[ "${STATUS}" == "200" ]]; then
        echo "  PASS  served_inside_the_container_at_${path}"
    else
        echo "  FAIL  served_inside_the_container_at_${path}: ${STATUS}"
        FAIL=1
    fi
done

"${COMPOSE[@]}" run --rm browser pytest -v --tb=short -W error -p no:cacheprovider test_base_path.py test_root.py || FAIL=1

# a wrong value stops the start with a message that names the variable
for value in "hermes" "/a b" "/x/../y"; do
    OUTPUT=$(timeout 300 "${COMPOSE[@]}" run --rm --no-deps -e "HERMES_BASE_PATH=${value}" dashboard-root 2>&1)
    CODE=$?
    if [[ ${CODE} -ne 0 && ${CODE} -ne 124 ]] && grep -q "configuration error: HERMES_BASE_PATH is" <<< "${OUTPUT}"; then
        echo "  PASS  wrong_base_path_stops_the_start: '${value}'"
    else
        echo "  FAIL  wrong_base_path_stops_the_start: '${value}' ended with code ${CODE}:"
        tail -n 40 <<< "${OUTPUT}"
        FAIL=1
    fi
done

if [[ ${FAIL} -ne 0 ]]; then
    "${COMPOSE[@]}" logs --tail 120 dashboard dashboard-root proxy
    exit 1
fi
echo "==> Dashboard below a base path: green"
