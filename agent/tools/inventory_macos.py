"""macOS read-only inventory tools for RepairCraft.

These tools are intended for *information only* (no writes). They may run a
small number of fixed OS commands (brew list, npm -g ls) and parse their
output, or scan a limited set of directories under user space.
"""

from __future__ import annotations

import os
import platform
import plistlib
import re
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

import psutil
from crewai.tools import tool


def _darwin_only(msg: str) -> str:
    return msg if platform.system() == "Darwin" else "Not supported on this OS."


def _run_fixed_cmd(args: list[str], timeout_s: int = 45) -> tuple[str, str, int]:
    """Run a fixed allowlisted command and capture stdout/stderr."""
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return p.stdout or "", p.stderr or "", int(p.returncode)
    except subprocess.TimeoutExpired:
        return "", "timeout", -1
    except OSError as e:
        return "", str(e), -1


def _iter_apps(app_roots: Iterable[Path]) -> Iterator[Path]:
    for root in app_roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            for ent in root.iterdir():
                if ent.is_dir() and ent.suffix.lower() == ".app":
                    yield ent
        except OSError:
            continue


def _read_app_info(app_path: Path) -> tuple[str, str] | None:
    """Return (name, bundle_id) for an *.app, or None if unreadable."""
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.exists():
        return None
    try:
        with info_plist.open("rb") as f:
            data = plistlib.load(f)
    except Exception:
        return None

    name = (
        data.get("CFBundleName")
        or data.get("CFBundleDisplayName")
        or app_path.stem
    )
    bundle_id = data.get("CFBundleIdentifier") or "unknown.bundle.id"
    return str(name), str(bundle_id)


@tool
def list_installed_apps() -> str:
    """List installed macOS apps from ~/Applications and /Applications.

    This is a read-only inventory (not exact “all apps on disk”).
    It scans only one directory level (each *.app folder) and reads Info.plist.
    """
    if platform.system() != "Darwin":
        return "list_installed_apps: Not supported on this OS."

    roots = [Path.home() / "Applications", Path("/Applications")]
    apps = []
    for app_dir in _iter_apps(roots):
        info = _read_app_info(app_dir)
        if not info:
            continue
        apps.append((info[0], info[1], str(app_dir)))

    apps.sort(key=lambda x: x[0].lower())
    limit = 200
    lines: list[str] = []
    lines.append(f"Installed apps scanned: {len(apps)} (showing first {min(limit, len(apps))})")
    for name, bundle_id, p in apps[:limit]:
        lines.append(f"- {name} ({bundle_id}) :: {p}")
    if len(apps) > limit:
        lines.append("... (truncated)")
    if not apps:
        lines.append("No apps found in scanned roots.")
    return "\n".join(lines)


@tool
def list_brew_installed() -> str:
    """List Homebrew-installed formulae/casks (if brew exists)."""
    if platform.system() != "Darwin":
        return "list_brew_installed: Not supported on this OS."

    brew = shutil.which("brew")
    if not brew:
        return "brew not found on PATH."

    out_f, err_f, code_f = _run_fixed_cmd(["brew", "list", "--formula", "--verbose"], timeout_s=60)
    out_c, err_c, code_c = _run_fixed_cmd(["brew", "list", "--cask", "--verbose"], timeout_s=60)

    if code_f != 0 and not out_f:
        return f"brew list (formula) failed: {err_f.strip() or out_f.strip() or 'unknown error'}"

    formulas = [ln.strip() for ln in out_f.splitlines() if ln.strip()]
    casks = [ln.strip() for ln in out_c.splitlines() if ln.strip()]

    formulas = sorted(set(formulas), key=lambda s: s.lower())
    casks = sorted(set(casks), key=lambda s: s.lower())

    def _fmt(items: list[str], title: str) -> list[str]:
        lim = 120
        lines_ = [f"{title}: {len(items)} (showing {min(lim, len(items))})"]
        for it in items[:lim]:
            lines_.append(f"- {it}")
        if len(items) > lim:
            lines_.append("... (truncated)")
        return lines_

    lines: list[str] = []
    lines.extend(_fmt(formulas, "brew formulae"))
    lines.append("")
    lines.extend(_fmt(casks, "brew casks"))
    return "\n".join(lines)


@tool
def list_npm_global_installed() -> str:
    """List global npm packages (if npm exists)."""
    if platform.system() != "Darwin":
        return "list_npm_global_installed: Not supported on this OS."

    npm = shutil.which("npm")
    if not npm:
        return "npm not found on PATH."

    # JSON is preferred because it's easier to parse than text output.
    out, err, code = _run_fixed_cmd(["npm", "-g", "ls", "--depth=0", "--json"], timeout_s=60)
    if code != 0 and not out:
        return f"npm global list failed: {err.strip() or out.strip() or 'unknown error'}"

    try:
        import json

        data = json.loads(out)
        deps = data.get("dependencies") or {}
        items: list[tuple[str, str]] = []
        for name, meta in deps.items():
            if name == "npm":
                continue
            if isinstance(meta, dict):
                ver = meta.get("version") or ""
            else:
                ver = ""
            items.append((name, str(ver)))
    except Exception as e:
        # Fallback: best-effort parsing from raw output.
        return f"Failed parsing npm JSON output: {type(e).__name__}: {e}\n--- raw ---\n{out[:8000]}"

    items.sort(key=lambda x: x[0].lower())
    lim = 150
    lines: list[str] = []
    lines.append(f"npm global packages: {len(items)} (showing first {min(lim, len(items))})")
    for name, ver in items[:lim]:
        lines.append(f"- {name}@{ver}" if ver else f"- {name}")
    if len(items) > lim:
        lines.append("... (truncated)")
    return "\n".join(lines) if lines else "No npm global packages found."


