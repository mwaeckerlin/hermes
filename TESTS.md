# Tests

Register of all tests, grouped by kind and sorted by the [FEATURES.md](FEATURES.md) number each test covers. `npm test` builds the three images with `npm run build` and then runs everything against them; the guard `tests/docs-contract.sh` fails when a feature has no test entry here, when a `SECURITY-WORKAROUND` has passed its review date, or when any test carries a skip marker — tests are never skipped.

The sandbox toolset and SSH behaviour are tested end to end in the [mwaeckerlin/sandbox-base] project (this stack consumes that image); the rootless docker-in-docker daemon is tested end to end in the [mwaeckerlin/dockindock] project.

## Backend API

`npm run test:python` runs these inside the test image built from the gateway image (`test/Dockerfile`, `test/docker-compose.yml`), on the plugin files and the config renderer as the dashboard and gateway images ship them, and on the pairing store of the hermes-agent version in the image.

- **F7** `tests/test_todo_api.py` — the TODO plugin API over HTTP: full review cycle, empty claim, forbidden transitions (400), unknown task (404), cancel and delete.
- **F9** `tests/test_pairing_api.py` — the pairing plugin API over HTTP: list with request id, approve by request id and by the reported code, unknown request and code refused, neither given (400), revoke.
- **F11** `tests/test_litellm_without_key.py` — the real `hermes -z` CLI, with only `LITELLM_BASE_URL` set and no key anywhere, sends its chat request to that endpoint; the endpoint records the request as the proxy would, and every request carries the fixed placeholder `Bearer no-key-required` or no header.

## Hindsight End to End

`npm run test:e2e` runs `tests/e2e/` with `tests/run-e2e.sh` in `test/docker-compose.yml`: a real Hindsight server with its mock LLM that demands a key, an nginx proxy that adds the key, and the test container built from the gateway image, which holds no key and carries the Hindsight plugin installed the way the gateway installs it on its first start.

