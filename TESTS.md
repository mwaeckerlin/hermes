# Tests

Register of all tests, grouped by kind and sorted by the [FEATURES.md](FEATURES.md) number each test covers. `npm test` runs everything after `npm run build`; the guard `tests/docs-contract.sh` fails when a feature has no test entry here, when a `SECURITY-WORKAROUND` has passed its review date, or when any test carries a skip marker — tests are never skipped.

The sandbox toolset and SSH behaviour are tested end to end in the [mwaeckerlin/sandbox-base] project (this stack consumes that image); the rootless docker-in-docker daemon is tested end to end in the [mwaeckerlin/dockindock] project.

## Backend API

`npm run test:python` runs these inside the built dashboard image (`test/docker-compose.yml`), on the plugin files and the config renderer as the dashboard and gateway images ship them, and on the pairing store of the hermes-agent version in the image.

- **F7** `tests/test_todo_api.py` — the TODO plugin API over HTTP: full review cycle, empty claim, forbidden transitions (400), unknown task (404), cancel and delete.
- **F9** `tests/test_pairing_api.py` — the pairing plugin API over HTTP: list with request id, approve by request id and by the reported code, unknown request and code refused, neither given (400), revoke.
- **F11** `tests/test_litellm_without_key.py` — the real `hermes -z` CLI, with only `LITELLM_BASE_URL` set and no key anywhere, sends its chat request to that endpoint; the endpoint records the request as the proxy would, and every request carries the fixed placeholder `Bearer no-key-required` or no header.

## Hindsight End to End

`npm run test:e2e` runs `tests/e2e/` with `tests/run-e2e.sh` in `test/docker-compose.yml`: a real Hindsight server with its mock LLM that demands a key, an nginx proxy that adds the key, and the test container built from the gateway image, which holds no key.

- **F10** `tests/run-e2e.sh` › gateway_memory_status: the gateway image, started through its real entrypoint with `HERMES_MEMORY_PROVIDER=hindsight`, writes `hindsight/config.json` from the environment, and `hermes memory status` reports the provider hindsight as installed and available, with no warning.
- **F10** `tests/e2e/test_hindsight_memory.py` › test_container_holds_no_hindsight_key, test_server_refuses_a_request_without_the_proxy: the key lives only in the proxy, and the server refuses a request that does not pass it.
- **F10** `tests/e2e/test_hindsight_memory.py` › test_retain_and_recall_through_the_proxy: hermes finds the plugin through its own provider lookup, the plugin offers its three tools, and a memory retained through the proxy is recalled.
- **F10** `tests/e2e/test_hindsight_memory.py` › test_shared_bank_is_an_mcp_server_of_hermes: `HINDSIGHT_SHARED_MCP_URL` becomes the MCP server `hindsight-shared` in hermes' own MCP configuration, and that endpoint answers the MCP handshake through the proxy.
- **F10** `tests/e2e_key/test_hindsight_key.py` › test_retain_and_recall_with_the_key_in_the_environment: with the Hindsight key held by the gateway as `HINDSIGHT_API_KEY` and no proxy, a memory is retained on and recalled from the real server, and `hindsight/config.json` does not carry the key.

## Isolation End to End

`npm run test:isolation` (`tests/run-isolation.sh`) runs the real gateway, sandbox and dashboard images of `test/docker-compose.yml`. The gateway holds a canary value in every secret variable it knows and a freshly generated SSH key; a skill in its skills directory asks for all of them and for the key and configuration files (`tests/isolation/probe_skill.py`); a scripted model (`tests/isolation/scripted_model.py`) drives the real agent to load that skill and to search the sandbox, and records everything the agent sees. `run-isolation.sh <image> '<terminal JSON>'` runs the same test against another gateway image or configuration: against 1.0.2 with `credential_files: [.ssh/hermes-sandbox]` it finds the gateway's private key in the sandbox and is red.

- **F12** `tests/run-isolation.sh` › sandbox_accepts_no_secret_variable: the sandbox's sshd (`sshd -T`) accepts no variable beyond `LANG`, `LC_*`, `COLORTERM` and `NO_COLOR`, so nothing hermes sends with `SendEnv` arrives.
- **F12** `tests/isolation/test_agent_sees_no_secret.py` › test_every_probe_step_ran: the probe skill was loaded and the search ran to its end, so the checks below are not empty.
- **F12** `tests/isolation/test_agent_sees_no_secret.py` › test_no_secret_reaches_the_agent: no canary and no line of the private key in anything the agent saw.
- **F12** `tests/isolation/test_agent_sees_no_secret.py` › test_no_private_key_in_the_sandbox: no file in the sandbox holds a canary or a line of the private key.
- **F11** `tests/isolation/test_agent_sees_no_secret.py` › test_gateway_uses_its_litellm_key: with `LITELLM_API_KEY` set, every chat request of the gateway carries it, while the agent never sees it.
- **F12** `tests/isolation/test_agent_sees_no_secret.py` › test_sandbox_cannot_reach_the_dashboard: the sandbox cannot connect to the dashboard.
- **F12** `tests/isolation/dashboard_check.py` › dashboard_requires_login, dashboard_shows_no_secret: the dashboard's key page refuses a request without login and, logged in, shows no secret of the gateway.
- **F2** `tests/isolation/dashboard_check.py` › dashboard_requires_login: the dashboard starts with the current hermes-agent and serves its pages behind the login.
- **F13** `tests/isolation/test_agent_sees_no_secret.py` › test_agent_is_told_never_to_ask_for_a_secret: the system prompt the agent works with carries the rule never to ask for a secret and to warn first when the user offers one.

