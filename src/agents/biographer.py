from __future__ import annotations

from src.agents.base import SpecialistAgent


class BiographerAgent(SpecialistAgent):
    prompt_name = "biographer"
    section_name = "讲人物"
