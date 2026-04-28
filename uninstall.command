#!/usr/bin/env bash
# MSPclaw uninstaller. Removes launchd services, the 'mspclaw' command,
# and the persisted machine_id. Leaves the repo, .venv, and .env intact —
# delete the repo manually if you want a clean slate.

set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [[ -t 1 ]]; then
  B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; D=$'\033[2m'; N=$'\033[0m'
else
  B=""; G=""; Y=""; D=""; N=""
fi

cat <<EOF

${B}MSPclaw — uninstaller${N}
${D}Removes background services and the 'mspclaw' command. Leaves the repo, venv, and .env in place.${N}

EOF

read -r -p "Continue? [y/N] " confirm
[[ "${confirm:-N}" =~ ^[Yy] ]] || { echo "Aborted."; exit 0; }

removed=0

for label in com.mspclaw.agent com.mspclaw.server; do
  plist="$HOME/Library/LaunchAgents/$label.plist"
  if [[ -f "$plist" ]]; then
    launchctl unload "$plist" 2>/dev/null || true
    rm -f "$plist"
    echo "${G}✓${N}  removed $label"
    removed=$((removed+1))
  fi
done

if [[ -L "$HOME/.local/bin/mspclaw" ]] || [[ -f "$HOME/.local/bin/mspclaw" ]]; then
  rm -f "$HOME/.local/bin/mspclaw"
  echo "${G}✓${N}  removed ~/.local/bin/mspclaw"
  removed=$((removed+1))
fi

if [[ -f "$HOME/.mspclaw/machine_id" ]]; then
  rm -f "$HOME/.mspclaw/machine_id"
  echo "${G}✓${N}  removed ~/.mspclaw/machine_id"
  removed=$((removed+1))
fi

if [[ $removed -eq 0 ]]; then
  echo "${Y}!${N}  nothing to remove — was MSPclaw installed on this Mac?"
fi

cat <<EOF

${G}Done.${N} The repo at $SCRIPT_DIR is untouched.
To remove it completely:
    rm -rf "$SCRIPT_DIR"
And to clear logs:
    rm -rf ~/.mspclaw

EOF
