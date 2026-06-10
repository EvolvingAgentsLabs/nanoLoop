#!/usr/bin/env bash
# Launch the harness INSIDE the OpenShell sandbox so every action the agent
# takes is gated by policy.yaml, sandboxed, and audited.
set -euo pipefail

TASK="${*:-}"
if [[ -z "$TASK" ]]; then
  echo "usage: ./run.sh \"<startup task>\"" >&2
  exit 2
fi

# Resolve how to invoke nanoloop. Prefer a local venv, then an installed
# console script, then `python -m nanoloop` (works without activating a venv).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$HERE/.venv/bin/nanoloop" ]]; then
  RUN=("$HERE/.venv/bin/nanoloop")
elif command -v nanoloop >/dev/null 2>&1; then
  RUN=(nanoloop)
else
  PY="python3"
  [[ -x "$HERE/.venv/bin/python" ]] && PY="$HERE/.venv/bin/python"
  RUN=("$PY" -m nanoloop)
fi

# Fallback: if OpenShell isn't installed, warn and run unsandboxed (dev only).
if ! command -v openshell >/dev/null 2>&1; then
  echo "WARNING: openshell not found — running WITHOUT sandbox (dev only)." >&2
  echo "Install: curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh" >&2
  exec "${RUN[@]}" "$TASK"
fi

exec openshell sandbox create --policy policy.yaml -- "${RUN[@]}" "$TASK"