- **F10** `tests/run-e2e.sh` › gateway_memory_status: the gateway image, started through its real entrypoint with `HERMES_MEMORY_PROVIDER=hindsight` on an empty data volume, installs the Hindsight plugin, writes `hindsight/config.json` from the environment, and `hermes memory status` reports the provider hindsight as installed and available, with no warning.
- **F10** `tests/run-e2e.sh` › first_start_with_dashboard_on_the_volume: the gateway starts on an empty data volume, the dashboard starts on the same volume once the gateway has started, as in `docker-compose.yml`, a helper on the volume changes `config.yaml` every 50ms for 10 seconds from the moment hermes takes the lock of the plugin's Python dependencies, as the dashboard's init did on CephFS where that sync took 20 minutes, and the test checks that it did, and the gateway reaches «Hermes Gateway Starting» and keeps running (regression: «Plugin 'hindsight' was not published: Plugin enablement changed while preparing the update; retry.» stopped the gateway, because the dashboard's init rewrote `config.yaml` during the install).
- **F10** `tests/run-e2e.sh` › gateway_turns_healthy: the gateway of the first start, with a real Hindsight that demands its tenant key and the key held by the gateway alone, as in the swarm, turns healthy from the HEALTHCHECK of the image (regression: the check asked `/healthz`, which the API server of hermes does not serve, and Swarm stopped the gateway as unhealthy).
- **F10** `tests/run-e2e.sh` › shared_bank_mcp_with_the_key: the MCP connect to the shared bank straight on Hindsight carries the gateway's key, and the log shows no 401 and no fallback to SSE (regression: the entry went out without the bearer).
- **F10** `tests/run-e2e.sh` › restart_during_first_install: on a volume that carries the links of `gateway.pid` and `gateway.lock` into `/tmp` made by the images up to 1.0.8, a gateway killed 20 seconds into its first install and started again on the half-written volume reaches «Hermes Gateway Starting».
- **F10** `tests/run-e2e.sh` › gateway_healthy_without_dashboard: without a dashboard on the volume, whose init would write `API_SERVER_KEY`, the gateway creates the key of its API server itself and turns healthy (regression: the current hermes refused the linked `gateway.lock` with «Too many levels of symbolic links» and the gateway exited with code 1 after its banner).
- **F10** `tests/run-e2e.sh` › links_of_1.0.8_replaced: the running gateway holds its lock in the file `gateway.lock` of the volume, and neither `gateway.lock` nor `gateway.pid` is a link any more.
- **F10** `tests/e2e/test_hindsight_memory.py` › test_container_holds_no_hindsight_key, test_server_refuses_a_request_without_the_proxy: the key lives only in the proxy, and the server refuses a request that does not pass it.
- **F10** `tests/e2e/test_hindsight_memory.py` › test_retain_and_recall_through_the_proxy: hermes finds the plugin through its own provider lookup, the plugin offers its three tools, and a memory retained through the proxy is recalled.
- **F10** `tests/e2e/test_hindsight_memory.py` › test_shared_bank_is_an_mcp_server_of_hermes: `HINDSIGHT_SHARED_MCP_URL` becomes the MCP server `hindsight-shared` in hermes' own MCP configuration, and that endpoint answers the MCP handshake through the proxy.
- **F10** `tests/e2e_key/test_hindsight_key.py` › test_retain_and_recall_with_the_key_in_the_environment: with the Hindsight key held by the gateway as `HINDSIGHT_API_KEY` and no proxy, a memory is retained on and recalled from the real server, and `hindsight/config.json` does not carry the key.

## Base Path End to End

`npm run test:base-path` runs `tests/run-base-path.sh` with `tests/base-path/docker-compose.yml` on a network without internet access: the built dashboard image with `HERMES_BASE_PATH=/hermes` behind Traefik with ``PathPrefix(`/hermes`)`` and without StripPrefix, the same image without the variable at the root, and Chromium (pytest-playwright) in a container of its own. The login comes as Docker secrets.

- **F16** `tests/run-base-path.sh` › serves_below_the_base_path: the dashboard reports at its start that it serves below `/hermes/`.
- **F16** `tests/run-base-path.sh` › served_inside_the_container_at_/login, served_inside_the_container_at_/hermes/login: inside the container the dashboard answers at the root, for its own self-test, and below the base path.
- **F16** `tests/run-base-path.sh` › wrong_base_path_stops_the_start: with `hermes`, `/a b` and `/x/../y` the dashboard container ends with an error code and the message `configuration error: HERMES_BASE_PATH is …`.
- **F16** `tests/base-path/browser/test_base_path.py` › test_bare_base_path_redirects_to_its_slash_form: `/hermes` and `/hermes?next=%2F` answer 308 to `/hermes/` with the query kept.
- **F16** `tests/base-path/browser/test_base_path.py` › test_nothing_outside_the_base_path_is_routed: the proxy routes nothing outside `/hermes`.
- **F16** `tests/base-path/browser/test_base_path.py` › test_login_redirect_stays_below_the_base_path: a page without login redirects to `/hermes/login`.
- **F16** `tests/base-path/browser/test_base_path.py` › test_login_page_posts_below_the_base_path: the login page posts and loads its fonts below `/hermes`.
- **F16** `tests/base-path/browser/test_base_path.py` › test_a_prefix_header_of_the_client_does_not_reach_the_dashboard: a client's `X-Forwarded-Prefix: /elsewhere` changes nothing on the page.
- **F16** `tests/base-path/browser/test_base_path.py` › test_the_page_names_its_assets_below_the_base_path: logged in, the page loads its assets from `/hermes/assets/` and carries the base path for the bundle.
- **F16** `tests/base-path/browser/test_base_path.py` › test_sign_in_opens_the_dashboard_below_the_base_path, test_assets_load_below_the_base_path, test_document_names_no_url_outside_the_base_path: Chromium signs in on the login page, the dashboard opens, every request of the page from the first address on stays below `/hermes`, the login and an API call answer 200, the scripts and stylesheets load, and the rendered document names no root-absolute URL outside `/hermes`.
- **F16** `tests/base-path/browser/test_base_path.py` › test_plugin_tab_adds_a_task_below_the_base_path: the deep link `/hermes/todo` opens the TODO tab from its plugin bundle below `/hermes`, and a task added with its button is saved through `/hermes/api/plugins/todo/add` and shown.
- **F16** `tests/base-path/browser/test_base_path.py` › test_navigation_between_tabs_stays_below_the_base_path: the link from the TODO tab to the Pairing tab leads to an address below `/hermes`, a reload there lands on the same address, and no request of the page leaves `/hermes`.
- **F16** `tests/base-path/browser/test_base_path.py` › test_websocket_opens_below_the_base_path: the websocket of the dashboard's events feed, addressed the way the bundle addresses it, opens below `/hermes`.
- **F16** `tests/base-path/browser/test_root.py` › test_login_redirect_at_the_root, test_the_page_names_its_assets_at_the_root, test_sign_in_opens_the_dashboard_at_the_root, test_plugin_tab_at_the_root: without the variable the same image redirects to `/login`, loads its assets from `/assets/`, signs in, opens the TODO tab, and no request and no URL of the page names `/hermes`.

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
- **F2** `tests/run-isolation.sh` › dashboard_login_not_in_environment: the dashboard gets its password and session secret as Docker secrets only, and its container configuration carries neither.
- **F2** `tests/isolation/dashboard_check.py` › dashboard_login_from_secret: the login with the password of the Docker secret `hermes_dashboard_basic_auth_password` succeeds.
- **F2** `tests/isolation/dashboard_check.py` › dashboard_session_survives_restart: the session cookie of a login still opens the key page after a restart of the dashboard, so the session was signed with the Docker secret `hermes_dashboard_basic_auth_secret`.
- **F13** `tests/isolation/test_agent_sees_no_secret.py` › test_agent_is_told_never_to_ask_for_a_secret: the system prompt the agent works with carries the rule never to ask for a secret and to warn first when the user offers one.

## OpenCode Delegation

`npm run test:opencode` builds the sandbox image and runs `tests/opencode-delegation.sh` against it. The OpenCode server runs from the same image; its model is the recording OpenAI-compatible endpoint of `tests/openai-stub.cjs`, which answers `pong`.

- **F14** `tests/opencode-delegation.sh` › sandbox_has_opencode_client: the sandbox image carries the OpenCode client, `opencode-delegate` and the skill `opencode-delegation`.
- **F14** `tests/opencode-delegation.sh` › stalled_server_ends_the_wait: against a server that takes the connection and never answers, `opencode-delegate` gives up after `HERMES_OPENCODE_TIMEOUT` seconds with exit code 4 and a message that names the timeout.
- **F14** `tests/opencode-delegation.sh` › url_and_skill_reach_the_agent: the sandbox, started through its real entrypoint, writes `HERMES_OPENCODE_URL` and `HERMES_OPENCODE_TIMEOUT` into `/etc/environment` for the agent's SSH sessions and installs the skill into `~/.hermes/skills`.
- **F14** `tests/opencode-delegation.sh` › task_delegated_and_answered: `opencode-delegate` hands a task to the OpenCode server, prints the answer and the session id, and continues that session with a follow-up that reaches OpenCode's model.
- **F14** `tests/opencode-delegation.sh` › password_server_refuses_sandbox: a server with `OPENCODE_SERVER_PASSWORD` refuses the sandbox, which holds no password, with HTTP 401 and a clear message, and answers a client that has the password.

## OpenCode in the Sandbox

`npm run test:opencode` also runs `tests/opencode-local.sh` against the built sandbox image: the stack `tests/opencode-local.yml` starts the sandbox, the real OpenCode gateway with a test key and the recording model endpoint of `tests/openai-stub.cjs` in the place of LiteLLM.

- **F15** `tests/opencode-local.sh` › gateway_and_models_reach_the_agent — the sandbox, started through its real entrypoint, writes `OPENCODE_GATEWAY_URL`, `OPENCODE_MODELS`, `HINDSIGHT_SHARED_BANK` and `HINDSIGHT_OWN_BANK` into `/etc/environment` for the agent's SSH sessions.
- **F15** `tests/opencode-local.sh` › memory_banks_through_the_gateway — in such a session, the configuration of OpenCode names both memory banks as MCP servers on the gateway.
- **F15** `tests/opencode-local.sh` › local_task_answered_through_the_gateway — in such a session, `opencode run` in a fresh git checkout prints the answer of the model, which received the key of the real `mwaeckerlin/opencode:gateway` and never the placeholder the sandbox sent.
- **F15** `tests/opencode-local.sh` › no_key_in_sandbox — the key of the gateway stands neither in the environment of the sandbox, nor in the configuration of OpenCode, nor in a file of the sandbox.
- **F15** `tests/compose-contract.sh` › local_opencode_through_its_gateway, opencode_from_sandbox_base — the sandbox names `http://hermes-opencode-gateway:8080`, shares a network of its own with that gateway, which runs `mwaeckerlin/opencode:gateway`, carries no key variable, and takes OpenCode from `mwaeckerlin/sandbox-base`.

## Data Flow

- **F12** `tests/test_isolation_check.py`: the gateway's start check passes the default configuration and MCP servers reached by `url`, and refuses `terminal.env_passthrough`, `terminal.credential_files` and an MCP server with `command`.

- **F10** `tests/test_config_hindsight.py` › test_shared_bank_carries_the_key_as_a_placeholder — with `HINDSIGHT_API_KEY` set, the MCP entry `hindsight-shared` carries `Authorization: Bearer ${HINDSIGHT_API_KEY}`, and the key itself does not stand in `config.yaml`.
- **F10** `tests/test_config_hindsight.py` — `memory.provider` from `HERMES_MEMORY_PROVIDER`, the shared bank as MCP server `hindsight-shared` beside the servers of `HERMES_MCP_SERVERS_YAML`, `hindsight/config.json` with `local_external` and `hybrid` by default and every `HINDSIGHT_*` setting from the environment, and never a key in it even when `HINDSIGHT_API_KEY` is set.
- **F11** `tests/test_config_hindsight.py` › test_litellm_base_url_alone_selects_litellm — `LITELLM_BASE_URL` alone sets the model endpoint.
- **F1** `tests/test_config_image_gen.py` — the gateway's config renderer omits, renders or replaces the `image_gen` section from the environment.
- **F1** `tests/test_config_compression.py` › test_compression_model_defaults_per_provider: without `HERMES_COMPRESSION_MODEL`, `auxiliary.compression` of the rendered configuration is exactly today's section for OpenRouter, Anthropic, Google, Gemini, OpenAI, LiteLLM with and without `LITELLM_DEFAULT_MODEL`, and no key.
- **F1** `tests/test_config_compression.py` › test_compression_model_from_the_environment: with `HERMES_COMPRESSION_MODEL` set, the same section carries that model for every provider and keeps everything else.
- **F1** `tests/test_config_compression.py` › test_compression_model_cannot_inject_keys: a model value with quotes and a line break stays one string and adds no key to the section.
- **F7** `tests/test_todo_storage.py` — the TODO store: persistence, claim, role-bound transitions, delete rules.
- **F16** `tests/test_base_path.py` › test_unset_or_root_serves_at_the_root, test_base_path_is_normalised, test_wrong_base_path_names_the_variable: unset, empty and `/` mean the root, a trailing slash and spaces are dropped, and every malformed value (no leading slash, space, `.` or `..` segment, empty segment, `?`, `#`, `%`, quotes, angle brackets, non-ASCII) is refused with a message that names `HERMES_BASE_PATH`.
- **F16** `tests/test_base_path.py` › test_request_below_the_base_path_reaches_the_dashboard_without_it, test_slash_form_of_the_base_path_reaches_the_root_of_the_dashboard, test_a_prefix_header_of_the_client_is_replaced, test_request_outside_the_base_path_reaches_the_dashboard_at_the_root, test_a_path_that_only_starts_like_the_base_path_lies_outside, test_bare_base_path_redirects_to_its_slash_form, test_bare_base_path_refuses_a_websocket, test_lifespan_reaches_the_dashboard_unchanged: the routing of `BasePathApp` for HTTP requests and websockets, inside, outside and at the bare path, with `X-Forwarded-Prefix` set by the image alone.
- **F16** `tests/test_base_path.py` › test_redirect_of_the_dashboard_gets_the_base_path, test_prefixed_foreign_and_relative_redirects_stay, test_redirect_outside_the_base_path_stays: a root-absolute redirect or one on the request's host gets the base path; one already below it and a foreign, protocol-relative or relative one stay, and other headers stay.
- **F16** `tests/test_base_path.py` › test_hook_serves_uvicorn_through_base_path_app, test_hook_leaves_uvicorn_alone_without_a_base_path, test_hook_stops_the_start_on_a_wrong_base_path: in a fresh Python, the hook puts `BasePathApp` in front of the application uvicorn loads, leaves it alone without the variable, and ends the start with code 1 and the message on a wrong value.
- **F16** `tests/test_base_path.py` › test_upstream_contract_holds_on_the_counted_texts, test_changed_upstream_stops_the_build_and_names_file_and_text, test_missing_upstream_file_stops_the_build: the build check of the dashboard image passes on the counted upstream texts and names the file and the text when a count differs or a file is missing.
- **F16** `tests/test_base_path.py` › test_preload_helper_builds_its_urls_below_the_base_path, test_bundle_without_the_preload_helper_stops_the_build, test_preload_helper_twice_stops_the_build: the build patch of Vite's preload helper, on the helper as Vite 8 writes it and as rolldown minifies it, puts `window.__HERMES_BASE_PATH__` in front of `"/" + file` in the one chunk that carries it and leaves the others alone; a bundle without the helper, with a relative base or with the helper twice stops the build with the count and the files and changes nothing.

## Compose Contract

- **F1** `tests/compose-contract.sh` › compose_renders, only_mwaeckerlin_images — the environment-driven stack renders and deploys only mwaeckerlin images.
- **F2** `tests/compose-contract.sh` › dashboard_port_published — the dashboard is reachable on its published port.
- **F3** `tests/compose-contract.sh` › sandbox_from_shared_base, only_dind_privileged — the sandbox builds on the shared base and runs unprivileged.
- **F3** `tests/compose-contract.sh` › skills_copied — the hermes skills are installed into the sandbox image.
- **F4** `tests/compose-contract.sh` › dind_is_rootless_dockindock, docker_host_port_wired, dind_volume_on_data_root — the sandbox's `DOCKER_HOST` matches the rootless dind service and its port, storage sits on the daemon's real data path.
- **F5** `tests/compose-contract.sh` › skills_copied — the GitHub MCP skill reaches the sandbox; the service URL is part of the rendered stack (compose_renders).
- **F6** `tests/compose-contract.sh` › ownership_bootstrap_present — the ownership bootstrap service is part of the stack.
- **F6** `tests/compose-contract.sh` › ownership_bootstrap_user_read: the ownership bootstrap service gets its user as `RUN_USER` and `RUN_GROUP`, the variables `mwaeckerlin/allow-write-access` reads, and no other variable.
- **F8** `tests/compose-contract.sh` › deploy_pushes_every_built_image, workflow_calls_shared_build — `npm run deploy` pushes exactly the images the compose file builds, and `.github/workflows/docker.yml` calls the shared workflow; the tag and architecture selection of that workflow is tested by `tests/workflow-contract.sh` of `mwaeckerlin/scratch`.
- **F16** `tests/compose-contract.sh` › dashboard_base_path_passed: the stack passes `HERMES_BASE_PATH` to the dashboard and to no other service.

## Frontend Unit

- **F7** `files/todo-plugin/test/index.test.js` — the TODO plugin frontend registers, exposes only the user-owned transitions and updates its list without a reload.
- **F9** `files/pairing-plugin/test/index.test.js` — the pairing plugin frontend registers, approves a pending request by its request id, shows no code column, and revokes by platform and user id.

[mwaeckerlin/sandbox-base]: https://github.com/mwaeckerlin/sandbox-base
[mwaeckerlin/dockindock]: https://github.com/mwaeckerlin/dockindock
