"""Reconciler contract: prompt content, JSON extraction, resolved_files passthrough.

The model is mocked, so these run offline (no OPENROUTER_API_KEY needed) and pin
the `agentvcs merge --reconcile` contract: {goal, trace, notes, resolved_files?}.
"""
from __future__ import annotations

import json

import nanoloop.reconcile as rec


class _FakeResp:
    def __init__(self, content: str):
        self.content = content


class _FakeModel:
    """Records the messages it was invoked with and returns a canned reply."""
    def __init__(self, reply: str):
        self._reply = reply
        self.last_messages = None

    def invoke(self, messages):
        self.last_messages = messages
        return _FakeResp(self._reply)


def _bundle(**over) -> dict:
    b = {
        "base": {"goal": "refund bot", "trace_messages": []},
        "ours": {"branch": "runtime", "goal": "screen fraud",
                 "metrics": {"eval_score": 0.9, "eval_ok": True},
                 "code_diff": {}, "trace_messages": []},
        "theirs": {"branch": "main", "goal": "30-day window",
                   "metrics": {"eval_score": 0.7, "eval_ok": True},
                   "code_diff": {}, "trace_messages": []},
        "conflicts": [],
        "conflict_files": [],
    }
    b.update(over)
    return b


def _patch(monkeypatch, reply: str) -> _FakeModel:
    fake = _FakeModel(reply)
    monkeypatch.setattr(rec, "make_model", lambda **_: fake)
    return fake


def test_prompt_carries_target_goal_and_metrics(monkeypatch):
    fake = _patch(monkeypatch, json.dumps({"goal": "g", "trace": [], "notes": "n"}))
    rec.reconcile_bundle(_bundle(target_goal="prioritize fraud safety"))
    user = fake.last_messages[1]["content"]
    assert "prioritize fraud safety" in user        # directed-merge objective
    assert '"eval_score": 0.9' in user               # ours metrics surfaced
    assert '"eval_score": 0.7' in user               # theirs metrics surfaced


def test_resolved_files_passthrough(monkeypatch):
    reply = json.dumps({
        "goal": "g", "trace": [{"role": "system", "content": "merged"}],
        "notes": "union", "resolved_files": {"skills/refund-policy.md": "both rules"},
    })
    _patch(monkeypatch, reply)
    out = rec.reconcile_bundle(_bundle(conflict_files=[{"path": "skills/refund-policy.md"}]))
    assert out["resolved_files"] == {"skills/refund-policy.md": "both rules"}
    assert out["goal"] == "g" and out["notes"] == "union"


def test_empty_resolved_files_omitted(monkeypatch):
    _patch(monkeypatch, json.dumps({"goal": "g", "trace": [], "resolved_files": {}}))
    out = rec.reconcile_bundle(_bundle())
    assert "resolved_files" not in out               # no conflicts → key omitted
    assert out["notes"] == "reconciled by nanoLoop"  # default note


def test_extract_json_tolerates_code_fence(monkeypatch):
    _patch(monkeypatch, "```json\n{\"goal\": \"g\", \"trace\": []}\n```")
    out = rec.reconcile_bundle(_bundle())
    assert out["goal"] == "g"
