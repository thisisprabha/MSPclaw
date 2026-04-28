# Playbook Authoring Guide

Playbooks tell MSPclaw **what kinds of issues to handle, what tools the AI is allowed to use, and how far it can escalate**. They are the MSP-controlled safety boundary — the AI literally cannot run any tool that isn't whitelisted by a matched playbook.

## Where playbooks live

```
playbooks/
  macos/
    slow.yaml             ← shipped example
    disk-space.yaml       ← your new one goes here
  windows/                ← v1.0
  linux/                  ← v1.0
```

Drop new YAML files anywhere under `playbooks/`. The loader recursively picks up every `*.yaml` file at server startup. To **reload after adding/editing** a playbook, restart the launchd-managed server:

```bash
launchctl unload ~/Library/LaunchAgents/com.mspclaw.server.plist
launchctl load   ~/Library/LaunchAgents/com.mspclaw.server.plist
```

(Hot-reload is on the v0.2 list.)

---

## Anatomy of a playbook (with the example dissected)

```yaml
id: macos-slow                                    # 1. unique identifier
description: Mac is slow — performance triage     # 2. human-readable label

match:                                            # 3. when does this apply?
  keywords: [slow, sluggish, lag, freeze]         #    case-insensitive substring match
  os: macos                                       #    optional OS gate

escalation:                                       # 4. tiered scopes — L1/L2/L3
  L1:
    intent: |                                     # 5. plain-English goal fed to the brain
      Diagnose CPU/memory bottlenecks.
      Identify top resource hogs.
    tools:                                        # 6. whitelist — brain CANNOT call others
      - get_system_info
      - list_top_processes
      - check_disk_usage

  L2:
    intent: |
      In addition to L1: clear user-level caches.
    tools:
      - get_system_info
      - list_top_processes
      - check_temp_files
      - run_safe_command
    requires_human_approval: false                # 7. v0.2 — MSP tech must approve

  L3:
    intent: |
      Deep diagnostics. ALL destructive actions need MSP approval.
    tools:
      - "*"                                       # 8. wildcard — every registered tool
    requires_human_approval: true
```

### Field reference

| # | Field | Required | Notes |
|---|---|---|---|
| 1 | `id` | yes | Use `kebab-case`. Must be unique across all playbooks. Stored on each job in the DB. |
| 2 | `description` | optional | Used by the MSP CLI's `playbook validate` command. |
| 3 | `match.keywords` | yes (≥1) | Lowercase substrings. Match score = how many keywords appear in the parsed issue. Highest scorer wins. |
| 3 | `match.os` | optional | `macos` / `windows` / `linux`. Filters out non-matching clients. Omit to match any OS. |
| 4 | `escalation` | yes (≥1 level) | Use `L1`, `L2`, `L3`. The end-user CLI submits at `L1` by default; MSP can override. |
| 5 | `intent` | yes | Multi-line YAML scalar — feeds straight into the brain's prompt. Be specific about goals AND constraints ("read-only", "no sudo", "ask user before X"). |
| 6 | `tools` | yes (≥1) | Whitelist by exact tool name. See **Available tools** below. |
| 7 | `requires_human_approval` | optional | Reserved for v0.2 MSP-side approval flow. Set `true` on destructive levels. |
| 8 | `tools: ["*"]` | special | Wildcard. Allows any registered agent tool. Reserve for L3 with strict approval. |

### How matching works (in plain English)

1. End-user submits `"my mac is slow"`.
2. OpenAI parses it → `{ "issue": "Mac performance is slow", ... }`.
3. Matcher loops every playbook:
   - Skip if `match.os` is set and doesn't match the client's OS.
   - Score = count of `match.keywords` that appear (case-insensitively) in `issue`.
4. Highest-scoring playbook wins. Score 0 = no match → server returns `{"status": "no_playbook", "plan": ...}` and the user sees the parsed plan but no automation runs.
5. Server passes `intent` + `tools` (for the chosen level, default `L1`) to the orchestrator. The brain is now constrained: it can ONLY call tools in that list.

---

## Available tools (v0.1)

These are the names you can put under `tools:` in any playbook. They map to functions in `agent/tools/*.py`. Adding new tools needs Python code (see "Extending tools" below).

| Tool name | What it does | Args | Destructive? |
|---|---|---|---|
| `get_system_info` | CPU %, RAM %, main disk usage snapshot | none | no |
| `list_top_processes` | Top N processes by CPU or memory | `limit: int (default 5)`, `sort_by: cpu \| mem` | no |
| `check_disk_usage` | Per-path disk usage breakdown | `path: string (default "/")` | no |
| `check_temp_files` | Estimate temp/cache directory sizes | none | no |
| `list_installed_apps` | Inventory of installed macOS apps | none | no |
| `list_brew_installed` | Homebrew formulae + casks | none | no |
| `get_power_battery_info` | Battery health + power source | none | no |
| `run_safe_command` | Run an allowlisted read-only shell command | `cmd: string` | controlled — built-in denylist for sudo, rm -rf /, mkfs, dd, shutdown, fork bombs, etc. |

