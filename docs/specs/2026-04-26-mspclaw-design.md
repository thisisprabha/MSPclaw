---
title: MSPclaw — AI-Native Open-Source RMM
date: 2026-04-26
status: draft
---

# MSPclaw Design Spec

## Vision

> The open-source AI-native RMM. MSP configures playbooks. AI reasons. Agent executes on the end-user's machine.

MSPclaw is positioned as the open-source alternative to proprietary RMMs (ConnectWise, NinjaOne, Kaseya) — but built AI-first, not script-first. It synthesizes three existing prototypes (pcfix, RepairCraft, OwnClaw) into a single platform with a clean client/server split.

## Target user

- **Primary buyer:** Small MSPs (50–200 client machines) running their own infrastructure.
- **Secondary user:** End-users on the client side who hit "issue" via the deployed CLI for self-service.

## Architecture

### Topology

```
End-user Mac          MSP Server                MSP Tech
─────────────         ──────────────────        ───────────
mspclaw-agent  ◄──WS──►  FastAPI brain   ◄──── msp-cli
                          + Postgres
                          + Playbooks
                          + Audit log
                              ▲
                              │
                          [Ticket / Email]
```

### Why this topology

- **AI brain on server, not client.** One LLM API key. Centralized audit. MSP controls cost. No client-side secret distribution.
- **Outbound WebSocket from agent.** Firewall-friendly. No inbound port required on the end-user's Mac. Real-time job dispatch without polling cost.
- **Playbooks-as-code.** YAML in git. MSPs version-control runbooks like infrastructure. Diffable, reviewable, rollback-able.
- **MCP-compatible tool interfaces.** The agent's tools speak a shape compatible with Model Context Protocol so a future migration to MCP doesn't break the client. v1 ships with custom WebSocket framing for simplicity.

## Components

### `server/` — MSP Server

FastAPI application. Single self-hostable deployment per MSP.

| Module | Responsibility | Source |
|---|---|---|
| `server/intake/` | Parse incoming tickets/CLI requests into structured issue objects | from OwnClaw `brain/llm.js` |
| `server/brain/` | ReAct reasoning loop; turns issue into ordered tool calls | from pcfix `agent/loop.py` |
| `server/playbooks/` | Load, validate, match YAML playbooks against issues | new |
| `server/connections/` | WebSocket manager; tracks connected agents per tenant | new |
| `server/storage/` | Postgres models — clients, jobs, playbook runs, audit | new (replaces SQLite) |
| `server/api/` | REST endpoints: tickets, clients, jobs, playbooks | new |

### `agent/` — Client Daemon

Lightweight Python daemon deployed to each end-user Mac. No LLM API key. No reasoning. Just executes what the server dispatches.

| Module | Responsibility | Source |
|---|---|---|
| `agent/tools/` | Diagnostic + execution tools (psutil, shell, dynamic Python) | from RepairCraft `tools/` |
| `agent/safety/` | AST validator, command allowlist, path rules | from pcfix `utils/safety.py` + RepairCraft `host_exec` |
| `agent/executor/` | Receives jobs, runs tools, streams results back | new |
| `agent/transport.py` | WebSocket client, reconnect logic, auth | new |

### `msp-cli/` — MSP-side Command Line

For MSP technicians. Pre-portal interface (web UI in v2).

```
msp-cli clients list
msp-cli clients status <client-id>
msp-cli playbook new --from-template macos-slow
msp-cli playbook validate ./playbooks/macos/slow.yaml
msp-cli job dispatch --client <id> --issue "outlook crashes"
msp-cli audit tail --client <id>
msp-cli roles assign --tech alice --level L2
```

### `playbooks/` — Resolution Playbooks

YAML format. Describe the *intent* of resolution, not the exact steps.

```yaml
# playbooks/macos/slow.yaml
id: macos-slow
match:
  keywords: [slow, sluggish, lag, freeze]
  os: macos
escalation:
  L1:
    intent: |
      Diagnose CPU/memory bottlenecks. Identify top hogs.
      Suggest closing apps. Do not modify system state.
    tools: [get_system_info, list_top_processes]
  L2:
    intent: |
      Clear user caches and restart heavy services.
      Require YES gate for any destructive action.
    tools: [get_system_info, list_top_processes, clear_user_cache, restart_service]
  L3:
    intent: |
      Deep diagnostics. May propose dynamic Python fixes.
      All destructive actions require MSP tech approval.
    tools: [*]
    requires_human_approval: true
```

