---
name: agentvcs-merge
description: Use when the task asks to implement multidimensional `merge` and/or a decision-aware `log --reasoning` in the agentvcs project.
---

Implement two features in the **agentvcs** repo at
`/Users/agustinazwiener/evolvingagents/agentvcs` (Python 3, pure stdlib, ZERO
third-party runtime deps — do not add any). Source in `src/agentvcs/`, tests in
`tests/` (plain `unittest`/pytest style, run with
`/Users/agustinazwiener/evolvingagents/agentvcs/.venv/bin/python -m pytest tests/ -q`).

Hard rule: **agentvcs core never calls an LLM.** All intelligence (trace
reconciliation, decision summaries) is delegated to an external process via a
`--reconcile CMD` seam, exactly like the existing `replay(..., executor=CMD)`
hook in `replay.py`/`cli.py`. The core ships a deterministic fallback that works
with no CMD.

Study these first (they are the patterns to mirror):
- `repository.py` — `commit()` stores `parents: [list]` already; `log()` walks
  only `parents[0]`; `branch()`, `checkout()`, `rollback()`, `_resolve()`,
  `_restore_tree()`, object read/write via `self.objects`.
- `crystallize.py` — how to build a commit object by hand and `_set_head_commit`.
- `diff.py` — `diff_commits()` and the per-dimension two-way diff helpers.
- `cli.py` — subparser wiring (`add("branch")` ~L608, `add("replay")` ~L631),
  `_out()` JSON/human dual output, `_diff_human()`.
- `objects.py` — content-addressed `read_obj`/`write_obj`/`read_blob`/`write_blob`.

================================================================
FEATURE A — `agentvcs merge <branch> [--reconcile CMD] [--force] [--json]`
================================================================
New file `src/agentvcs/merge.py` exposing `merge(repo, branch, reconcile=None,
force=False) -> dict`. Add `Repository` helpers as needed.

1. Resolve `ours = repo.head_commit()`, `theirs = repo._resolve(branch,
   expect="commit")`. Error `code="NO_COMMITS"` if no head; `code="BAD_REF"` via
   `_resolve` if branch unknown. If `theirs` is an ancestor of `ours` →
   already-merged, return `{"status":"up_to_date"}`. If `ours` is an ancestor of
   `theirs` → fast-forward: move the branch ref, `_restore_tree`, done.

2. `merge_base(a_oid, b_oid)` — lowest common ancestor over the FULL parent DAG
   (follow ALL `parents`, not just parents[0]). BFS ancestors of `a` into a set,
   then BFS from `b` returning the first node already in that set (breadth order
   = nearest). Return None if no common ancestor. Pure stdlib.

3. Code three-way merge over tree `entries` ({path: blob_oid}) of base/ours/theirs:
   - path in only one side, or identical oids → take it.
   - `ours==theirs` → take it. `base==ours` → take theirs. `base==theirs` → take ours.
   - otherwise CONFLICT. For text blobs (decode utf-8; on UnicodeDecodeError treat
     as binary conflict) attempt a line-level 3-way using `difflib.SequenceMatcher`:
     auto-merge non-overlapping hunks; on overlap write git-style markers
     `<<<<<<< ours` / `=======` / `>>>>>>> theirs` into the blob and append
     `{path, reason}` to `conflicts`. Binary conflict → keep ours, record conflict.
   - Build the merged tree object and write it.

