# Changelog

- 2026-07-28 **1.0.1**
    - Docker-in-docker is now rootless: the sandbox's docker service runs the hardened mwaeckerlin/dockindock image instead of the foreign root-daemon docker:dind — a compromise of the inner daemon no longer yields a root process, and inner images persist on the daemon's real data path
        - no host configuration is needed for this (no AppArmor profile, no sysctl change)
        - inner images from the previous root daemon are not reused; they are simply pulled again on first use
    - The sandbox now builds on the shared base image mwaeckerlin/sandbox-base: the complete toolset, the hardened SSH configuration and the docker client are maintained and tested once for all agent sandboxes — the hermes sandbox only adds its skills and entrypoint
    - Feature and test registers added (FEATURES.md, TESTS.md) with an automatic guard, plus a stack wiring contract test (only mwaeckerlin images deployed, docker host/port wiring, privileges, skills, ownership bootstrap)
