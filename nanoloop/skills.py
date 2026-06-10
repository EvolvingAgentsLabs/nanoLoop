"""Skills: reusable instruction packs loaded from ./Skills/.

A skill is a Markdown file with frontmatter:

    ---
    name: <slug>
    description: <when to use this skill>
    ---

    <step-by-step instructions the crew should follow>

Layout (either works):
    Skills/<name>.md
    Skills/<name>/SKILL.md      (directory form; can ship support files alongside)

The orchestrator sees the name+description of every skill up front, then calls
`use_skill(<name>)` to pull the full instructions into context on demand.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter

SKILLS_DIR = Path(os.environ.get("NANOLOOP_SKILLS_DIR", "Skills"))


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


def _candidates() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    found = list(SKILLS_DIR.glob("*.md"))
    found += list(SKILLS_DIR.glob("*/SKILL.md"))
    return found


def _load(path: Path) -> Skill:
    meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
    # Name: frontmatter wins; else dir name (SKILL.md) or file stem.
    name = meta.get("name")
    if not name:
        name = path.parent.name if path.name == "SKILL.md" else path.stem
    return Skill(name=name, description=meta.get("description", ""),
                 body=body, path=path)


def discover() -> list[Skill]:
    skills = [_load(p) for p in _candidates()]
    skills.sort(key=lambda s: s.name)
    return skills


def get(name: str) -> Skill | None:
    name = name.strip().lower()
    for s in discover():
        if s.name.lower() == name:
            return s
    return None


def catalog_text() -> str:
    """One line per skill (name: description) for the orchestrator prompt."""
    skills = discover()
    if not skills:
        return ""
    return "\n".join(f"- {s.name}: {s.description}" for s in skills)
