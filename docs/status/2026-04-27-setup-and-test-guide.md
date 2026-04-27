# MSPclaw — Two-Machine Setup & Test Guide

A step-by-step guide written for someone who has never used MSPclaw before. Follow top to bottom.

---

## 1. The big picture (what you're about to do)

MSPclaw has three roles:

- **Server** — the brain. Runs on the Mac mini. Talks to Google's Gemini AI.
- **Agent** — the hands. Runs on the MacBook Pro. Executes diagnostic tools when the server asks.
- **End-user CLI** — the user's voice. Also runs on the MacBook Pro. Lets the user type "my mac is slow" and get an answer.

The Mac mini and MacBook talk over your home Wi-Fi. The MacBook opens a long-lived connection **out** to the Mac mini (so no router port forwarding needed).

```
+--------------+                        +---------------+
|  Mac mini    | <-- WebSocket -------- | MacBook Pro   |
|  (server)    |                        | (agent + CLI) |
|  Gemini AI   |                        | runs tools    |
+--------------+                        +---------------+
```

---

## 2. Before you start — what you need

- **Mac mini** with macOS, internet, Python 3.11+ installed (`python3 --version` — if it says 3.11 or higher you're good; if not, install from [python.org](https://www.python.org/downloads/macos/) or `brew install python@3.12`).
- **MacBook Pro** with the same.
- **A Gemini API key.** Get one free at <https://aistudio.google.com/app/apikey>. It's a long string starting with `AIza…`. **Only the Mac mini needs this** — the MacBook never sees it.
- **Both machines on the same Wi-Fi network.**
- **Git installed** on both (`git --version`).

You will NOT need: Postgres, Docker, any cloud account besides Google AI Studio.

---

## 3. Find the Mac mini's IP address

On the **Mac mini**, open Terminal and run:

```bash
ipconfig getifaddr en0
```

You'll get something like `192.168.1.42`. **Write this down** — the MacBook needs it.

(If `en0` returns nothing, try `en1` — Wi-Fi vs ethernet.)

---

## 4. Mac mini setup (the server)

### 4a. Get the code

```bash
cd ~
git clone <your-MSPclaw-repo-url> MSPclaw
cd MSPclaw
```

(If you don't have a repo URL yet — push this folder to GitHub first, or just copy the `MSPclaw/` directory across with `scp`/AirDrop.)

### 4b. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

This downloads ~15 Python packages (FastAPI, Gemini SDK, etc.). Takes 1–2 minutes.

### 4c. Set the API key

Copy the example env file and edit it:

```bash
cp .env.example .env
nano .env
```

Find this line and paste your key:

```
GEMINI_API_KEY=AIza…your-key-here…
```

⚠️ **Important fix:** if `.env` has a line starting with `MSPCLAW_DB_URL=postgresql://`, **delete it or comment it out** (`#MSPCLAW_DB_URL=...`). Otherwise the server tries Postgres and crashes. SQLite is the default and that's fine.

Save (Ctrl-O, Enter, Ctrl-X).

### 4d. Start the server

```bash
make server
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8080
INFO:     Application startup complete.
```

Leave this terminal open. The server is now listening.

### 4e. Verify from the Mac mini itself

Open a **second** Terminal on the Mac mini:

```bash
curl http://localhost:8080/health
```

Expected: `{"status":"ok","connected_agents":0}`

If you see that, the server is healthy. (Zero agents — that's right, the MacBook hasn't connected yet.)

---

## 5. MacBook Pro setup (the agent + the user)

### 5a. Get the code

```bash
cd ~
git clone <your-MSPclaw-repo-url> MSPclaw
cd MSPclaw
python3 -m venv .venv
source .venv/bin/activate
make install
```

### 5b. Configure the MacBook to find the Mac mini

```bash
cp .env.example .env
nano .env
```

Set these two lines (replace `192.168.1.42` with the IP you wrote down in step 3):

```
MSPCLAW_SERVER_URL=ws://192.168.1.42:8080/ws/agent
MSPCLAW_API_URL=http://192.168.1.42:8080
```

Notice: **no `GEMINI_API_KEY` on the MacBook.** The brain lives on the Mac mini only.

Same as before — comment out any `MSPCLAW_DB_URL=postgresql://` line.

Save.

### 5c. Start the agent

```bash
make agent
```

You should see:

```
INFO  mspclaw.agent.transport: connected to ws://192.168.1.42:8080/ws/agent
INFO  mspclaw.agent.transport: server ack received
```

Leave this terminal open.

### 5d. Confirm the Mac mini sees the MacBook

Back on the **Mac mini** in the second Terminal:

```bash
curl http://localhost:8080/health
```

Now expected: `{"status":"ok","connected_agents":1}`

Counted! The two machines are talking.

---

## 6. The actual test (does the AI work?)

Open a **third** Terminal on the **MacBook**:

```bash
cd ~/MSPclaw
source .venv/bin/activate
python -m enduser.cli issue "my mac is slow"
```

What happens, in plain English:

1. CLI sends "my mac is slow" to the Mac mini.
2. Mac mini parses it with Gemini → picks the `macos-slow` playbook.
3. Mac mini's brain decides "I should check system info."
4. Mac mini sends that request to the MacBook over the open WebSocket.
5. MacBook runs `psutil` locally, gets real CPU/memory numbers from your laptop.
6. MacBook sends results back to Mac mini.
7. Mac mini's brain reads the numbers, writes a recommendation.
8. CLI prints the recommendation.

**Expected output:**

```
MSPclaw resolved issue <some-uuid> via playbook macos-slow

Issue Summary: …
Diagnostics: CPU at X%, memory at Y%…
Recommended Fixes:
1. …
2. …
```

Total time: 5–15 seconds (depends on Gemini latency).

---

## 7. ⚠️ Known blocker — read before testing

A code review on 2026-04-26 found a real bug: the agent's tool files (`agent/tools/*.py`) were copied from an old project and use a `@tool` decorator from a library called CrewAI. The decorator wraps the function in a way our runner can't call. **Step 6 will crash on first dispatch** with something like `TypeError: 'Tool' object is not callable` or `ModuleNotFoundError: No module named 'crewai'`.

**Two options:**

- **Option A — fix first (recommended).** Ask Claude to dispatch a fix-pass subagent that strips the `@tool` decorators from `agent/tools/*.py`, aligns the catalog/registry tool list, fixes the dispatcher disconnect leak, fixes the `.env.example` Postgres URL, and wraps the Gemini call in `asyncio.to_thread`. ~30 minutes of work.
- **Option B — go now, see it break, then fix.** Useful if you want to confirm the network plumbing (steps 1–5) works on real hardware before touching code. You'll see the `connected_agents: 1` and the WebSocket dispatch arriving — the failure is purely on the agent's side when the tool runs.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `make: command not found` | macOS Command Line Tools missing | `xcode-select --install` |
| Mac mini's `connected_agents: 0` after starting agent | MacBook can't reach Mac mini | Check IP in step 3, confirm both on same Wi-Fi, try `ping <mac-mini-ip>` from MacBook |
| Agent log shows `connection error: …; reconnecting in Xs` | Server not running, wrong URL, or firewall | Confirm `make server` is alive; check macOS Firewall (System Settings → Network → Firewall → allow Python) |
| `/issues` returns `{"status": "no_playbook"}` | Issue text didn't match any playbook keyword | Try "my mac is slow" exactly — `playbooks/macos/slow.yaml` matches `slow`, `lag`, `cpu`, `memory` |
| `RuntimeError: GEMINI_API_KEY not set` | `.env` not loaded or key missing | On Mac mini, ensure `.env` is in the project root and `make server` was run from that directory |
| `httpx.ReadTimeout` from CLI | Gemini call slow or failing | Check Mac mini server logs for the actual error |
| Agent connects, dispatch arrives, then crashes | The blocker in section 7 | Fix that first |

---

## 9. After it works — Windows PC test

This is just to prove the server is portable. The Windows PC won't run the agent (the macOS-specific tools in `agent/tools/` won't work on Windows yet — that's a v1.0 item).

On the Windows PC:

```powershell
git clone <repo> $env:USERPROFILE\MSPclaw
cd $env:USERPROFILE\MSPclaw
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env   # set GEMINI_API_KEY, comment out the postgres URL
python -m server.main
```

From the MacBook, edit `.env`'s `MSPCLAW_SERVER_URL` and `MSPCLAW_API_URL` to point at the Windows PC's IP. Re-run `make agent` and the test in section 6.

---

## 10. What to capture during the test

Create a notes file as you go: `docs/test-runs/2026-04-27-mac-mini-macbook.md`. Capture:

- IPs / hostnames you used
- Exact `python -m enduser.cli issue "..."` text and the full output
- Latency (rough — "took 10 sec")
- Any errors and what fixed them
- Screenshots if anything looks broken

This becomes the proof that v0.1 works end-to-end on real hardware, and the input to the v0.2 plan.
