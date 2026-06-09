# nanoLoop

Tiny autonomous engineering harness for startup tasks. Three layers:

| Layer | Piece | Role |
|-------|-------|------|
| Model | [OpenRouter](https://openrouter.ai) | One API, any tool-calling model. OpenAI-compatible → `ChatOpenAI` w/ custom `base_url`. |
| Orchestration | [LangChain DeepAgents](https://github.com/langchain-ai/deepagents) | Planning todo tool + role subagents w/ isolated context. |
| Runtime safety | [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) | Sandboxed exec, declarative policy, audit, privacy router. |

Workflow is [Gstack](https://github.com/garrytan/gstack)-inspired: **Plan → Build → Review → Test → Ship**, each phase a subagent. Sessions persist task memory across runs; human-in-the-loop gates are opt-in.

## Architecture

```
./run.sh "task"
   └─ openshell sandbox (policy.yaml) ──── filesystem / network / process gates + audit
        └─ nanoloop CLI  (nanoloop/main.py)
             └─ DeepAgents orchestrator   [OpenRouter: HARNESS_MODEL]
                  ├─ todo planning tool
                  ├─ tools: run_shell / read_file / write_file / human_review / track_task
                  └─ subagents (isolated context, HARNESS_SUBAGENT_MODEL)
                       planner · builder · reviewer · qa · shipper
```

OpenShell wraps the **whole process**, so the policy engine gates actions
out-of-process — the agent cannot escape its own sandbox by editing tool code.

## Install

From PyPI (once published):

```bash
pip install nanoloop
```

From source (editable dev):

```bash
python3.11 -m venv .venv && source .venv/bin/activate   # 3.11+ required
pip install -e .
cp .env.example .env        # add your OPENROUTER_API_KEY
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
```

## Run

```bash
chmod +x run.sh
./run.sh "Scaffold a FastAPI service with health check and a passing test"
```

Or call the installed CLI directly:

```bash
nanoloop "<task>"                  # new session, gates OFF (autonomous)
nanoloop new "<task>"
nanoloop interactive "<task>"      # gates ON: pause for y/n/guidance at key points
nanoloop resume <id> ["follow-up"] # continue a saved session (keeps task memory)
nanoloop list                      # list saved sessions
nanoloop show <id>                 # task log + human decisions
```

Without OpenShell installed, `run.sh` falls back to unsandboxed (dev only) and warns.

### Sessions & memory

Each run is a **Session** persisted to `./.nanoloop/sessions/<id>.json`: original goal,
task log (`pending → active → done/blocked`), human decisions, and a compact transcript.
`resume` injects that state back so the crew continues where it left off.

### Human-in-the-loop

Off by default (autonomous). Prefix any run command with `interactive` to enable
`human_review` gates at **plan-approval**, **pre-ship**, and when **blocked**. Equivalent
to `HARNESS_HITL=1`. Enabled gates still auto-approve (logged as `auto`) when there's no
tty, so non-interactive/sandbox runs never hang.

## Build the pip package

```bash
pip install build
python -m build          # → dist/nanoloop-0.1.0-py3-none-any.whl + .tar.gz
python -m twine upload dist/*   # publish to PyPI
```

## Layout

- `nanoloop/model.py` — OpenRouter `ChatOpenAI` factory
- `nanoloop/agents.py` — `create_deep_agent` w/ subagents + optional checkpointer
- `nanoloop/roles.py` — Gstack role prompts + orchestrator prompt
- `nanoloop/tools.py` — shell/file/`human_review`/`track_task` tools
- `nanoloop/session.py` — durable session + task memory
- `nanoloop/main.py` — streaming CLI w/ subcommands
- `policy.yaml` — OpenShell policy (default-deny; allowlist gateway + registries)

## Caveats

- Verify exact API surface against installed versions: DeepAgents `subagents=`
  schema and OpenShell `policy.yaml` keys evolve. Run `openshell policy validate policy.yaml`.
- DeepAgents needs Python ≥3.11.
