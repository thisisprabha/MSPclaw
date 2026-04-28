"""psutil-based system telemetry tools for MSPclaw agent."""

from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

import psutil


def _system_disk_path() -> str:
    if platform.system() == "Windows":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def get_system_stats() -> str:
    """Return CPU, RAM, and main disk usage as percentages with brief context."""
    cpu = psutil.cpu_percent(interval=0.5)
    vm = psutil.virtual_memory()
    disk_path = _system_disk_path()
    try:
        disk = psutil.disk_usage(disk_path)
        disk_pct = disk.percent
        disk_free_gb = disk.free / (1024**3)
    except OSError:
        disk_pct = -1.0
        disk_free_gb = -1.0
    return (
        f"CPU usage (approx): {cpu:.1f}%\n"
        f"RAM: {vm.percent:.1f}% used ({vm.used / (1024**3):.2f} GB / "
        f"{vm.total / (1024**3):.2f} GB)\n"
        f"Disk ({disk_path}): {disk_pct:.1f}% used"
        + (f", {disk_free_gb:.2f} GB free" if disk_free_gb >= 0 else " (unavailable)")
    )


def list_top_processes() -> str:
    """Return the top 5 processes by resident memory (RSS) with PID and name."""
    procs: list[tuple[int, str, float]] = []
    for p in psutil.process_iter(attrs=["pid", "name", "memory_info"]):
        try:
            info = p.info
            rss = info.get("memory_info")
            if rss is None:
                continue
            name = info.get("name") or "?"
            pid = int(info["pid"])
            procs.append((pid, name, rss.rss / (1024**2)))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x[2], reverse=True)
    lines = ["Top 5 by memory (MB):"]
    for pid, name, mb in procs[:5]:
        lines.append(f"  PID {pid}: {name} — {mb:.1f} MB")
    return "\n".join(lines) if len(lines) > 1 else "No process data available."


def _temp_dir_candidates() -> list[Path]:
    system = platform.system()
    raw: list[Path] = [Path(tempfile.gettempdir())]
    if system == "Darwin":
        raw.append(Path.home() / "Library" / "Caches")
        raw.append(Path("/tmp"))
    elif system == "Windows":
        for key in ("TEMP", "TMP", "LOCALAPPDATA"):
            v = os.environ.get(key)
            if v:
                p = Path(v)
                raw.append(p)
                if key == "LOCALAPPDATA":
                    raw.append(p / "Temp")
    else:
        raw.append(Path("/tmp"))
    seen: set[str] = set()
    out: list[Path] = []
    for p in raw:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _dir_size_limited(root: Path, max_depth: int = 2, _depth: int = 0) -> tuple[int, list[str]]:
    total = 0
    errors: list[str] = []
    if not root.exists():
        return 0, [f"Missing: {root}"]
    try:
        with os.scandir(root) as it:
            for ent in it:
                try:
                    if ent.is_file(follow_symlinks=False):
                        total += ent.stat().st_size
                    elif ent.is_dir(follow_symlinks=False) and _depth < max_depth:
                        sub, err = _dir_size_limited(
                            Path(ent.path), max_depth, _depth + 1
                        )
                        total += sub
                        errors.extend(err)
                except OSError as e:
                    errors.append(f"{ent.path}: {e}")
    except OSError as e:
        errors.append(f"{root}: {e}")
    return total, errors


def check_temp_files() -> str:
    """Estimate total size of common temp/cache directories (limited-depth walk)."""
    parts: list[str] = []
    for root in _temp_dir_candidates():
        size, errs = _dir_size_limited(root, max_depth=2)
        gb = size / (1024**3)
        status = f"{root}: ~{gb:.2f} GB (depth-limited scan)"
        if errs:
            status += f" [notes: {len(errs)} path(s) skipped or partial]"
        parts.append(status)
    return "\n".join(parts) if parts else "No temp directories found."
