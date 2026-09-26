# Changelog

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