4. Models: union of the two commits' model pins, dedup by `provider/model`;
   same model with differing `params` → record a conflict note (keep ours' pin).

5. Reconciliation bundle (build always):
   {
     "base":   {"commit", "goal", "trace_messages"},
     "ours":   {"branch", "commit", "goal", "trace_messages", "code_diff"},
     "theirs": {"branch", "commit", "goal", "trace_messages", "code_diff"},
     "conflicts": [{"path","reason"}]
   }
   `code_diff` = `diff_commits(repo, base, side)["code"]`. `trace_messages` =
   the commit's trace object messages (or []).

   - If `reconcile` is None → deterministic fallback:
       merged_goal = "[merge] {ours_goal} + {theirs_goal}"
       merged_trace = [ {"role":"system","content":"KNOWLEDGE RECONCILIATION
         (mechanical): merged <ours_branch>@<short> + <theirs>@<short>. Both
         parent traces are preserved and reachable via this commit's two parents;
         no semantic reconciliation was performed."} ]
   - If `reconcile` is set → run it as a subprocess, write the bundle JSON to its
     stdin, read stdout, parse `{"goal": str, "trace": [{"role","content"}...],
     "notes": str}`. Validate shape; on bad/empty output fall back to the
     mechanical path and note it. (Use `subprocess.run(..., input=..., 
     capture_output=True, text=True)`. No shell=True; split CMD with shlex.)

6. Write the merge commit DIRECTLY (like crystallize): `type:"commit"`,
   `parents:[ours, theirs]`, `tree:<merged>`, `goal:<new goal obj>`,
   `models:<merged pins>`, `trace:<new trace obj or None>`, `state:"fluid"`,
   `metrics:{}`, `message` (default `f"merge {branch} into {current_branch}"`),
   `author`, `timestamp`. `_set_head_commit(new_oid)`.
   If `conflicts` and not `force` → DO NOT commit; instead write conflict-marked
   files into the working tree, and return
   `{"status":"conflict","conflicts":[...]}` with a non-zero CLI exit / 
   `{"ok":false,...}` JSON. With `--force`, commit anyway (state stays fluid).
   Freeze must remain blocked while conflict markers exist — add a cheap guard.

7. CLI: add subparser `add("merge")` with positional `name`/`branch`,
   `--reconcile` (metavar CMD), `--force`; `set_defaults(func=cmd_merge)`.
   `cmd_merge` mirrors `cmd_branch`/`cmd_diff` output style via `_out`.
   Export `merge` from `__init__.py` `__all__`. Add a `merge` tool to
   `mcp_server.py` alongside the others.

================================================================
FEATURE B — `agentvcs log --reasoning [--all] [--explain CMD]`
================================================================
1. Durable rollback ledger: in `repository.py` `rollback()`, in addition to
   writing `ROLLBACK_HEAD`, APPEND one JSON line to `.agentvcs/rollbacks.jsonl`:
   `{"from": previous_head, "to": target, "timestamp": int, "reason": <goal text of target>}`.
   Add `read_rollbacks() -> list[dict]`.

2. `log --reasoning`: walk history (first-parent; with `--all` include merge
   second-parents, dedup by oid). For each commit derive from on-disk facts ONLY:
   - goal transition vs its first parent (reuse `diff.py:_diff_goal`),
   - eval verdict/score via `repo.read_eval(oid)`,
   - state transition + crystallized flag, merge flag (len(parents)==2),
   - tier-1 "decision" text = goal delta if any else truncated last assistant
     message from the trace (no LLM).
   Interleave rollback-ledger events as `↩ ROLLBACK OCCURRED HERE` blocks keyed
   by the `from` commit, showing attempted decision + reason + restored-to.
   With `--explain CMD`, pipe each commit's thinking/assistant messages to CMD and
   read back a one-line `{"decision","why"}` (same subprocess pattern as merge).

3. Output shape (human) like:
       commit d4a897e080 [crystallized]
         Goal:     ...
         Decision: ...
         Proof:    ✓ Passed 'pytest -q' (score 1.0)   |  ✗ Failed ... (score 0.0)
   and the ROLLBACK block from the spec. `--json` emits a structured ledger list.
   Wire as flags on the EXISTING `log` subparser (`--reasoning`,`--all`,`--explain`);
   branch inside `cmd_log`.

================================================================
TESTS (add, keep style of existing tests/)
================================================================
`tests/test_merge.py`:
  - merge_base on a diamond DAG returns the true LCA.
  - clean three-way: file changed only on theirs is taken; only on ours is kept.
  - conflicting edit → markers present + `status==conflict` + no new commit
    without --force; with --force a 2-parent commit is created.
  - fallback trace contains the mechanical KNOWLEDGE RECONCILIATION marker.
  - `--reconcile` with a stub echo CMD (a tiny python -c that reads stdin JSON and
    prints `{"goal":"X","trace":[...] ,"notes":"t"}`) is used for the merge trace.
  - freeze blocked while conflict markers exist.
`tests/test_reasoning_log.py`:
  - goal transitions and eval verdicts render in the ledger.
  - two successive rollbacks both appear in `.agentvcs/rollbacks.jsonl` and in
    `log --reasoning --json`.

DONE = `/Users/agustinazwiener/evolvingagents/agentvcs/.venv/bin/python -m pytest tests/ -q`
is fully green (existing tests still pass + new ones). Keep vcs-mode commits
byte-identical for non-merge paths — only ADD behavior.
