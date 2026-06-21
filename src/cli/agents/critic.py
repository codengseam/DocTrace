from __future__ import annotations

from src.cli.agents.base import SpecialistAgent


class CriticAgent(SpecialistAgent):
    prompt_name = "critic"
    section_name = "讲道理"
