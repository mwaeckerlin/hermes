# Tests

Register of all tests, grouped by kind and sorted by the
[FEATURES.md](FEATURES.md) number each test covers. `npm test` runs
everything; the guard `tests/docs-contract.sh` fails when a feature has no
test entry here or when any test carries a skip/xfail marker — tests are
never skipped.

The sandbox toolset and SSH behaviour are tested end to end in the
[mwaeckerlin/sandbox-base] project (this stack consumes that image); the
rootless docker-in-docker daemon is tested end to end in the
[mwaeckerlin/dockindock] project.

## Contract-/Datenfluss-Tests

- **F1** `tests/compose-contract.sh` › compose_renders, only_mwaeckerlin_images — the environment-driven stack renders and deploys only mwaeckerlin images.
- **F2** `tests/compose-contract.sh` › dashboard_port_published — the dashboard is reachable on its published port.
- **F3** `tests/compose-contract.sh` › sandbox_from_shared_base, only_dind_privileged — the sandbox builds on the shared base and runs unprivileged.
- **F3** `tests/compose-contract.sh` › skills_copied — the hermes skills are installed into the sandbox image.
- **F4** `tests/compose-contract.sh` › dind_is_rootless_dockindock, docker_host_port_wired, dind_volume_on_data_root — the sandbox's `DOCKER_HOST` matches the rootless dind service and its port, storage sits on the daemon's real data path.
- **F5** `tests/compose-contract.sh` › skills_copied — the GitHub MCP skill reaches the sandbox; the service URL is part of the rendered stack (compose_renders).
- **F6** `tests/compose-contract.sh` › ownership_bootstrap_present — the ownership bootstrap service is part of the stack.

## Modul-/Unit-Tests

- **F7** `files/todo-plugin` test suite — the TODO plugin's storage and API behaviour.

[mwaeckerlin/sandbox-base]: https://github.com/mwaeckerlin/sandbox-base
[mwaeckerlin/dockindock]: https://github.com/mwaeckerlin/dockindock
