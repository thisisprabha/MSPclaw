#!/usr/bin/env bash
# MSPclaw — client installer (MacBook / requester machine).
# Sets up the agent + end-user CLI. Idempotent — safe to re-run.

set -euo pipefail

# Resolve repo root from this script's location, regardless of CWD.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors — only when running in a TTY.
if [[ -t 1 ]]; then
  B="\033[1m"; G="\033[32m"; Y="\033[33m"; R="\033[31m"; D="\033[2m"; N="\033[0m"
else
  B=""; G=""; Y=""; R=""; D=""; N=""
fi

say()  { printf "${B}==>${N} %s\n" "$*"; }
ok()   { printf "${G}✓${N}  %s\n" "$*"; }
warn() { printf "${Y}!${N}  %s\n" "$*"; }
die()  { printf "${R}✗${N}  %s\n" "$*" >&2; exit 1; }

cat <<EOF

${B}MSPclaw — client installer${N}
${D}This sets up the diagnostic agent + the 'mspclaw' command on this Mac.${N}

EOF

# 1. Python check
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
if [[ -z "$PYTHON" ]]; then
  die "Python 3.11+ not found. Install with:  brew install python@3.12"
fi
ok "$PYTHON ($("$PYTHON" --version))"

# 2. venv
say "Setting up virtual environment in .venv"
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
ok "venv ready"

# 3. Install deps
say "Installing dependencies (1–2 minutes)"
pip install --quiet -r requirements.txt
ok "dependencies installed"

# 4. Server URL
say "Configuring server connection"
DEFAULT_SERVER="${MSPCLAW_DEFAULT_SERVER:-}"
if [[ -f .env ]] && grep -q '^MSPCLAW_SERVER_URL=' .env; then
  DEFAULT_SERVER="$(grep '^MSPCLAW_SERVER_URL=' .env | head -1 | sed 's/^MSPCLAW_SERVER_URL=//')"
fi
prompt="Enter your MSP server LAN address (e.g. 192.168.1.42:8080)"
if [[ -n "$DEFAULT_SERVER" ]]; then
  prompt="$prompt [current: $DEFAULT_SERVER]"
fi
read -r -p "$prompt: " server_input
server_input="${server_input:-$DEFAULT_SERVER}"
if [[ -z "$server_input" ]]; then
  die "Server address is required."
fi
# Strip protocol if user pasted one.
server_input="${server_input#http://}"
server_input="${server_input#https://}"
server_input="${server_input#ws://}"
server_input="${server_input#wss://}"
# Add :8080 if no port given.
if [[ "$server_input" != *:* ]]; then
  server_input="${server_input}:8080"
fi
WS_URL="ws://${server_input}/ws/agent"
API_URL="http://${server_input}"

# 5. Write .env
say "Writing .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi
# Replace the relevant lines, preserving everything else.
python3 - "$WS_URL" "$API_URL" <<'PYEOF'
import sys, re, pathlib
ws, api = sys.argv[1], sys.argv[2]
p = pathlib.Path(".env")
text = p.read_text()
def upsert(text, key, val):
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={val}"
    return pat.sub(line, text) if pat.search(text) else text.rstrip() + f"\n{line}\n"
text = upsert(text, "MSPCLAW_SERVER_URL", ws)
text = upsert(text, "MSPCLAW_API_URL", api)
p.write_text(text)
PYEOF
ok ".env points at $WS_URL"

# 6. Install `mspclaw` command
say "Installing 'mspclaw' command"
mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/bin/mspclaw" "$HOME/.local/bin/mspclaw"
chmod +x "$SCRIPT_DIR/bin/mspclaw"

# Add ~/.local/bin to PATH if not already there.
shell_rc=""
case "${SHELL##*/}" in
  zsh)  shell_rc="$HOME/.zshrc" ;;
  bash) shell_rc="$HOME/.bash_profile" ;;
esac
if [[ -n "$shell_rc" ]]; then
  if ! grep -q 'HOME/.local/bin' "$shell_rc" 2>/dev/null; then
    printf '\n# Added by MSPclaw installer\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$shell_rc"
    warn "Added ~/.local/bin to PATH in $shell_rc — open a new terminal to pick it up"
  fi
fi
ok "'mspclaw' available at ~/.local/bin/mspclaw"

# 7. Auto-start agent on login? (launchd)
say "Background agent"
read -r -p "Start the diagnostic agent automatically on login? [Y/n] " autostart
autostart="${autostart:-Y}"
PLIST="$HOME/Library/LaunchAgents/com.mspclaw.agent.plist"
if [[ "$autostart" =~ ^[Yy] ]]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  mkdir -p "$HOME/.mspclaw/logs"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.mspclaw.agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>$SCRIPT_DIR/.venv/bin/python</string>
    <string>-m</string>
    <string>agent.main</string>
  </array>
  <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.mspclaw/logs/agent.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/.mspclaw/logs/agent.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
PLISTEOF
  # Reload if already loaded.
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  ok "agent registered with launchd (auto-starts on login)"
else
  warn "skipping auto-start. Run 'mspclaw start' to launch the agent manually."
fi

cat <<EOF

${G}${B}✓ Install complete.${N}

Try it:
    ${B}mspclaw issue "my mac is slow"${N}

Other commands:
    mspclaw status     show agent + server connectivity
    mspclaw start      start the agent (if not auto-started)
    mspclaw stop       stop the agent
    mspclaw logs       tail the agent log
    mspclaw uninstall  remove launchd service + the 'mspclaw' command

${D}If 'mspclaw' isn't found, open a new terminal window or run:${N}
    ${D}export PATH="\$HOME/.local/bin:\$PATH"${N}

EOF
