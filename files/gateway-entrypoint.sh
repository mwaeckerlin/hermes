#!/bin/sh -e

HERMES_HOME="${HERMES_HOME:-/opt/data}"

echo "==== Reading Docker Secrets ===="
_ssh_key_from_secret=false
for secret in /run/secrets/*; do
  test -e "$secret" || continue
  varname=$(basename "$secret" | tr '[:lower:]-' '[:upper:]_')
  if [ "$varname" = "HERMES_SANDBOX_SSH_PRIVATE_KEY" ]; then
    echo "Setting SSH private key from secret"
    _ssh_key_from_secret=true
  else
    echo "$varname from secret"
  fi
  export "$varname=$(sed -z 's/\n/\\n/g' "$secret")"
done

echo "==== Setting Derived Variables ===="
# Do not pass empty-string numeric overrides to Hermes. Hermes parses these
# with int(...), where "" raises ValueError and breaks message handling.
for _num_var in HERMES_HUMAN_DELAY_MIN_MS HERMES_HUMAN_DELAY_MAX_MS; do
  eval "_num_val=\${${_num_var}-}"
  if [ -z "${_num_val}" ]; then
    unset "${_num_var}"
  fi
done

# LiteLLM proxy: exposes an OpenAI-compatible endpoint at LITELLM_BASE_URL.
# Bridge into the slots Hermes reads when LiteLLM is the chosen provider.
# Only applied when no higher-priority provider is available.
if [ -n "$LITELLM_BASE_URL" ]; then
  if [ -z "$OPENROUTER_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && \
     [ -z "$GOOGLE_API_KEY" ] && [ -z "$GEMINI_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    export HERMES_MODEL_BASE_URL="${HERMES_MODEL_BASE_URL:-$LITELLM_BASE_URL}"
    # LiteLLM uses the OpenAI wire protocol; supply the key via OPENAI_API_KEY.
    if [ -n "$LITELLM_API_KEY" ]; then
      export OPENAI_API_KEY="${LITELLM_API_KEY}"
    fi
    echo "LiteLLM provider configured: $LITELLM_BASE_URL"
  fi
fi

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

# Whisper/TTS: VOICE_TOOLS_OPENAI_KEY is Hermes's real env var for voice features.
# Fall back to OPENAI_API_KEY if not set separately.
if [ -z "$VOICE_TOOLS_OPENAI_KEY" ] && [ -n "$OPENAI_API_KEY" ]; then
  export VOICE_TOOLS_OPENAI_KEY="$OPENAI_API_KEY"
  echo "VOICE_TOOLS_OPENAI_KEY set from OPENAI_API_KEY"
fi

# Auto-select default model based on available API keys (overridable via HERMES_DEFAULT_MODEL).
# All providers are optional; multiple can be active simultaneously — the priority
# order below only determines which model is used by default.
if [ -z "$HERMES_DEFAULT_MODEL" ]; then
  if [ -n "$OPENROUTER_API_KEY" ]; then
    # Model ID for OpenRouter: use the bare OpenRouter slug (e.g. anthropic/claude-opus-4-5)
    # WITHOUT any "openrouter/" routing prefix.  Hermes passes the model string
    # directly to https://openrouter.ai/api/v1, so the prefix must not appear in
    # the actual HTTP request body — OpenRouter rejects "openrouter/..." IDs.
    export HERMES_DEFAULT_MODEL="anthropic/claude-opus-4-5"
  elif [ -n "$ANTHROPIC_API_KEY" ]; then
    export HERMES_DEFAULT_MODEL="anthropic/claude-opus-4.6"
  elif [ -n "$GOOGLE_API_KEY" ] || [ -n "$GEMINI_API_KEY" ]; then
    export HERMES_DEFAULT_MODEL="gemini/gemini-2.5-pro"
  elif [ -n "$OPENAI_API_KEY" ]; then
    # Hermes's "auto" provider only tries OpenRouter → Nous → Codex and will
    # never reach OPENAI_API_KEY.  Use provider=custom with the OpenAI base URL
    # so requests go directly to api.openai.com (OPENAI_API_KEY is picked up
    # automatically by the custom endpoint auth chain).
    # Use o4-mini (not gpt-4o): Hermes always enables reasoning on the Responses
    # API transport with include=["reasoning.encrypted_content"], which gpt-4o
    # rejects (HTTP 400).  o4-mini fully supports the Responses API + encrypted
    # reasoning and is cost-effective for general assistant use.
    export HERMES_DEFAULT_MODEL="o4-mini"
    export HERMES_MODEL_PROVIDER="${HERMES_MODEL_PROVIDER:-custom}"
    export HERMES_MODEL_BASE_URL="${HERMES_MODEL_BASE_URL:-https://api.openai.com/v1}"
  elif [ -n "$LITELLM_BASE_URL" ]; then
    export HERMES_DEFAULT_MODEL="${LITELLM_DEFAULT_MODEL:-gpt-4o}"
  fi
  if [ -n "$HERMES_DEFAULT_MODEL" ]; then
    echo "HERMES_DEFAULT_MODEL auto-selected: $HERMES_DEFAULT_MODEL"
  fi
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

echo "==== Configuring Hermes ===="
# Copy the freshly rendered config to config.yaml when:
#   - OVERWRITE_CONFIG is set (admin-forced refresh), or
#   - config.yaml does not exist yet (first start).
# Leave the file untouched on subsequent starts to preserve user edits.
if [ -n "${OVERWRITE_CONFIG:-}" ] || [ ! -e "${HERMES_HOME}/config.yaml" ]; then
  cp "${HERMES_HOME}/config.yaml.rendered" "${HERMES_HOME}/config.yaml"
  echo "config.yaml written"
else
  echo "config.yaml preserved (set OVERWRITE_CONFIG=true to regenerate)"
fi

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