## OpenCode Delegation

`npm run test:opencode` builds the sandbox image and runs `tests/opencode-delegation.sh` against it. The OpenCode server runs from the same image; its model is the recording OpenAI-compatible endpoint of `tests/openai-stub.cjs`, which answers `pong`.

- **F14** `tests/opencode-delegation.sh` › sandbox_has_opencode_client: the sandbox image carries the OpenCode client, `opencode-delegate` and the skill `opencode-delegation`.
- **F14** `tests/opencode-delegation.sh` › stalled_server_ends_the_wait: against a server that takes the connection and never answers, `opencode-delegate` gives up after `HERMES_OPENCODE_TIMEOUT` seconds with exit code 4 and a message that names the timeout.
- **F14** `tests/opencode-delegation.sh` › url_and_skill_reach_the_agent: the sandbox, started through its real entrypoint, writes `HERMES_OPENCODE_URL` and `HERMES_OPENCODE_TIMEOUT` into `/etc/environment` for the agent's SSH sessions and installs the skill into `~/.hermes/skills`.
- **F14** `tests/opencode-delegation.sh` › task_delegated_and_answered: `opencode-delegate` hands a task to the OpenCode server, prints the answer and the session id, and continues that session with a follow-up that reaches OpenCode's model.
- **F14** `tests/opencode-delegation.sh` › password_server_refuses_sandbox: a server with `OPENCODE_SERVER_PASSWORD` refuses the sandbox, which holds no password, with HTTP 401 and a clear message, and answers a client that has the password.

## Data Flow

- **F12** `tests/test_isolation_check.py`: the gateway's start check passes the default configuration and MCP servers reached by `url`, and refuses `terminal.env_passthrough`, `terminal.credential_files` and an MCP server with `command`.

- **F10** `tests/test_config_hindsight.py` — `memory.provider` from `HERMES_MEMORY_PROVIDER`, the shared bank as MCP server `hindsight-shared` beside the servers of `HERMES_MCP_SERVERS_YAML`, `hindsight/config.json` with `local_external` and `hybrid` by default and every `HINDSIGHT_*` setting from the environment, and never a key in it even when `HINDSIGHT_API_KEY` is set.
- **F11** `tests/test_config_hindsight.py` › test_litellm_base_url_alone_selects_litellm — `LITELLM_BASE_URL` alone sets the model endpoint.
- **F1** `tests/test_config_image_gen.py` — the gateway's config renderer omits, renders or replaces the `image_gen` section from the environment.
- **F7** `tests/test_todo_storage.py` — the TODO store: persistence, claim, role-bound transitions, delete rules.

## Compose Contract

- **F1** `tests/compose-contract.sh` › compose_renders, only_mwaeckerlin_images — the environment-driven stack renders and deploys only mwaeckerlin images.
- **F2** `tests/compose-contract.sh` › dashboard_port_published — the dashboard is reachable on its published port.
- **F3** `tests/compose-contract.sh` › sandbox_from_shared_base, only_dind_privileged — the sandbox builds on the shared base and runs unprivileged.
- **F3** `tests/compose-contract.sh` › skills_copied — the hermes skills are installed into the sandbox image.
- **F4** `tests/compose-contract.sh` › dind_is_rootless_dockindock, docker_host_port_wired, dind_volume_on_data_root — the sandbox's `DOCKER_HOST` matches the rootless dind service and its port, storage sits on the daemon's real data path.
- **F5** `tests/compose-contract.sh` › skills_copied — the GitHub MCP skill reaches the sandbox; the service URL is part of the rendered stack (compose_renders).
- **F6** `tests/compose-contract.sh` › ownership_bootstrap_present — the ownership bootstrap service is part of the stack.
- **F8** `tests/compose-contract.sh` › deploy_pushes_every_built_image, workflow_calls_shared_build — `npm run deploy` pushes exactly the images the compose file builds, and `.github/workflows/docker.yml` calls the shared workflow; the tag and architecture selection of that workflow is tested by `tests/workflow-contract.sh` of `mwaeckerlin/scratch`.

## Frontend Unit

- **F7** `files/todo-plugin/test/index.test.js` — the TODO plugin frontend registers, exposes only the user-owned transitions and updates its list without a reload.
- **F9** `files/pairing-plugin/test/index.test.js` — the pairing plugin frontend registers, approves a pending request by its request id, shows no code column, and revokes by platform and user id.

[mwaeckerlin/sandbox-base]: https://github.com/mwaeckerlin/sandbox-base
[mwaeckerlin/dockindock]: https://github.com/mwaeckerlin/dockindock
