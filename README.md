# MSPclaw

> The open-source AI-native RMM. MSP configures playbooks. AI reasons. Agent executes on the client Mac.

MSPclaw is a self-hosted Remote Monitoring & Management platform built AI-first. Unlike traditional RMMs (NinjaOne, ConnectWise, Kaseya) that bolt AI onto script runners, MSPclaw uses an LLM reasoning loop as its core orchestrator — playbooks describe intent, the agent decides the steps, and a deployed daemon executes them safely on the end-user's machine.

## Quickstart (macOS)

**On the MSP's Mac mini:**
```bash
git clone https://github.com/prabha-thats-it/MSPclaw.git ~/MSPclaw
cd ~/MSPclaw
```
Then double-click **`install-server.command`** in Finder. Pick a provider (`openai` default), paste your API key, done.

**On any requester's MacBook:**
```bash
git clone https://github.com/prabha-thats-it/MSPclaw.git ~/MSPclaw
cd ~/MSPclaw
```
Then double-click **`install-client.command`**. Enter the Mac mini's LAN address (e.g. `192.168.1.42:8080`), done.

```bash
mspclaw issue "my mac is slow"
```

Full guide: [docs/status/2026-04-28-quickstart.md](docs/status/2026-04-28-quickstart.md).

## Why MSPclaw

| Traditional RMM | MSPclaw |
|---|---|
| Proprietary, $$$ per endpoint | Open source, self-hosted |
| Scripts + monitoring | AI reasoning + structured playbooks |
| AI as an afterthought | AI-native from day 1 |
| Vendor lock-in | LLM-agnostic (Gemini, Claude, Ollama) |
| Closed protocols | MCP-compatible interfaces |

## Architecture

```
[Ticket / End-user CLI]
          │
          ▼
┌──────────────────────────┐
│      MSP Server          │   FastAPI + Postgres
│  ─ Intake (ticket parse) │
│  ─ Brain (ReAct loop)    │   ← from pcfix/agent/loop.py
│  ─ Playbook engine       │
│  ─ WebSocket dispatcher  │
└──────────┬───────────────┘
           │  WebSocket (outbound from agent)
           ▼
┌──────────────────────────┐
│   Client Agent (Mac)     │   Python daemon
│  ─ Tool executor         │   ← from RepairCraft/tools
│  ─ AST sandbox           │
│  ─ YES-gate              │
│  ─ Result reporter       │
└──────────────────────────┘

           ▲
           │
┌──────────┴───────────────┐
│       MSP CLI            │   manage clients,
│                          │   author playbooks,
│                          │   view audit log
└──────────────────────────┘
```

## Components

- **`server/`** — MSP-side FastAPI app. Holds the AI brain, ticket intake, playbook engine, and WebSocket job dispatcher.
- **`agent/`** — Lightweight Python daemon deployed to client Macs. Runs diagnostic tools, executes approved fixes, reports results.
- **`msp-cli/`** — Command-line tool for MSP technicians. List clients, create playbooks, dispatch jobs, view audit.
- **`playbooks/`** — YAML playbooks (version-controlled runbooks). MSPs define resolution intent; the AI fills in tool calls.

## Project lineage

MSPclaw synthesizes three predecessor projects:

| From | What was reused |
|---|---|
| **pcfix** (mac-trouble-shooter) | ReAct reasoning loop, AST sandbox |
| **RepairCraft** (pc-doc) | Tool ecosystem (telemetry, inventory, host_exec), KB, intent routing |
| **OwnClaw** (gpt-doc) | Ticket parsing, structured plan output, few-shot prompts |

The new code is the glue: client/server WebSocket protocol, multi-tenant data model, MSP CLI, playbook engine.

## Status

Skeleton phase. See [docs/specs/](docs/specs/) for the design.

## License

MIT (planned).
