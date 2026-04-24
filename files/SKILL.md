---
name: ssh-sandbox
description: Use this skill to operate safely inside the Hermes SSH sandbox.
---

# SSH Sandbox

Canonical active install path on the sandbox:

- `~/.hermes/skills/ssh-sandbox/SKILL.md`

Only this path counts as installed. Hermes syncs skills from the gateway to
this directory automatically via the SSH backend before each session.

## Environment Facts

- You run in an Ubuntu SSH sandbox. The Hermes gateway connects here via SSH.
- Package inventory sources:
  - `/etc/installed-ubuntu-packages` (image package list)
  - `/var/lib/dpkg/status` (dpkg database)
- If `DOCKER_HOST` is set, Docker is available through a connected Docker service.

## First Steps (Always)

Run:

```bash
uname -a
cat /etc/os-release
whoami
pwd
echo "DOCKER_HOST=${DOCKER_HOST}"
test -f /etc/installed-ubuntu-packages && echo "package list present"
test -f /var/lib/dpkg/status && echo "dpkg status present"
```

Interpretation:

- Empty `DOCKER_HOST` — do not assume Docker usage.
- Missing `/etc/installed-ubuntu-packages` or `/var/lib/dpkg/status` — package
  baseline is unverified; treat package assumptions as uncertain.
- `DOCKER_HOST` set does not guarantee usability; only treat Docker as usable
  after `docker info` succeeds.

## Security Rules

Mandatory:

- Do not expect gateway API keys or LLM provider tokens in the sandbox.
- Do not perform direct secret extraction attempts.
- Do not infer permission or safety from command visibility alone.

## Common False Assumptions

- Gateway tokens or LLM API keys are not available inside the sandbox. False
  assumptions about their presence are a security risk.
- A visible CLI command is automatically usable/safe. False.
- Missing tokens inside sandbox is a configuration bug. False — by design.

## Packaged Skill Sources

This deployment copies skills at sandbox startup into `~/.hermes/skills/`:

- `/opt/hermes/skills/ssh-sandbox/SKILL.md`

Verify installed copies:

```bash
find ~/.hermes/skills -maxdepth 3 -type f -name 'SKILL.md' 2>/dev/null
```

## Troubleshooting

### Docker not available

```bash
echo "$DOCKER_HOST"
docker info
```

- Empty `DOCKER_HOST`: Docker not configured for this session.
- `DOCKER_HOST` set but failing: verify the Docker service/container/network.

### Skill missing

```bash
find ~/.hermes/skills -maxdepth 3 -type d 2>/dev/null
find ~/.hermes/skills -maxdepth 3 -type f -name 'SKILL.md' 2>/dev/null
```
