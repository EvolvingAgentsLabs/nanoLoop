"""CLI entrypoint. Run a startup task through the autonomous crew.

Launched inside the OpenShell sandbox via run.sh:
    openshell sandbox create --policy policy.yaml -- nanoloop "<task>"

Commands:
    nanoloop "<task>"          start a new session for <task>
    nanoloop new "<task>"      same, explicit
    nanoloop resume <id>       continue a saved session (keeps task memory)
    nanoloop resume <id> "<follow-up>"   resume and add a new instruction
    nanoloop list              list saved sessions
    nanoloop show <id>         print a session's task log + decisions

Human-in-the-loop is OFF by default. Prefix any run command with `interactive`
to enable gates (plan-approval, pre-ship, blocked); the crew then pauses for your
y/n/guidance. Equivalent to HARNESS_HITL=1.
    nanoloop interactive "<task>"
    nanoloop interactive resume <id>
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from rich.console import Console

from .agents import build_agent
from .session import Session
from .tools import set_session

console = Console()


def _checkpointer():
    """In-process conversation memory. Durable task memory lives in Session."""
    try:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    except Exception:
        return None


def _drive(session: Session, prompt: str) -> None:
    load_dotenv()
    set_session(session)
    agent = build_agent(checkpointer=_checkpointer())

    console.rule("[bold]nanoLoop[/] — autonomous sprint")
    console.print(f"[dim]session:[/] {session.id}  [dim]goal:[/] {session.goal}\n")

    config = {"configurable": {"thread_id": session.id}}
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        config=config,
        stream_mode="values",
    ):
        msgs = chunk.get("messages", [])
        if msgs:
            last = msgs[-1]
            content = getattr(last, "content", last)
            role = getattr(last, "type", "msg")
            console.print(content)
            if isinstance(content, str) and content.strip():
                session.log(role, content)
    console.print(f"\n[dim]saved → {session.path}[/]")


def _cmd_list() -> None:
    rows = Session.list_all()
    if not rows:
        console.print("[dim]no sessions[/]")
        return
    for s in rows:
        done = sum(1 for t in s.tasks if t.status == "done")
        console.print(f"[bold]{s.id}[/]  {done}/{len(s.tasks)} done  — {s.goal}")


def _cmd_show(sid: str) -> None:
    s = Session.load(sid)
    console.print(f"[bold]{s.id}[/] — {s.goal}")
    console.print("\n[bold]tasks[/]")
    for t in s.tasks:
        console.print(f"  [{t.status}] {t.title}" + (f" — {t.note}" if t.note else ""))
    console.print("\n[bold]decisions[/]")
    for d in s.decisions:
        console.print(f"  {d.gate}: {d.verdict} ({d.action}) {d.note}")


def cli() -> None:
    argv = sys.argv[1:]
    # `interactive` prefix enables human-in-the-loop gates (off by default).
    if argv and argv[0] == "interactive":
        argv = argv[1:]
        os.environ["HARNESS_HITL"] = "1"

    if not argv:
        console.print(__doc__)
        raise SystemExit(2)

    cmd = argv[0]

    if cmd == "list":
        _cmd_list()
        return
    if cmd == "show":
        if len(argv) < 2:
            console.print("usage: nanoloop show <id>")
            raise SystemExit(2)
        _cmd_show(argv[1])
        return
    if cmd == "resume":
        if len(argv) < 2:
            console.print("usage: nanoloop resume <id> [\"follow-up\"]")
            raise SystemExit(2)
        session = Session.load(argv[1])
        follow_up = " ".join(argv[2:]).strip()
        prompt = session.context_brief()
        if follow_up:
            prompt += f"\n\nNew instruction: {follow_up}"
        else:
            prompt += "\n\nContinue from where the task log left off."
        _drive(session, prompt)
        return
    if cmd == "new":
        goal = " ".join(argv[1:]).strip()
    else:
        goal = " ".join(argv).strip()

    if not goal:
        console.print("usage: nanoloop \"<startup task>\"")
        raise SystemExit(2)
    session = Session.create(goal)
    _drive(session, goal)


if __name__ == "__main__":
    cli()
