#!/usr/bin/env bash
# Launch the harness INSIDE the OpenShell sandbox so every action the agent
# takes is gated by policy.yaml, sandboxed, and audited.
set -euo pipefail

TASK="${*:-}"
if [[ -z "$TASK" ]]; then
  echo "usage: ./run.sh \"<startup task>\"" >&2
  exit 2
fi

# Fallback: if OpenShell isn't installed, warn and run unsandboxed (dev only).
if ! command -v openshell >/dev/null 2>&1; then
  echo "WARNING: openshell not found — running WITHOUT sandbox (dev only)." >&2
  echo "Install: curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh" >&2
  exec hardness "$TASK"
fi

exec openshell sandbox create --policy policy.yaml -- hardness "$TASK"
