# Features

Numbered register of every end-user visible feature; a number is never reused. Every feature is covered by tests listed in [TESTS.md](TESTS.md); the guard `tests/docs-contract.sh` fails when a feature has no test.

- **F1 — Hermes agent gateway, fully configurable via environment.** The gateway runs the Hermes agent with messaging channels (Telegram, WhatsApp, Discord, Slack), model providers and tool integrations configured entirely through environment variables rendered into the configuration at startup.
- **F2 — Web dashboard.** A separate dashboard service (port 9119) shows the gateway state and the TODO board.
- **F3 — Isolated SSH sandbox with the full development toolset.** The agent works in a separate container (key-only SSH, unprivileged user) built on the shared [mwaeckerlin/sandbox-base] — compilers, language runtimes, media/LaTeX tools, database clients — with the hermes skills preinstalled.
- **F4 — Docker-in-docker for the sandbox.** The sandbox can build and run containers against a dedicated rootless [mwaeckerlin/dockindock] daemon on an isolated network — a compromise of the inner daemon never yields root, and inner images persist across restarts.
- **F5 — GitHub MCP integration.** The GitHub MCP service is wired into the sandbox (skill and service URL).
- **F6 — Persistent state with correct ownership.** Gateway data and sandbox workspaces live on named volumes; ownership is bootstrapped automatically so the unprivileged users can write.
- **F7 — TODO dashboard plugin.** A local TODO board plugin stores and serves tasks for the dashboard. The human operator adds, cancels, accepts, rejects and deletes tasks in the dashboard; the agent claims the next open task and marks it done through the plugin API.
- **F8 — Published for amd64 and arm64.** Every push to `master` and a weekly rebuild build each image natively for both architectures and publish it on Docker Hub as one multi-platform image under its tag, its tag with the build date, its tag with the version, and its tag with version and date, with the reusable workflow of `mwaeckerlin/scratch`.
- **F9 — Pairing dashboard plugin.** The dashboard lists the pending pairing requests and the approved users of the chat platforms; the operator approves a request to admit its user and revokes an approved user.

[mwaeckerlin/sandbox-base]: https://github.com/mwaeckerlin/sandbox-base
[mwaeckerlin/dockindock]: https://github.com/mwaeckerlin/dockindock