---

## Three example playbooks you might write next

### `playbooks/macos/disk-space.yaml`

```yaml
id: macos-disk-space
description: Mac is running out of disk space
match:
  keywords: [disk, space, storage, full, "out of space", apps, "too many"]
  os: macos

escalation:
  L1:
    intent: |
      Identify what's eating disk space on this Mac. Report largest
      consumers (apps, caches, temp files) and recommend safe cleanup
      steps the user can do themselves. Read-only.
    tools:
      - check_disk_usage
      - check_temp_files
      - list_installed_apps
      - list_brew_installed

  L2:
    intent: |
      In addition to L1: run `du -sh ~/Library/Caches` and similar
      read-only inspection commands to localize the bloat.
    tools:
      - check_disk_usage
      - check_temp_files
      - list_installed_apps
      - run_safe_command
```

### `playbooks/macos/battery.yaml`

```yaml
id: macos-battery
description: Battery health / drain issues
match:
  keywords: [battery, drain, draining, charge, charging, "won't charge", power]
  os: macos

escalation:
  L1:
    intent: |
      Report battery health, current charge, and power source.
      Identify any high-CPU process that might be draining the battery.
      Suggest power-saving steps (close apps, reduce brightness).
    tools:
      - get_power_battery_info
      - list_top_processes
      - get_system_info
```

### `playbooks/macos/wifi.yaml`

```yaml
id: macos-wifi
description: Network / Wi-Fi connectivity problems
match:
  keywords: [wifi, "wi-fi", network, internet, "no internet", offline, slow internet, "can't connect"]
  os: macos

escalation:
  L1:
    intent: |
      Diagnose Wi-Fi connectivity. Check connection status, signal,
      and DNS resolution via read-only shell commands. Don't change
      any network settings without escalation.
    tools:
      - run_safe_command
      - get_system_info
```

---

## Validating a playbook before shipping it

The MSP CLI has a validator:

```bash
python msp-cli/main.py playbook validate playbooks/macos/disk-space.yaml
```

Expected output:

```
ok: playbook macos-disk-space is valid
+--------------------+
| Escalation levels  |
+-------+------------+
| Level | Tools      | Approval |
| L1    | …          | no       |
| L2    | …          | no       |
+-------+------------+
```

If you get `invalid: missing keys [...]`, you're missing one of: `id`, `match`, `escalation`. Add it.

---

## Tips for writing good playbooks

1. **Keywords are matched as substrings, lowercased.** `slow` matches "my mac feels slow" and "slowness." Don't pluralize redundantly.
2. **Pick keywords your users actually use.** Watch the parsed `issue` field in `{"status": "no_playbook"}` responses — those are missed-match opportunities.
3. **L1 should always be read-only.** Users self-serve at L1. Anything that changes state goes to L2+.
4. **`intent` is the brain's compass.** If the recommendations are too vague or too aggressive, tighten the intent text. The LLM follows it.
5. **`tools: ["*"]` is a footgun.** Reserve for L3 + `requires_human_approval: true`. Otherwise the brain can reach for `run_safe_command` and surprise you.
6. **Multiple playbooks can have overlapping keywords** — highest score wins. So a more specific playbook with more matching keywords beats a general one.

---

## Extending tools (when YAML alone isn't enough)

If your playbook needs a tool that doesn't exist yet (e.g., `restart_service`, `clear_dns_cache`):

1. Add the function to a file in `agent/tools/` — must be a plain callable that returns a JSON-serializable result.
2. Register it in `agent/executor/runner.py` → `_registry()`.
3. Add a description to `server/brain/tool_catalog.py` so the brain knows about it.
4. Reference it by name in your playbook's `tools:` list.

That's a code change — outside the YAML-only authoring loop. Aim to keep adding playbooks for ~80% of new issue types; only extend tools when you genuinely need new capability on the agent.

---

## Pushing your playbooks back to the team

```bash
git add playbooks/macos/disk-space.yaml
git commit -m "playbook: macos disk-space triage"
git push
```

Then on the Mac mini server:

```bash
cd ~/MSPclaw
git pull
launchctl unload ~/Library/LaunchAgents/com.mspclaw.server.plist
launchctl load   ~/Library/LaunchAgents/com.mspclaw.server.plist
```

New playbook is live. No code review needed — it's just YAML.
