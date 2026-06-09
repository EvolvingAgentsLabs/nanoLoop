"""Tools for the harness.

Shell + file tools. Safe under OpenShell: every subprocess the agent spawns is
already inside the OpenShell sandbox (the whole process is launched with
`openshell sandbox create -- hardness ...`), so the OpenShell policy engine
gates filesystem/network/process actions out-of-process. These tools do NOT
reimplement policy — they trust the sandbox boundary.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from langchain_core.tools import tool

# Workspace root — all file/shell actions confined here. Defaults to ./workspace
# under the current dir. Absolute paths from the model are remapped inside it.
WORKDIR = Path(os.environ.get("HARNESS_WORKDIR", "./workspace")).resolve()


def _resolve(path: str) -> Path:
    """Map any model-supplied path to a safe location inside WORKDIR."""
    WORKDIR.mkdir(parents=True, exist_ok=True)
    p = Path(path)
    # Strip leading slash / drive so absolute paths land inside the workspace.
    rel = Path(*[part for part in p.parts if part not in ("/", p.anchor)])
    target = (WORKDIR / rel).resolve()
    # Block path-traversal escapes.
    if not str(target).startswith(str(WORKDIR)):
        raise ValueError(f"path escapes workspace: {path}")
    return target


@tool
def run_shell(command: str, timeout: int = 120) -> str:
    """Run a shell command and return combined stdout/stderr.

    Runs inside the OpenShell sandbox; disallowed actions are blocked by policy.
    """
    WORKDIR.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKDIR),
        )
    except subprocess.TimeoutExpired:
        return f"[timeout after {timeout}s] {command}"
    except OSError as e:
        return f"[error] {e}"
    out = (proc.stdout or "") + (proc.stderr or "")
    return f"[exit {proc.returncode}]\n{out}".strip()


@tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the workspace."""
    try:
        p = _resolve(path)
    except ValueError as e:
        return f"[error] {e}"
    if not p.exists():
        return f"[not found] {path}"
    return p.read_text(encoding="utf-8", errors="replace")


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in the workspace, creating parent dirs."""
    try:
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"[error] {e}"
    return f"[wrote {len(content)} bytes] {p.relative_to(WORKDIR)}"


HARNESS_TOOLS = [run_shell, read_file, write_file]
