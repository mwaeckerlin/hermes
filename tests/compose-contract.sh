#!/usr/bin/env bash
# Compose contract: the deployment wiring the stack promises.
#
#   - the compose file renders
#   - only mwaeckerlin images are deployed (base-image policy; the foreign
#     root-daemon docker:dind was replaced by rootless dockindock)
#   - the dind service is mwaeckerlin/dockindock, its TCP port matches the
#     sandbox's DOCKER_HOST, and storage sits on the real data path
#   - exactly the dind service is privileged, nothing else
#
# Usage: tests/compose-contract.sh

set -uo pipefail
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
declare -a FAILED_NAMES

_pass() { PASS=$((PASS + 1)); echo "  PASS  $1"; }
_fail() { FAIL=$((FAIL + 1)); FAILED_NAMES+=("$1"); echo "  FAIL  $1: $2"; }

echo "==> Compose contract: hermes stack wiring"

if ! CONFIG=$(docker compose config 2>/dev/null); then
    _fail "compose_renders" "docker compose config failed"
else
    _pass "compose_renders"

    FOREIGN=$(echo "${CONFIG}" | grep -E '^\s+image: ' | grep -v 'mwaeckerlin/')
    if [[ -z "${FOREIGN}" ]]; then
        _pass "only_mwaeckerlin_images"
    else
        _fail "only_mwaeckerlin_images" "foreign deployment images: ${FOREIGN}"
    fi

    if echo "${CONFIG}" | grep -q 'image: mwaeckerlin/dockindock'; then
        _pass "dind_is_rootless_dockindock"
    else
        _fail "dind_is_rootless_dockindock" "dind service does not use mwaeckerlin/dockindock"
    fi

    if echo "${CONFIG}" | grep -q 'DOCKER_HOST: tcp://hermes-dind:2375' \
        && echo "${CONFIG}" | grep -q 'DOCKER_TCP_PORT: "2375"'; then
        _pass "docker_host_port_wired"
    else
        _fail "docker_host_port_wired" "sandbox DOCKER_HOST and dind DOCKER_TCP_PORT do not match"
    fi

    if echo "${CONFIG}" | grep -q 'target: /docker-data'; then
        _pass "dind_volume_on_data_root"
    else
        _fail "dind_volume_on_data_root" "dind volume not mounted on /docker-data"
    fi

    PRIV=$(echo "${CONFIG}" | grep -c 'privileged: true')
    if [[ "${PRIV}" == "1" ]]; then
        _pass "only_dind_privileged"
    else
        _fail "only_dind_privileged" "expected exactly 1 privileged service, found ${PRIV}"
    fi

    if grep -q 'FROM mwaeckerlin/sandbox-base' Dockerfile.sandbox; then
        _pass "sandbox_from_shared_base"
    else
        _fail "sandbox_from_shared_base" "Dockerfile.sandbox does not build on mwaeckerlin/sandbox-base"
    fi

    if grep -q 'COPY --from=mcp_github_skills' Dockerfile.sandbox \
        && grep -q 'ADD files/SKILL.md' Dockerfile.sandbox; then
        _pass "skills_copied"
    else
        _fail "skills_copied" "skills not installed into the sandbox"
    fi

    # OpenCode in the sandbox reaches its gateway, which alone holds the keys
    OPENCODE=$(docker compose config --format json | python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
sandbox, gateway = services["hermes-sandbox"], services.get("hermes-opencode-gateway", {})
shared = set(sandbox.get("networks") or {}) & set(gateway.get("networks") or {})
keys = [k for k in (sandbox.get("environment") or {}) if "KEY" in k and "SSH" not in k]
print(sandbox["environment"].get("OPENCODE_GATEWAY_URL"), gateway.get("image"), ",".join(sorted(shared)), ",".join(keys) or "-")')
    if [[ "${OPENCODE}" == "http://hermes-opencode-gateway:8080 mwaeckerlin/opencode:gateway sandbox-opencode-gateway -" ]]; then
        _pass "local_opencode_through_its_gateway"
    else
        _fail "local_opencode_through_its_gateway" "gateway URL, gateway image, shared network, keys in the sandbox: ${OPENCODE}"
    fi

    if ! grep -q 'mwaeckerlin/opencode:sandbox' Dockerfile.sandbox; then
        _pass "opencode_from_sandbox_base"
    else
        _fail "opencode_from_sandbox_base" "Dockerfile.sandbox still takes OpenCode from mwaeckerlin/opencode:sandbox"
    fi

    if echo "${CONFIG}" | grep -q 'mwaeckerlin/allow-write-access'; then
        _pass "ownership_bootstrap_present"
    else
        _fail "ownership_bootstrap_present" "allow-write-access service missing"
    fi

    # mwaeckerlin/allow-write-access reads RUN_USER and RUN_GROUP and nothing else
    OWNER_ENV=$(docker compose config --format json | python3 -c '
import json, sys
env = json.load(sys.stdin)["services"]["allow-write-access"].get("environment") or {}
print(" ".join(f"{k}={v}" for k, v in sorted(env.items())))')
    if [[ "${OWNER_ENV}" == "RUN_GROUP=somebody RUN_USER=somebody" ]]; then
        _pass "ownership_bootstrap_user_read"
    else
        _fail "ownership_bootstrap_user_read" "allow-write-access environment is '${OWNER_ENV}', expected RUN_USER and RUN_GROUP only"
    fi

    if echo "${CONFIG}" | grep -q '9119'; then
        _pass "dashboard_port_published"
    else
        _fail "dashboard_port_published" "dashboard port 9119 not published"
    fi

    # the shared workflow publishes what `npm run deploy` pushes: every
    # service that builds an image must be named there, and nothing else
    BUILT=$(docker compose config --format json | python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
print(" ".join(sorted(n for n, s in services.items() if "build" in s and s.get("image"))))')
    DEPLOYED=$(python3 -c '
import json
words = json.load(open("package.json"))["scripts"].get("deploy", "").split()
print(" ".join(sorted(words[words.index("push") + 1:])) if words[:3] == ["docker", "compose", "push"] else "")')
    if [[ -n "${BUILT}" && "${BUILT}" == "${DEPLOYED}" ]]; then
        _pass "deploy_pushes_every_built_image"
    else
        _fail "deploy_pushes_every_built_image" "built: '${BUILT}', deploy pushes: '${DEPLOYED}'"
    fi

    if grep -q 'uses: mwaeckerlin/scratch/.github/workflows/docker-image.yml@master' .github/workflows/docker.yml \
        && grep -q 'secrets: inherit' .github/workflows/docker.yml; then
        _pass "workflow_calls_shared_build"
    else
        _fail "workflow_calls_shared_build" ".github/workflows/docker.yml does not call the shared docker-image workflow"
    fi
fi

echo ""
echo "==> Compose contract results: ${PASS} passed, ${FAIL} failed"
if [[ ${FAIL} -gt 0 ]]; then
    echo "==> Failed contracts: ${FAILED_NAMES[*]}"
    exit 1
fi
