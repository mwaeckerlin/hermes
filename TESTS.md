# Tests

Register of all tests, grouped by kind and sorted by the [FEATURES.md](FEATURES.md) number each test covers. `npm test` runs everything after `npm run build`; the guard `tests/docs-contract.sh` fails when a feature has no test entry here or when any test carries a skip marker — tests are never skipped.

The sandbox toolset and SSH behaviour are tested end to end in the [mwaeckerlin/sandbox-base] project (this stack consumes that image); the rootless docker-in-docker daemon is tested end to end in the [mwaeckerlin/dockindock] project.

## Backend API

`npm run test:python` runs these inside the built dashboard image (`test/docker-compose.yml`), on the plugin files and the config renderer as the dashboard and gateway images ship them, and on the pairing store of the hermes-agent version in the image.

- **F7** `tests/test_todo_api.py` — the TODO plugin API over HTTP: full review cycle, empty claim, forbidden transitions (400), unknown task (404), cancel and delete.
- **F9** `tests/test_pairing_api.py` — the pairing plugin API over HTTP: list with request id, approve by request id and by the reported code, unknown request and code refused, neither given (400), revoke.

## Data Flow

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
