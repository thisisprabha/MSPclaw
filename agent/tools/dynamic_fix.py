"""Approval-gated dynamic Python execution with AST validation and timeout."""

from __future__ import annotations

import ast
import multiprocessing
import os
import re
import textwrap
from typing import Any

ALLOWED_MODULES = frozenset({"psutil", "subprocess", "os", "shutil", "json", "sys"})

_SUDO_IN_STRING = re.compile(r"\bsudo\b", re.IGNORECASE)

_FORBIDDEN_AST_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
    }
)


class _CodeSafetyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            base = alias.name.split(".")[0]
            if base not in ALLOWED_MODULES:
                self.errors.append(f"import not allowed: {alias.name}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            self.errors.append("from-import without module")
            return
        base = node.module.split(".")[0]
        if base not in ALLOWED_MODULES:
            self.errors.append(f"from-import not allowed: {node.module}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
            self.errors.append("access to __builtins__ not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _FORBIDDEN_AST_NAMES:
            self.errors.append(f"name not allowed: {node.id}")

    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func
        if isinstance(fn, ast.Attribute):
            owner = fn.value
            attr = fn.attr
            if isinstance(owner, ast.Name) and owner.id == "os" and attr in (
                "system",
                "popen",
                "posix_spawn",
                "spawnlp",
                "spawnvp",
                "execl",
                "execle",
                "execlp",
                "execv",
                "execve",
                "open",
            ):
                self.errors.append(f"os.{attr} not allowed")
            if isinstance(owner, ast.Name) and owner.id == "shutil" and attr in (
                "rmtree",
                "move",
                "copytree",
            ):
                self.errors.append(f"shutil.{attr} not allowed")
            if isinstance(owner, ast.Name) and owner.id == "subprocess" and attr in (
                "call",
                "run",
                "Popen",
                "check_output",
                "check_call",
            ):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        self.errors.append("subprocess with shell=True not allowed")
        self.generic_visit(node)


def validate_dynamic_code(code: str) -> tuple[bool, str]:
    if _SUDO_IN_STRING.search(code):
        return False, "code contains 'sudo'"
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    v = _CodeSafetyVisitor()
    v.visit(tree)
    if v.errors:
        return False, "; ".join(v.errors)
    return True, ""


def _restricted_builtins() -> dict[str, Any]:
    def _safe_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):  # type: ignore[no-untyped-def]
        base = str(name).split(".")[0]
        if base not in ALLOWED_MODULES:
            raise ImportError(f"import not allowed: {name}")
        return __import__(name, globals, locals, fromlist, level)

    return {
        "__builtins__": {
            "None": None,
            "True": True,
            "False": False,
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "isinstance": isinstance,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "print": print,
            "range": range,
            "repr": repr,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "Exception": Exception,
            "ValueError": ValueError,
            "RuntimeError": RuntimeError,
            "OSError": OSError,
            "__import__": _safe_import,
        }
    }


def _worker_run(code: str, queue: multiprocessing.Queue) -> None:
    import json as json_m
    import os as os_m
    import shutil as shutil_m
    import subprocess as subprocess_m
    import sys as sys_m

    import psutil as psutil_m

    g = _restricted_builtins()
    g.update(
        {
            "psutil": psutil_m,
            "subprocess": subprocess_m,
            "os": os_m,
            "shutil": shutil_m,
            "json": json_m,
            "sys": sys_m,
        }
    )
    try:
        exec(compile(code, "<dynamic_fix>", "exec"), g, g)
        queue.put(("ok", ""))
    except Exception as e:
        queue.put(("err", f"{type(e).__name__}: {e}"))


def execute_dynamic_fix(code: str, approved: bool) -> str:
    if not approved:
        return "Observation: User declined execution of dynamic fix."
    ok, reason = validate_dynamic_code(code)
    if not ok:
        return f"Observation: Code rejected: {reason}"
    ctx = multiprocessing.get_context("fork")
    q: multiprocessing.Queue = ctx.Queue()
    proc = ctx.Process(target=_worker_run, args=(code, q))
    proc.start()
    proc.join(timeout=30)
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
        return "Observation: Dynamic fix timed out (30s) and was killed."
    try:
        kind, payload = q.get_nowait()
    except Exception:
        return "Observation: No result from worker (crashed?)"
    if kind == "ok":
        return "Observation: Dynamic fix finished without uncaught exception."
    return f"Observation: {payload}"


def preview_wrapped(code: str) -> str:
    return textwrap.dedent(code).strip()


def is_dynamic_fix_approved() -> bool:
    return os.environ.get("REPAIRCRAFT_DYNAMIC_FIX_APPROVED", "0") == "1"


def run_dynamic_fix_code(code: str) -> str:
    """Run LLM-generated Python only when explicitly approved for this run."""
    approved = is_dynamic_fix_approved()
    return execute_dynamic_fix(preview_wrapped(code), approved=approved)