@dataclass
class _LastSeen:
    name: str
    last_seen: datetime


def _parse_lsappinfo_list(text: str) -> list[_LastSeen]:
    # Blocks look like:
    #  1) "AppName" ASN:... ...
    #      checkin time = 2026/03/09 08:07:15 ( ...)
    #
    # We capture the quoted name and the checkin time.
    name_re = re.compile(r'^\s*\d+\)\s+"([^"]+)"\s+ASN:', re.MULTILINE)
    checkin_re = re.compile(r"checkin time\s*=\s*(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})", re.MULTILINE)
    names = name_re.findall(text)
    checkins = checkin_re.findall(text)
    # If parsing fails/mismatch, return empty; we don't want to guess.
    if not names or not checkins or len(names) != len(checkins):
        return []
    out: list[_LastSeen] = []
    for n, (d, t) in zip(names, checkins):
        try:
            dt = datetime.strptime(f"{d} {t}", "%Y/%m/%d %H:%M:%S")
            out.append(_LastSeen(name=n, last_seen=dt))
        except ValueError:
            continue
    return out


@tool
def estimate_unused_apps(days: int = 30) -> str:
    """Best-effort estimate of apps “unused” for N days using lsappinfo checkin time.

    This is a proxy and may not match “usage” perfectly.
    """
    if platform.system() != "Darwin":
        return "estimate_unused_apps: Not supported on this OS."
    if days < 1:
        return "days must be >= 1."

    lsappinfo = shutil.which("lsappinfo")
    if not lsappinfo:
        return "lsappinfo not found on PATH; cannot estimate unused apps."

    out, err, code = _run_fixed_cmd(["lsappinfo", "list"], timeout_s=60)
    if code != 0 and not out:
        return f"lsappinfo list failed: {err.strip() or out.strip() or 'unknown error'}"

    parsed = _parse_lsappinfo_list(out)
    if not parsed:
        return "Could not parse lsappinfo output; returning unknown."

    cutoff = datetime.now() - timedelta(days=days)
    unused = [x for x in parsed if x.last_seen < cutoff]
    unused.sort(key=lambda x: x.last_seen)

    lim = 80
    lines: list[str] = []
    lines.append(f"Apps with last check-in older than {days} day(s): {len(unused)} (showing first {min(lim, len(unused))})")
    for x in unused[:lim]:
        lines.append(f"- {x.name} (last_seen={x.last_seen.isoformat(timespec='seconds')})")
    if len(unused) > lim:
        lines.append("... (truncated)")
    return "\n".join(lines)


@tool
def get_today_usage_proxies(hours: int = 24) -> str:
    """Best-effort “today usage” proxy from process start times.

    It reports running processes that started within the last N hours.
    (Without a tracker like ActivityWatch, this is an approximation.)
    """
    if hours < 1:
        return "hours must be >= 1."
    if platform.system() != "Darwin":
        return "get_today_usage_proxies: process-based proxy works on this OS, but tool is intended for macOS."

    now = datetime.now()
    cutoff = now - timedelta(hours=hours)

    items: list[tuple[str, int, datetime]] = []
    for p in psutil.process_iter(attrs=["pid", "name", "create_time"]):
        try:
            pid = int(p.info.get("pid"))
            name = (p.info.get("name") or "?")[:80]
            ct = p.info.get("create_time")
            if ct is None:
                continue
            started = datetime.fromtimestamp(float(ct))
            if started >= cutoff:
                items.append((str(name), pid, started))
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
            continue

    # Summarize by name first, and also show top PIDs.
    by_name: Counter[str] = Counter([n for n, _, _ in items])
    top_names = by_name.most_common(15)
    top_pids = sorted(items, key=lambda x: x[2], reverse=True)[:25]

    lines: list[str] = []
    lines.append(f"Process start proxy for last {hours}h: {len(items)} matching process instance(s)")
    lines.append("Top process names:")
    for name, cnt in top_names:
        lines.append(f"- {name}: {cnt} instance(s)")
    lines.append("")
    lines.append("Recent process instances (name, pid, started_at):")
    for name, pid, started in top_pids:
        lines.append(f"- {name} ({pid}) @ {started.isoformat(timespec='seconds')}")
    return "\n".join(lines)


@tool
def get_purchase_date_hint() -> str:
    """Return purchase-date hints (cannot be reliably read from macOS alone)."""
    if platform.system() != "Darwin":
        return "get_purchase_date_hint: Not supported on this OS."
    # macOS doesn’t reliably expose “when you bought it” in a trustworthy field.
    return "\n".join(
        [
            "Purchase date / when you bought the laptop: unknown (macOS typically does not store a reliable purchase date).",
            "",
            "Safe ways to estimate (read-only, user-side):",
            "- Check your email receipts (search: 'MacBook', 'order', 'receipt', your vendor name).",
            "- Check warranty/coverage: open 'About This Mac' → Serial Number → use Apple coverage lookup (Apple website).",
            "- If you bought via reseller, check their order history for the invoice date.",
        ]
    )

