#!/usr/bin/env bash
# MSPclaw — server installer (Mac mini).
# Sets up the FastAPI server + AI brain. Idempotent.

set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [[ -t 1 ]]; then
  B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else
  B=""; G=""; Y=""; R=""; D=""; N=""
fi
say()  { printf "%s==>%s %s\n" "$B" "$N" "$*"; }
ok()   { printf "%s✓%s  %s\n" "$G" "$N" "$*"; }
warn() { printf "%s!%s  %s\n" "$Y" "$N" "$*"; }
die()  { printf "%s✗%s  %s\n" "$R" "$N" "$*" >&2; exit 1; }

cat <<EOF

${B}MSPclaw — server installer${N}
${D}This sets up the MSP-side AI brain on this Mac.${N}

EOF

# 1. Python check (same as client)
say "Checking Python 3.11+"
PYTHON=""
for cand in python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "0.0")
    major=${ver%.*}; minor=${ver#*.}
    if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
      PYTHON="$cand"; break
    fi
  fi
done
[[ -z "$PYTHON" ]] && die "Python 3.11+ not found. Try:  brew install python@3.12"
ok "$PYTHON"

# 2. venv + deps
say "Setting up venv + installing dependencies"
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "dependencies installed"

# 3. LLM provider + key
say "Configuring AI provider"

# Read existing if any.
existing_provider=""
if [[ -f .env ]] && grep -q '^MSPCLAW_LLM_PROVIDER=' .env; then
  existing_provider="$(grep '^MSPCLAW_LLM_PROVIDER=' .env | head -1 | sed 's/^MSPCLAW_LLM_PROVIDER=//')"
fi
prompt="Which LLM? [openai/gemini/anthropic]"
if [[ -n "$existing_provider" ]]; then
  prompt="$prompt (current: $existing_provider, press Enter to keep)"
else
  prompt="$prompt (default: openai)"
fi
read -r -p "$prompt: " provider
provider="${provider:-${existing_provider:-openai}}"
case "$provider" in
  openai)    key_var="OPENAI_API_KEY";    key_url="https://platform.openai.com/api-keys" ;;
  gemini)    key_var="GEMINI_API_KEY";    key_url="https://aistudio.google.com/apikey" ;;
  anthropic) key_var="ANTHROPIC_API_KEY"; key_url="https://console.anthropic.com/settings/keys" ;;
  *) die "unknown provider '$provider'. Choose openai, gemini, or anthropic." ;;
esac

existing_key=""
if [[ -f .env ]] && grep -q "^${key_var}=" .env; then
  existing_key="$(grep "^${key_var}=" .env | head -1 | sed "s/^${key_var}=//")"
fi
key_prompt="$key_var (get one at $key_url)"
if [[ -n "$existing_key" ]]; then
  key_prompt="$key_prompt — press Enter to keep existing"
fi
read -r -s -p "$key_prompt: " api_key
echo
api_key="${api_key:-$existing_key}"
if [[ -z "$api_key" ]]; then
  die "API key is required."
fi

# 4. Write .env (preserve other keys)
say "Writing .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi
python3 - "$provider" "$key_var" "$api_key" <<'PYEOF'
import sys, re, pathlib
provider, key_var, key_val = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(".env")
text = p.read_text()
def upsert(text, key, val):
    # Uncomment a commented-out matching line, otherwise upsert.
    cpat = re.compile(rf"^#\s*{re.escape(key)}=.*$", re.MULTILINE)
    text = cpat.sub(f"{key}={val}", text)
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    return pat.sub(f"{key}={val}", text) if pat.search(text) else text.rstrip() + f"\n{key}={val}\n"
text = upsert(text, "MSPCLAW_LLM_PROVIDER", provider)
text = upsert(text, key_var, key_val)
p.write_text(text)
PYEOF
ok "provider=$provider, $key_var set"

# 5. Auto-start server on login?
say "Background server"
read -r -p "Start the MSPclaw server automatically on login? [Y/n] " autostart
autostart="${autostart:-Y}"
PLIST="$HOME/Library/LaunchAgents/com.mspclaw.server.plist"
if [[ "$autostart" =~ ^[Yy] ]]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  mkdir -p "$HOME/.mspclaw/logs"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.mspclaw.server</string>
  <key>ProgramArguments</key>
  <array>
    <string>$SCRIPT_DIR/.venv/bin/python</string>
    <string>-m</string>
    <string>server.main</string>
  </array>
  <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.mspclaw/logs/server.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/.mspclaw/logs/server.err.log</string>
</dict>
</plist>
PLISTEOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  ok "server registered with launchd"

  # Determine LAN IP for the next-step instruction.
  LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo '<this-mac-ip>')"
  cat <<EOF

${G}${B}✓ Server running.${N}

Server should be reachable at:  ${B}http://$LAN_IP:8080${N}
Health check:                   curl http://$LAN_IP:8080/health
Logs:                           tail -f ~/.mspclaw/logs/server.err.log

On the requester's MacBook, run install-client.command and enter:
    ${B}$LAN_IP:8080${N}

EOF
else
  warn "skipping auto-start. Run manually with:  source .venv/bin/activate && python -m server.main"
fi
