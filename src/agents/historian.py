from __future__ import annotations

from src.agents.base import SpecialistAgent


class HistorianAgent(SpecialistAgent):
    prompt_name = "historian"
    section_name = "讲事情"