The brain matches an incoming issue to a playbook, picks the right escalation level (based on user's role / repeat history), and uses the playbook's intent + tool whitelist to constrain its ReAct loop.

## Data model (Postgres)

```sql
tenants(id, name, created_at)
clients(id, tenant_id, machine_id, hostname, os, last_seen_at)
agents(id, client_id, agent_version, connected_at, ws_session_id)
issues(id, tenant_id, client_id, source, raw_text, parsed_issue, created_at)
jobs(id, issue_id, status, playbook_id, escalation_level, started_at, finished_at)
job_steps(id, job_id, step_no, tool, args, result, approved_by, ran_at)
playbooks(id, tenant_id, slug, yaml_blob, version, created_by, created_at)
roles(id, tenant_id, user_email, level)  -- L1/L2/L3
audit_log(id, tenant_id, actor, action, target, payload, ts)
```

## Job flow

1. **Issue arrives** (CLI on end-user Mac → server, or ticket email → intake parser).
2. Server creates an `issues` row. Intake module structures it (issue summary, possible causes, signals).
3. Brain looks up client → tenant → playbook match → escalation level.
4. Brain runs ReAct loop, constrained to playbook's tool whitelist.
5. For each tool call: server sends `dispatch` message over WebSocket to agent.
6. Agent validates (AST/allowlist), executes, streams `result` back.
7. If destructive + `requires_human_approval`, server pauses; MSP tech approves via `msp-cli`.
8. Final answer + audit log written. Issue marked resolved or escalated.

## Safety model

Inherited and tightened from pcfix + RepairCraft:

- **Allowlist, not denylist** — only known-safe binaries/modules.
- **AST validation** — all dynamic Python parsed and inspected before execution.
- **Subprocess isolation** — dynamic code never runs in agent process.
- **YES gate** — destructive actions require explicit confirmation (end-user OR MSP tech, per playbook).
- **No sudo, ever.** No exception.
- **Per-tenant tool scoping** — tenant A's playbook cannot invoke tools tenant B disabled.
- **Audit log is append-only.** Every tool call, approval, dispatch, result.

## v1 scope (what we build first)

- Server: FastAPI app with intake, brain, WebSocket dispatcher, Postgres storage.
- Agent: Python daemon, copies RepairCraft tools, WebSocket client, YES gate.
- CLI: `msp-cli clients list/status`, `playbook validate`, `job dispatch`, `audit tail`.
- Single tenant only. Multi-tenant schema present but not enforced.
- One playbook included: `macos-slow.yaml`.
- LLM: Gemini Flash (Ollama swap supported via env var).
- End-user entry: existing pcfix-style CLI, but it now talks to the server.

## v1 out of scope

- Web portal (CLI only).
- PSA integrations (ConnectWise, Autotask, Freshdesk).
- Windows / Linux agents.
- True multi-tenant enforcement.
- MCP protocol (interfaces are MCP-shaped; native MCP transport comes in v2).
- Billing, metering.

## Open questions

- Agent auth: client cert, signed token, or shared secret per tenant? *Decision needed before agent ships.*
- Playbook authoring UX: pure YAML, or YAML with a `msp-cli playbook new` scaffolder? *Recommend scaffolder.*
- Reconnect strategy: exponential backoff cap? *Default 60s.*

## Migration path from existing prototypes

1. Copy `RepairCraft/repaircraft/tools/*.py` → `MSPclaw/agent/tools/`.
2. Copy `pcfix/agent/loop.py` + `prompt.py` → `MSPclaw/server/brain/`.
3. Port `OwnClaw/brain/llm.js` ticket parsing logic to Python → `MSPclaw/server/intake/`.
4. Replace SQLite (`pcfix/agent/memory.py`) with Postgres equivalents.
5. Wrap pcfix CLI as a thin client that talks to server instead of running brain locally.
