"""Build the DeepAgents orchestrator with role subagents."""
from __future__ import annotations

from deepagents import create_deep_agent

from . import memory, skills
from .model import make_model, subagent_model
from .roles import ORCHESTRATOR_PROMPT, subagent_specs
from .tools import HARNESS_TOOLS


def _compose_prompt() -> str:
    """Base orchestrator prompt + live memory index and skills catalog."""
    parts = [ORCHESTRATOR_PROMPT]
    idx = memory.index_text()
    if idx:
        parts.append(
            "Known memory (knowledge graph in ./Memory). `recall` to read full "
            "notes, `remember` to add:\n" + idx
        )
    cat = skills.catalog_text()
    if cat:
        parts.append(
            "Available skills (./Skills). `use_skill(<name>)` to load full "
            "instructions before acting:\n" + cat
        )
    return "\n\n".join(parts)


def build_agent(checkpointer=None):
    """Create the orchestrator deep agent.

    - Main model: OpenRouter (HARNESS_MODEL).
    - Subagents: one per Gstack role, each with isolated context, on the
      (optionally cheaper) HARNESS_SUBAGENT_MODEL.
    - checkpointer: optional LangGraph checkpointer; enables conversation memory
      keyed by thread_id (the session id) so a resumed run keeps context.
    """
    main = make_model()
    sub = subagent_model()

    # Attach the subagent model to each role spec.
    subagents = [{**spec, "model": sub} for spec in subagent_specs()]

    kwargs = dict(
        model=main,
        tools=HARNESS_TOOLS,
        system_prompt=_compose_prompt(),
        subagents=subagents,
    )
    if checkpointer is not None:
        # DeepAgents passes this through to the compiled LangGraph graph. Guard
        # against version skew in the kwarg name.
        try:
            return create_deep_agent(**kwargs, checkpointer=checkpointer)
        except TypeError:
            pass
    return create_deep_agent(**kwargs)
