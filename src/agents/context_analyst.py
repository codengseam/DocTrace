from __future__ import annotations

from src.agents.base import SpecialistAgent


class ContextAnalystAgent(SpecialistAgent):
    prompt_name = "context_analyst"
    section_name = "讲背景"
