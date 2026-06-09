"""CLI entrypoint. Run a startup task through the autonomous crew.

Intended to be launched inside the OpenShell sandbox via run.sh:
    openshell sandbox create --policy policy.yaml -- hardness "<task>"
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv
from rich.console import Console

from .agents import build_agent

console = Console()


def run(task: str) -> None:
    load_dotenv()
    agent = build_agent()
    console.rule("[bold]custom-hardness[/] — autonomous sprint")
    console.print(f"[dim]task:[/] {task}\n")

    # Stream the orchestration so progress is visible.
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": task}]},
        stream_mode="values",
    ):
        msgs = chunk.get("messages", [])
        if msgs:
            last = msgs[-1]
            content = getattr(last, "content", last)
            console.print(content)


def cli() -> None:
    if len(sys.argv) < 2:
        console.print("usage: hardness \"<startup task>\"")
        raise SystemExit(2)
    run(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    cli()
