#!/bin/sh -e

HERMES_HOME="${HERMES_HOME:-/opt/data}"

mask_set() {
  _name="$1"
  eval "_value=\${${_name}:-}"
  if [ -n "$_value" ]; then
    echo "  - $_name: set"
  else
    echo "  - $_name: unset"
  fi
}

echo "==== Reading Docker Secrets ===="
_ssh_key_from_secret=false
_secret_names=""
for secret in /run/secrets/*; do
  test -e "$secret" || continue
  varname=$(basename "$secret" | tr '[:lower:]-' '[:upper:]_')
  _secret_names="${_secret_names:+$_secret_names, }$varname"
  if [ "$varname" = "HERMES_SANDBOX_SSH_PRIVATE_KEY" ]; then
    echo "Setting SSH private key from secret"
    _ssh_key_from_secret=true
  else
    echo "$varname from secret"
  fi
  export "$varname=$(sed -z 's/\n/\\n/g' "$secret")"
done
if [ -n "$_secret_names" ]; then
  echo "Secrets loaded: $_secret_names"
else
  echo "Secrets loaded: none"
fi

echo "==== Setting Derived Variables ===="
echo "HERMES_HOME=$HERMES_HOME"
echo "Configured secret-bearing env vars:"
for _var in \
  OPENROUTER_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY GOOGLE_API_KEY GEMINI_API_KEY \
  LITELLM_API_KEY TELEGRAM_BOT_TOKEN DISCORD_BOT_TOKEN SLACK_BOT_TOKEN SLACK_APP_TOKEN \
  VOICE_TOOLS_OPENAI_KEY GROQ_API_KEY EXA_API_KEY FIRECRAWL_API_KEY PARALLEL_API_KEY \
  TAVILY_API_KEY FAL_KEY BROWSERBASE_API_KEY ELEVENLABS_API_KEY GITHUB_TOKEN \
  HERMES_SANDBOX_SSH_PRIVATE_KEY; do
  mask_set "$_var"
done

# Require at least one LLM provider to be configured.
if [ -z "$OPENROUTER_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && \
   [ -z "$OPENAI_API_KEY" ] && [ -z "$GOOGLE_API_KEY" ] && \
   [ -z "$GEMINI_API_KEY" ] && [ -z "$LITELLM_BASE_URL" ]; then
  echo "ERROR: No LLM provider configured." >&2
  echo "       Set at least one of:" >&2
  echo "         OPENROUTER_API_KEY  — OpenRouter (300+ models)" >&2
  echo "         ANTHROPIC_API_KEY   — Anthropic Claude direct" >&2
  echo "         OPENAI_API_KEY      — OpenAI direct" >&2
  echo "         GOOGLE_API_KEY      — Google Gemini direct" >&2
  echo "         LITELLM_BASE_URL    — LiteLLM proxy (OpenAI-compatible)" >&2
  exit 1
fi

# Log which providers are active.
echo "==== Configured LLM Providers ===="
[ -n "$OPENROUTER_API_KEY" ]                           && echo "  - OpenRouter"
[ -n "$ANTHROPIC_API_KEY" ]                            && echo "  - Anthropic (Claude)"
[ -n "$OPENAI_API_KEY" ]                               && echo "  - OpenAI"
{ [ -n "$GOOGLE_API_KEY" ] || [ -n "$GEMINI_API_KEY" ]; } && echo "  - Google Gemini"
[ -n "$LITELLM_BASE_URL" ]                             && echo "  - LiteLLM ($LITELLM_BASE_URL)"
echo "LLM selection priority: OpenAI -> OpenRouter -> Anthropic -> Google -> LiteLLM"

# Whisper/TTS: VOICE_TOOLS_OPENAI_KEY is Hermes's real env var for voice features.
# Fall back to OPENAI_API_KEY if not set separately.
if [ -z "$VOICE_TOOLS_OPENAI_KEY" ] && [ -n "$OPENAI_API_KEY" ]; then
  export VOICE_TOOLS_OPENAI_KEY="$OPENAI_API_KEY"
  echo "VOICE_TOOLS_OPENAI_KEY set from OPENAI_API_KEY"
fi

echo "==== Setting Up SSH Key for Sandbox ===="
if [ -z "${HERMES_SANDBOX_SSH_PRIVATE_KEY:-}" ]; then
  echo "ERROR: HERMES_SANDBOX_SSH_PRIVATE_KEY is not set." >&2
  echo "       Provide it as an environment variable or as Docker secret hermes_sandbox_ssh_private_key." >&2
  exit 1
fi
if [ "$_ssh_key_from_secret" != "true" ]; then
  echo "Setting SSH private key from environment"
fi
mkdir -p "${HERMES_HOME}/.ssh"
printf '%b' "${HERMES_SANDBOX_SSH_PRIVATE_KEY}" | tr -d '\r' > "${HERMES_HOME}/.ssh/hermes-sandbox"
# Disable host key checking for the sandbox: the container gets a fresh host key
# on every restart, so strict checking would always fail.  This is safe because
# the sandbox is on a private Docker overlay network (gateway-sandbox) that is
# not reachable from outside the Compose stack.
_ssh_host="${HERMES_TERMINAL_SSH_HOST:-hermes-sandbox}"
cat > "${HERMES_HOME}/.ssh/config" <<EOF
Host ${_ssh_host}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    IdentityFile ${HERMES_HOME}/.ssh/hermes-sandbox
EOF
chown -R hermes:hermes "${HERMES_HOME}/.ssh"
chmod 700 "${HERMES_HOME}/.ssh"
chmod 600 "${HERMES_HOME}/.ssh/hermes-sandbox"
chmod 600 "${HERMES_HOME}/.ssh/config"
# TERMINAL_SSH_KEY is the env var Hermes reads for the SSH private key path.
export TERMINAL_SSH_KEY="${HERMES_HOME}/.ssh/hermes-sandbox"

echo "==== Rendering Jinja2 Configuration ===="
/opt/hermes/.venv/bin/python3 /render-config.py \
  /config.yaml.j2.default \
  "${HERMES_HOME}/config.yaml.rendered"
echo "Configuration rendered to ${HERMES_HOME}/config.yaml.rendered"

echo "==== Rendered Hermes Configuration Summary ===="
/opt/hermes/.venv/bin/python3 - <<'PY' "${HERMES_HOME}/config.yaml.rendered"
import sys
import yaml

path = sys.argv[1]
with open(path) as fh:
    cfg = yaml.safe_load(fh) or {}

def get(mapping, *path, default=None):
    cur = mapping
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

model = get(cfg, "model", default={}) or {}
terminal = get(cfg, "terminal", default={}) or {}
approvals = get(cfg, "approvals", default={}) or {}
streaming = get(cfg, "streaming", default={}) or {}
tts = get(cfg, "tts", default={}) or {}
stt = get(cfg, "stt", default={}) or {}
auxiliary = get(cfg, "auxiliary", default={}) or {}
vision = auxiliary.get("vision", {}) if isinstance(auxiliary, dict) else {}
compression = auxiliary.get("compression", {}) if isinstance(auxiliary, dict) else {}
web_extract = auxiliary.get("web_extract", {}) if isinstance(auxiliary, dict) else {}
web = get(cfg, "web", default={}) or {}
browser = get(cfg, "browser", default={}) or {}
display = get(cfg, "display", default={}) or {}
human_delay = get(cfg, "human_delay", default={}) or {}
delegation = get(cfg, "delegation", default={}) or {}

print(f"  model.default: {model.get('default', '(unset)')}")
print(f"  model.provider: {model.get('provider', '(unset)')}")
if model.get("base_url"):
    print(f"  model.base_url: {model['base_url']}")
if model.get("max_tokens") is not None:
    print(f"  model.max_tokens: {model['max_tokens']}")
print(f"  terminal.backend: {terminal.get('backend', '(unset)')}")
print(f"  terminal.ssh_target: {terminal.get('ssh_user', '(unset)')}@{terminal.get('ssh_host', '(unset)')}:{terminal.get('ssh_port', '(unset)')}")
print(f"  terminal.timeout: {terminal.get('timeout', '(unset)')}")
print(f"  approvals.mode: {approvals.get('mode', '(unset)')}")
print(f"  streaming.enabled: {streaming.get('enabled', '(unset)')}")
print(f"  tts.enabled: {tts.get('enabled', '(unset)')}")
print(f"  tts.provider: {tts.get('provider', '(unset)')}")
print(f"  stt.enabled: {stt.get('enabled', '(unset)')}")
if isinstance(stt.get("local"), dict):
    print(f"  stt.local.model: {stt['local'].get('model', '(unset)')}")
print(f"  auxiliary.compression.provider: {compression.get('provider', compression.get('base_url', '(unset)'))}")
print(f"  auxiliary.compression.model: {compression.get('model', '(unset)')}")
print(f"  auxiliary.vision.provider: {vision.get('provider', vision.get('base_url', '(unset)'))}")
print(f"  auxiliary.vision.model: {vision.get('model', '(unset)')}")
print(f"  auxiliary.web_extract.provider: {web_extract.get('provider', '(unset)')}")
if web:
    print(f"  web.backend: {web.get('backend', '(unset)')}")
if browser:
    print(f"  browser.inactivity_timeout: {browser.get('inactivity_timeout', '(unset)')}")
print(f"  display.tool_progress: {display.get('tool_progress', '(unset)')}")
print(f"  human_delay.mode: {human_delay.get('mode', '(unset)')}")
print(f"  delegation.max_iterations: {delegation.get('max_iterations', '(unset)')}")
PY

# LiteLLM uses the OpenAI wire protocol. The config template selects the
# LiteLLM base_url; this runtime bridge supplies the API key to Hermes's
# OpenAI-compatible transport without affecting rendered provider selection.
if [ -n "$LITELLM_BASE_URL" ] && [ -n "$LITELLM_API_KEY" ] && \
   [ -z "$OPENROUTER_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && \
   [ -z "$GOOGLE_API_KEY" ] && [ -z "$GEMINI_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
  export OPENAI_API_KEY="${LITELLM_API_KEY}"
  echo "LiteLLM API key bridged for OpenAI-compatible transport"
fi

echo "==== Configuring Hermes ===="
# Copy the freshly rendered config to config.yaml when:
#   - OVERWRITE_CONFIG is true/unset (default refresh), or
#   - config.yaml does not exist yet (first start).
# Set OVERWRITE_CONFIG=false to preserve manual edits in the persistent volume.
_overwrite_config="${OVERWRITE_CONFIG:-true}"
if [ "$_overwrite_config" = "true" ] || [ "$_overwrite_config" = "1" ] || [ "$_overwrite_config" = "yes" ] || [ "$_overwrite_config" = "on" ] || [ ! -e "${HERMES_HOME}/config.yaml" ]; then
  cp "${HERMES_HOME}/config.yaml.rendered" "${HERMES_HOME}/config.yaml"
  echo "config.yaml written"
else
  echo "config.yaml preserved (OVERWRITE_CONFIG=false)"
fi
echo "Active config file: ${HERMES_HOME}/config.yaml"

echo "==== Redirecting PID and Lock Files to /tmp ===="
# gateway.pid and gateway.lock must not live in the persistent volume — stale
# files from a previous container would block startup.  Symlink them into /tmp
# (ephemeral, never persisted) so the volume only holds user data.
for f in gateway.pid gateway.lock; do
  rm -f "${HERMES_HOME}/${f}"
  ln -sf "/tmp/${f}" "${HERMES_HOME}/${f}"
done

echo "==== Starting Hermes Gateway ===="
# SECURITY: local code execution runs inside the gateway container and has
# access to all API keys and secrets.  Force-disable it unconditionally so
# that no caller-supplied environment variable can ever enable it.
export HERMES_CODE_EXECUTION_ENABLED=false

# Fix ownership of the data directory (Hermes runs as uid 10000 / hermes).
if [ "$(stat -c '%u' "${HERMES_HOME}")" != "10000" ]; then
  echo "${HERMES_HOME} is not owned by 10000, fixing"
  chown -R hermes:hermes "${HERMES_HOME}"
fi

# Drop root privileges using Python's os.setuid/os.setgid + os.execv.
# This is the most reliable way to switch users while preserving the full
# environment block: os.execv() replaces the process image directly (no shell,
# no PAM, no login session) so every variable exported above is inherited.
# gosu/su are NOT used here because both can silently clear env vars after a
# setuid() call in certain Docker/kernel configurations.
echo "Dropping root privileges"
exec /opt/hermes/.venv/bin/python3 -c "
import os, sys, pwd, grp
p = pwd.getpwnam('hermes')
groups = list({g.gr_gid for g in grp.getgrall() if p.pw_name in g.gr_mem} | {p.pw_gid})
os.setgroups(groups)
os.setgid(p.pw_gid)
os.setuid(p.pw_uid)
# Update HOME/USER so Hermes writes state files to the hermes user's directory,
# not /root (which is not accessible after the privilege drop).
os.environ['HOME'] = p.pw_dir
os.environ['USER'] = p.pw_name
os.environ['LOGNAME'] = p.pw_name
os.execv(sys.argv[1], sys.argv[1:])
" /opt/hermes/.venv/bin/hermes "$@"
