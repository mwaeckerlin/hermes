# Changelog

- 2026-10-19 **1.0.7**
    - The gateway turns healthy in Docker Swarm: its health check asked `/healthz`, which the API server of hermes does not serve, so Swarm stopped the gateway again and again; it asks `/health` now and prints the answer or what it waits for
    - The gateway creates the key of its API server in the data volume when none is given, as the upstream image does, so the API server and its health check run also without a dashboard on the volume
    - The shared Hindsight bank is reached with the gateway's Hindsight key: its MCP entry carries the key as bearer, filled in by hermes when it connects, where Hindsight refused the connect with 401
    - Test suite: the OpenCode delegation contract waits until the sandbox has written the OpenCode URL into the environment of the SSH sessions, where it read the environment as soon as the skills were copied and failed when the URL came a moment later

- 2026-10-18 **1.0.6**
    - The gateway gets through its first start on an empty data volume that the dashboard shares: the install of the Hindsight plugin is tried again when hermes refuses to publish it because the dashboard rewrote `config.yaml` meanwhile, up to `HERMES_PLUGIN_INSTALL_ATTEMPTS` times (default 5), and a gateway restarted in the middle of the install gets through as well
    - Test suite: the Hindsight end-to-end tests start again with the current upstream hermes, which takes the base site-packages off the path when it selects the plugin's dependencies, so pytest lost the metadata of pluggy

- 2026-10-15 **1.0.5**
    - The dashboard takes its password and session key from Docker secrets, so a swarm deployment shows neither in its configuration
    - The gateway image builds and starts again with the current Hermes, which reads YAML with another library
    - Hindsight memory with the current Hermes, where Hindsight became a plugin: the gateway installs it into the data volume on its first start, which needs GitHub and PyPI once
    - The current Hermes holds back only its own new Python packages for 14 days, no longer those of a plugin: Hindsight's packages arrive without the waiting period, a risk named in the README

- 2026-09-29 **1.0.4**
    - Development goes to OpenCode: the agent hands software development tasks to the central OpenCode server set in `HERMES_OPENCODE_URL` and reports its result; the sandbox carries the OpenCode client
    - A delegation that gets no answer ends after `HERMES_OPENCODE_TIMEOUT` seconds (two hours by default) with a message, and an unreachable or refusing OpenCode server is named as such

- 2026-09-29 **1.0.3**
    - Long-term memory with a self-hosted Hindsight server: the agent recalls and retains in its own memory bank and reaches a bank shared with other agents; everything is set from the environment, and the Hindsight key is optional
    - LiteLLM needs only its address; its key is optional, for a LiteLLM that needs none or a proxy that adds it
    - The agent never gets a token, a key or a password: no secret of the gateway reaches the sandbox, proven on every build by a test that lets the real agent search for planted secrets
        - the gateway's SSH key no longer lies in the data volume, from where a configuration could copy it into the sandbox; an old key file in the volume is removed
        - the gateway refuses to start with a configuration that hands variables or files to the sandbox, or with an MCP server running inside the gateway
    - The agent is told never to ask for a password or token, and to warn first when you offer one
    - The dashboard starts again with the current Hermes, which requires a login: set a user name and a password (or its hash)

- 2026-09-26 **1.0.2**
    - The images are published for amd64 and arm64, built and published automatically on every change and every week, each under its tag, its tag with the build date, its tag with the version, and its tag with version and date
    - Pairing tab: approving a pending request works again with the current Hermes, which no longer hands out the pairing code; the tab approves the request itself and no longer shows an empty code column
    - The dashboard's frontend plugins are built on the mwaeckerlin build image instead of a foreign Node image
    - README: the pairing tab, the roles in the TODO tab, the rootless docker-in-docker and the GitHub MCP network are described as they are

- 2026-07-28 **1.0.1**
    - Docker-in-docker is now rootless: the sandbox's docker service runs the hardened mwaeckerlin/dockindock image instead of the foreign root-daemon docker:dind — a compromise of the inner daemon no longer yields a root process, and inner images persist on the daemon's real data path
        - no host configuration is needed for this (no AppArmor profile, no sysctl change)
        - inner images from the previous root daemon are not reused; they are simply pulled again on first use
    - The sandbox now builds on the shared base image mwaeckerlin/sandbox-base: the complete toolset, the hardened SSH configuration and the docker client are maintained and tested once for all agent sandboxes — the hermes sandbox only adds its skills and entrypoint
    - Feature and test registers added (FEATURES.md, TESTS.md) with an automatic guard, plus a stack wiring contract test (only mwaeckerlin images deployed, docker host/port wiring, privileges, skills, ownership bootstrap)
