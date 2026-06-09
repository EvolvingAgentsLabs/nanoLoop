"""Build the DeepAgents orchestrator with role subagents."""
from __future__ import annotations

from deepagents import create_deep_agent

from .model import make_model, subagent_model
from .roles import ORCHESTRATOR_PROMPT, subagent_specs
from .tools import HARNESS_TOOLS


def build_agent():
    """Create the orchestrator deep agent.

    - Main model: OpenRouter (HARNESS_MODEL).
    - Subagents: one per Gstack role, each with isolated context, on the
      (optionally cheaper) HARNESS_SUBAGENT_MODEL.
    """
    main = make_model()
    sub = subagent_model()

    # Attach the subagent model to each role spec.
    subagents = [{**spec, "model": sub} for spec in subagent_specs()]

    return create_deep_agent(
        model=main,
        tools=HARNESS_TOOLS,
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
    )
