"""Read-only macOS sensors for MSPclaw agent (subprocess allowlist only)."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

_SUBPROC_TIMEOUT = 45


def _run_allowlisted(args: list[str]) -> tuple[str, str, int]:
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        return p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", -1
    except OSError as e:
        return "", str(e), -1


def get_power_battery_info() -> str:
    """Read-only macOS power/battery summary: pmset + system_profiler (no writes).

    Returns cycle count, charge %, capacity fields when present. Not all Macs expose
    'maximum capacity %' — report unknowns honestly.
    """
    if platform.system() != "Darwin":
        return "get_power_battery_info: supported only on macOS (Darwin)."

    parts: list[str] = []

    out, err, code = _run_allowlisted(["pmset", "-g", "batt"])
    parts.append("=== pmset -g batt ===")
    parts.append(out.strip() or "(no stdout)")
    if err.strip():
        parts.append(f"stderr: {err.strip()}")
    parts.append(f"exit: {code}")

    out2, err2, code2 = _run_allowlisted(
        ["system_profiler", "SPPowerDataType", "-json"]
    )
    parts.append("\n=== system_profiler SPPowerDataType -json (excerpt) ===")
    if code2 == 0 and out2.strip():
        try:
            data = json.loads(out2)
            # Compact: battery dict only if present
            sp = data.get("SPPowerDataType", data)
            parts.append(json.dumps(sp, indent=2)[:12000])
            if len(json.dumps(sp)) > 12000:
                parts.append("\n… (truncated)")
        except json.JSONDecodeError:
            parts.append(out2[:8000])
    else:
        parts.append(out2.strip() or "(no stdout)")
        if err2.strip():
            parts.append(f"stderr: {err2.strip()}")
        parts.append(f"exit: {code2}")

    return "\n".join(parts)


def _safe_user_path(user_path: str) -> Path | None:
    home = Path.home().resolve()
    raw = user_path.strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (home / p).resolve()
    else:
        p = p.resolve()
    try:
        if os.path.commonpath([str(home), str(p)]) != str(home):
            return None
    except ValueError:
        return None
    if not str(p).startswith(str(home)):
        return None
    return p


def get_path_disk_usage(path: str) -> str:
    """Read-only shallow size summary for a path under the user home directory.

    Args:
        path: e.g. ~/Downloads, Downloads, or absolute path under your home.

    Returns:
        Total bytes (approximate shallow walk depth 2), top-level entry count, errors.
    """
    target = _safe_user_path(path)
    if target is None:
        return (
            "Invalid or disallowed path — must resolve under your home directory "
            "(no .. escape to system roots)."
        )
    if not target.exists():
        return f"Path does not exist: {target}"
    if target.is_file():
        sz = target.stat().st_size
        return f"Path: {target}\nFile size: {sz / (1024**3):.4f} GB ({sz} bytes)\n"

    def walk_limited(root: Path, max_depth: int, depth: int = 0) -> tuple[int, int, list[str]]:
        total = 0
        n_entries = 0
        errs: list[str] = []
        try:
            with os.scandir(root) as it:
                for ent in it:
                    n_entries += 1
                    try:
                        if ent.is_file(follow_symlinks=False):
                            total += ent.stat().st_size
                        elif ent.is_dir(follow_symlinks=False) and depth < max_depth:
                            sub, subn, e2 = walk_limited(
                                Path(ent.path), max_depth, depth + 1
                            )
                            total += sub
                            n_entries += subn
                            errs.extend(e2)
                    except OSError as e:
                        errs.append(f"{ent.path}: {e}")
        except OSError as e:
            errs.append(f"{root}: {e}")
        return total, n_entries, errs

    size, top_count, errs = walk_limited(target, max_depth=2)
    gb = size / (1024**3)
    msg = (
        f"Path: {target}\n"
        f"Approximate size (depth-limited walk): {gb:.2f} GB ({size} bytes)\n"
        f"Top-level entries scanned: {top_count}\n"
    )
    if errs:
        msg += f"Notes ({len(errs)}): " + "; ".join(errs[:5])
        if len(errs) > 5:
            msg += " …"
    return msg
