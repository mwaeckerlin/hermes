# Open Tasks

One line per task, newest on top: date, status, who asked. An entry is removed when the task is implemented, entered in [FEATURES.md](FEATURES.md), tested green and entered in [TESTS.md](TESTS.md).

## Maintainer

Nothing open.

## Dependencies outside this repository

- 2026-09-26 · open · the pipeline cannot build `hermes-sandbox` until `mwaeckerlin/sandbox-base` is published on Docker Hub; its repository is on GitHub since 2026-09-26 and lacks the secret `DOCKERHUB_TOKEN`
- 2026-09-26 · open · the arm64 build needs arm64 images of `mwaeckerlin/mcp-github` (gateway, sandbox) and `mwaeckerlin/nodejs-build` (dashboard); both are published for amd64 only; the commit ordered by Marc on 2026-09-26 is pushed once they and `mwaeckerlin/sandbox-base` are published for both architectures
