"""Build the DeepAgents orchestrator with role subagents."""
from __future__ import annotations

from deepagents import create_deep_agent

from .model import make_model, subagent_model
from .roles import ORCHESTRATOR_PROMPT, subagent_specs
from .tools import HARNESS_TOOLS


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
        system_prompt=ORCHESTRATOR_PROMPT,
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
