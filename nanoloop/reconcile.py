"""Knowledge reconciliation for `agentvcs merge --reconcile`.

When two agent branches diverge, agentvcs merges the *code* deterministically and
hands the *reasoning* — a bundle of {base, ours, theirs} goals + message traces +
code diffs + conflicts — to an external process on stdin, expecting
``{goal, trace, notes}`` back on stdout. That seam keeps agentvcs's core free of
any LLM dependency.

This module is nanoLoop's implementation of that seam: it uses nanoLoop's own
OpenRouter model factory to synthesize a single, non-fragmented *Consolidated
Knowledge Trace* — the merged working memory an agent should resume from after the
merge, instead of two raw, contradictory chat logs concatenated together.

Exposed on the CLI as ``nanoloop reconcile [path/to/.env]`` (reads stdin, writes
stdout), so it drops straight into ``agentvcs merge <branch> --reconcile``.
"""
from __future__ import annotations

import json

from .model import make_model


SYSTEM = """You reconcile two divergent agent branches into ONE working memory.

You are given a merge bundle: a common-ancestor (base) goal+trace, and two
branches (ours/theirs) that evolved from it — each with its own goal, message
trace (the agent's reasoning), and code diff. The branches may have explored
different, even contradictory, approaches.

Do NOT concatenate the two traces. Synthesize. Produce a single Consolidated
Knowledge Trace that an agent resuming on the merged branch can read as coherent
working memory: what each branch was trying, what it learned, which decision
won and why, and what dead-ends to avoid re-exploring.

Return STRICT JSON, nothing else:
{
  "goal": "<the merged goal, one line>",
  "trace": [ {"role": "system"|"assistant", "content": "<one synthesized step>"}, ... ],
  "notes": "<one-line summary of how you reconciled>"
}
The trace should be 2-5 messages: a system summary of the reconciliation, then
assistant notes capturing the retained learning from each side."""


def _flatten(msgs):
    """Tolerate traces stored as a list-of-lists (e.g. a .jsonl line that is
    itself a JSON array) — normalize to a flat stream of message dicts."""
    for m in msgs or []:
        if isinstance(m, list):
            yield from _flatten(m)
        elif isinstance(m, dict):
            yield m


def _fmt_trace(msgs) -> str:
    out = []
    for m in _flatten(msgs):
        c = m.get("content", "")
        if isinstance(c, list):
            c = " ".join(str(x) for x in c)
        out.append(f"  [{m.get('role', '?')}] {c}")
    return "\n".join(out) or "  (none)"


def build_user_prompt(bundle: dict) -> str:
    b, o, t = bundle["base"], bundle["ours"], bundle["theirs"]
    return f"""BASE goal: {b.get('goal', '')}
BASE trace:
{_fmt_trace(b.get('trace_messages'))}

OURS branch '{o.get('branch', '')}' goal: {o.get('goal', '')}
OURS code diff: {json.dumps(o.get('code_diff', {}))}
OURS trace:
{_fmt_trace(o.get('trace_messages'))}

THEIRS branch '{t.get('branch', '')}' goal: {t.get('goal', '')}
THEIRS code diff: {json.dumps(t.get('code_diff', {}))}
THEIRS trace:
{_fmt_trace(t.get('trace_messages'))}

CONFLICTS: {json.dumps(bundle.get('conflicts', []))}

Reconcile these into one Consolidated Knowledge Trace. Return the strict JSON."""


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a model reply, tolerating code fences/prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model reply")
    return json.loads(text[start:end + 1])


def reconcile_bundle(bundle: dict) -> dict:
    """Synthesize a Consolidated Knowledge Trace from a merge bundle.

    Returns ``{goal: str, trace: list, notes: str}`` — exactly the shape
    ``agentvcs merge --reconcile`` validates and writes into the merge commit.
    """
    model = make_model(temperature=0.0)
    resp = model.invoke([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": build_user_prompt(bundle)},
    ])
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    parsed = _extract_json(text)
    return {
        "goal": parsed["goal"],
        "trace": parsed["trace"],
        "notes": parsed.get("notes", "reconciled by nanoLoop"),
    }
