# MSPclaw — Quickstart

The fastest path: clone the repo on each machine, double-click an installer, type your issue.

> **Two roles, two installers.** The Mac mini (or any always-on Mac) runs **the server** — that's where the AI lives. The MacBook (or any user's Mac) runs **the client** — agent + the `mspclaw` command.

---

## On the MSP's Mac mini (the server)

```bash
git clone https://github.com/prabha-thats-it/MSPclaw.git ~/MSPclaw
cd ~/MSPclaw
```

Then in **Finder**, open the `MSPclaw` folder and **double-click `install-server.command`**. A Terminal window opens. The script will ask you:

| Prompt | What to enter |
|---|---|
| Which LLM? `[openai/gemini/anthropic]` | `openai` (cheapest, default) — or `anthropic` / `gemini` if you prefer |
| `OPENAI_API_KEY` (get one at platform.openai.com/api-keys) | Paste your `sk-…` key. Input is hidden. |
| Start the server automatically on login? `[Y/n]` | `Y` (recommended) |

When done, the script prints the Mac mini's LAN address, e.g. `http://192.168.1.42:8080`. **Write it down** — the MacBook needs it next.

**Verify it's running:**
```bash
curl http://localhost:8080/health
```
Expected: `{"status":"ok","connected_agents":0}`

**Logs live at:** `~/.mspclaw/logs/server.err.log` (`tail -f` it if anything looks wrong).

---

## On the requester's MacBook (the client)

```bash
git clone https://github.com/prabha-thats-it/MSPclaw.git ~/MSPclaw
cd ~/MSPclaw
```

Double-click `install-client.command`. The script asks:

| Prompt | What to enter |
|---|---|
| Enter your MSP server LAN address | `192.168.1.42:8080` (whatever you wrote down) |
| Start the diagnostic agent automatically on login? `[Y/n]` | `Y` |

When done, **open a fresh terminal** (so the new PATH picks up) and try:

```bash
mspclaw issue "my mac is slow"
```

What happens:
1. CLI sends the issue to the Mac mini.
2. Mac mini's brain decides which diagnostic to run.
3. Mac mini asks the MacBook to run it (over the open WebSocket).
4. MacBook reads its real CPU/memory/disk numbers locally.
5. Mac mini's brain reads them, writes a recommendation.
6. CLI prints the recommendation. Total time: ~5–15 sec.

---

## The `mspclaw` command

```bash
mspclaw issue "..."   # submit an issue
mspclaw status        # is the agent running? is the server reachable?
mspclaw start         # start the agent (if you didn't auto-start)
mspclaw stop          # stop the agent
mspclaw logs          # tail ~/.mspclaw/logs/agent.err.log
mspclaw uninstall     # remove launchd service + the command
```

---

## Switching LLMs later

Edit `~/MSPclaw/.env` on the **server** and restart:

```env
MSPCLAW_LLM_PROVIDER=anthropic     # openai | gemini | anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5   # default
```

Then on the Mac mini:
```bash
launchctl unload ~/Library/LaunchAgents/com.mspclaw.server.plist
launchctl load   ~/Library/LaunchAgents/com.mspclaw.server.plist
```

The MacBook needs no change — it doesn't know or care which LLM the server uses.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `mspclaw: command not found` | New PATH not loaded yet | Open a new terminal, or `source ~/.zshrc` |
| `mspclaw status` shows server UNREACHABLE | Wrong IP, or Mac mini asleep, or firewall blocking 8080 | `ping 192.168.1.42` from MacBook; on Mac mini → System Settings → Network → Firewall → allow Python |
| `connected_agents: 0` after install | MacBook agent didn't start | `mspclaw start` then `mspclaw status` |
| `mspclaw issue` returns `{"status": "no_playbook"}` | Issue text didn't match any keyword | Try wording with "slow", "lag", "cpu", "memory", "disk" |
| Server log shows `OPENAI_API_KEY not set` | `.env` missing the key, or auto-start ran before key was saved | Edit `~/MSPclaw/.env`, then reload the launchd service (see "Switching LLMs" above) |
| MacBook agent log shows reconnecting in N seconds | Server down, or wrong URL in `.env` | Check `~/MSPclaw/.env` on MacBook — `MSPCLAW_SERVER_URL=ws://<mac-mini-ip>:8080/ws/agent` |

---

## Going further

- **Full uninstall on either machine:** double-click `uninstall.command` in the repo. Removes launchd services, the `mspclaw` command, and the persisted machine_id. Leaves the repo + venv + `.env` so you can re-install without re-typing keys.
- **Different LLM for testing:** the server's `MSPCLAW_LLM_PROVIDER` env var swaps adapters with no code change. Useful for comparing cost/quality between OpenAI 4o-mini, Gemini 2.0-flash, and Claude Haiku 4.5.
- **Windows server, Mac client:** the FastAPI server runs on Windows too — deps install with `pip install -r requirements.txt`. The MacBook agent then points at `ws://<windows-ip>:8080/ws/agent`. (Windows-side agent isn't supported in v0.1 — agent tools are macOS-specific via `psutil`.)
- **Adding playbooks:** edit `playbooks/macos/*.yaml` on the server, restart. Each playbook is a YAML file with match keywords + escalation levels (L1/L2/L3) listing allowed tools. The brain is whitelist-bound by these — it can't reach for tools the playbook doesn't permit.

---

## What's actually on disk after a successful install

**Server (Mac mini):**
- Repo at `~/MSPclaw`
- venv at `~/MSPclaw/.venv`
- Config at `~/MSPclaw/.env`
- Database at `~/MSPclaw/mspclaw.db` (SQLite)
- Launchd plist at `~/Library/LaunchAgents/com.mspclaw.server.plist`
- Logs at `~/.mspclaw/logs/server.{out,err}.log`

**Client (MacBook):**
- Repo at `~/MSPclaw`
- venv at `~/MSPclaw/.venv`
- Config at `~/MSPclaw/.env`
- Persistent machine ID at `~/.mspclaw/machine_id`
- `mspclaw` command at `~/.local/bin/mspclaw` (symlink → `~/MSPclaw/bin/mspclaw`)
- Launchd plist at `~/Library/LaunchAgents/com.mspclaw.agent.plist`
- Logs at `~/.mspclaw/logs/agent.{out,err}.log`
