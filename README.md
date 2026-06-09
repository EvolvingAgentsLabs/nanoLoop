# custom-hardness

Autonomous engineering harness for startup tasks. Three layers:

| Layer | Piece | Role |
|-------|-------|------|
| Model | [OpenRouter](https://openrouter.ai) | One API, any tool-calling model. OpenAI-compatible → `ChatOpenAI` w/ custom `base_url`. |
| Orchestration | [LangChain DeepAgents](https://github.com/langchain-ai/deepagents) | Planning todo tool + role subagents w/ isolated context. |
| Runtime safety | [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) | Sandboxed exec, declarative policy, audit, privacy router. |

Workflow is [Gstack](https://github.com/garrytan/gstack)-inspired: **Plan → Build → Review → Test → Ship**, each phase a subagent.

## Architecture

```
./run.sh "task"
   └─ openshell sandbox (policy.yaml) ──── filesystem / network / process gates + audit
        └─ hardness CLI  (harness/main.py)
             └─ DeepAgents orchestrator   [OpenRouter: HARNESS_MODEL]
                  ├─ todo planning tool
                  ├─ tools: run_shell / read_file / write_file
                  └─ subagents (isolated context, HARNESS_SUBAGENT_MODEL)
                       planner · builder · reviewer · qa · shipper
```

OpenShell wraps the **whole process**, so the policy engine gates actions
out-of-process — the agent cannot escape its own sandbox by editing tool code.

## Setup

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

Without OpenShell installed, `run.sh` falls back to unsandboxed (dev only) and warns.

## Layout

- `harness/model.py` — OpenRouter `ChatOpenAI` factory
- `harness/agents.py` — `create_deep_agent` w/ subagents
- `harness/roles.py` — Gstack role prompts + orchestrator prompt
- `harness/tools.py` — shell/file tools (trust sandbox boundary, no in-tool policy)
- `harness/main.py` — streaming CLI
- `policy.yaml` — OpenShell policy (default-deny; allowlist gateway + registries)

## Caveats

- Verify exact API surface against installed versions: DeepAgents `subagents=`
  schema and OpenShell `policy.yaml` keys evolve. Run `openshell policy validate policy.yaml`.
- DeepAgents needs Python ≥3.11.
