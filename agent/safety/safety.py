"""Command allowlists and path checks for dynamic fixes."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

# Read-only style commands; first argv[0] must be in this set.
_SAFE_COMMAND_BINS: frozenset[str] = frozenset(
    {
        "ps",
        "df",
        "sysctl",
        "vm_stat",
        "uptime",
        "top",
        "ioreg",
        "system_profiler",
        "sw_vers",
        "uname",
        "whoami",
        "id",
        "netstat",
        "ifconfig",
        "route",
        "ping",
        "osascript",
    }
)

_FORBIDDEN_SUBSTRINGS = ("sudo", "su ", "launchctl load", "chmod ", "chown ")


def is_safe_shell_command(command: str) -> tuple[bool, str]:
    """
    Reject shell metacharacters and disallowed binaries.
    ping is allowed only with -c for bounded count (enforced loosely).
    """
    raw = command.strip()
    if not raw:
        return False, "Empty command"
    lower = raw.lower()
    for bad in _FORBIDDEN_SUBSTRINGS:
        if bad in lower:
            return False, f"Forbidden pattern: {bad!r}"
    if any(ch in raw for ch in ";|&$`"):
        return False, "Shell metacharacters not allowed"
    try:
        parts = shlex.split(raw)
    except ValueError as e:
        return False, f"Invalid command: {e}"
    if not parts:
        return False, "No argv"
    exe = Path(parts[0]).name
    if exe not in _SAFE_COMMAND_BINS:
        return False, f"Binary not allowlisted: {exe}"
    if exe == "ping" and "-c" not in parts:
        return False, "ping requires -c (count) for safety"
    return True, ""


def is_path_allowed_for_fix(path_str: str, home: Path) -> bool:
    """Paths the dynamic fix may touch (user caches / tmp only)."""
    try:
        p = Path(path_str).expanduser().resolve()
    except OSError:
        return False
    home_r = home.resolve()
    allowed_roots = (
        home_r,
        Path("/tmp").resolve(),
        Path("/private/tmp").resolve(),
        home_r / "Library" / "Caches",
    )
    for root in allowed_roots:
        try:
            p.relative_to(root)
            return True
        except ValueError:
            continue
    return False


_SUDO_IN_STRING = re.compile(r"\bsudo\b", re.IGNORECASE)

# --- User-home path sandbox (read_file, get_folder_size, etc.) ---


def home_dir() -> Path:
    return Path.home().resolve()


def resolve_path_under_home(path_str: str, home: Path | None = None) -> Path | None:
    """Return resolved path only if it lies under the user's home directory."""
    h = (home or Path.home()).resolve()
    try:
        p = Path(path_str).expanduser().resolve()
    except OSError:
        return None
    try:
        p.relative_to(h)
        return p
    except ValueError:
        return None


_READ_MAX_BYTES = 2_000_000
_FOLDER_MAX_FILES = 120_000
_FOLDER_MAX_DEPTH = 25


def is_safe_write_path_under_home(path: Path, home: Path | None = None) -> tuple[bool, str]:
    """Block writes to credentials and keychain locations under home."""
    h = (home or Path.home()).resolve()
    try:
        rel = path.resolve().relative_to(h)
    except ValueError:
        return False, "path must be under home directory"
    parts = rel.parts
    if ".ssh" in parts:
        return False, "refusing writes under .ssh"
    if len(parts) >= 2 and parts[0] == "Library" and "Keychains" in parts:
        return False, "refusing writes under Library Keychains"
    if parts[0] == ".gnupg" or ".gnupg" in parts:
        return False, "refusing writes under .gnupg"
    return True, ""


# --- Broader shell (run_shell) after user types YES; still blocks obvious abuse ---

_RUN_SHELL_FORBIDDEN = re.compile(
    r"(sudo\b|su\s+-|rm\s+-rf\b|\bmkfs\b|\bdd\s+if=|/dev/(rdisk|disk)|"
    r"\bcurl\b|\bwget\b|bash\s+-c|sh\s+-c|\beval\b|`|\$\(|;\s*rm|\|\s*rm|&&\s*rm|"
    r">\s*/dev/|<\s*/dev/)",
    re.IGNORECASE,
)


def is_run_shell_command_allowed(command: str) -> tuple[bool, str]:
    """
    For run_shell after explicit YES. Stricter than nothing, looser than run_safe_command.
    Blocks pipes/semicolons/background to reduce one-shot injection.
    """
    raw = command.strip()
    if not raw:
        return False, "Empty command"
    if any(ch in raw for ch in ";|&`"):
        return False, "metacharacters ; | & ` not allowed in run_shell (use a single simple command)"
    if ">" in raw or "<" in raw:
        return False, "shell redirects not allowed in run_shell"
    if "$(" in raw or "${" in raw:
        return False, "command substitution not allowed"
    if _SUDO_IN_STRING.search(raw):
        return False, "sudo not allowed"
    if _RUN_SHELL_FORBIDDEN.search(raw):
        return False, "command matches forbidden pattern"
    return True, ""
