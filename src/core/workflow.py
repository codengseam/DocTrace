from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.biographer import BiographerAgent
from src.agents.context_analyst import ContextAnalystAgent
from src.agents.critic import CriticAgent
from src.agents.editor import EditorAgent
from src.agents.historian import HistorianAgent
from src.agents.orchestrator import OrchestratorAgent
from src.agents.philosopher import PhilosopherAgent
from src.utils.config import Config
from src.utils.llm import LLMClient, build_llm
from src.utils.logger import make_log_path
from src.utils.markdown import build_output_path, save_markdown
from src.utils.quality import run_quality_checks


class WorkflowState(TypedDict, total=False):
    user_input: str
    book: str
    chapter: str
    event: str
    output_path: str
    log_path: str
    sections: list[dict[str, Any]]
    final_markdown: str
    quality_report: dict[str, Any]


class DeepReadingWorkflow:
    def __init__(self, config: Config | None = None, llm: LLMClient | None = None) -> None:
        self.config = config or Config()
        self.llm = llm or build_llm(self.config.llm)
        self.prompts_dir = self.config.path("prompts")
        self.output_dir = self.config.path("output")
        self.logs_dir = self.config.path("logs")

        self.orchestrator = OrchestratorAgent(self.llm, self._logger("orchestrator"))
        self.specialists = [
            HistorianAgent(self.llm, self._logger("historian"), self.prompts_dir),
            BiographerAgent(self.llm, self._logger("biographer"), self.prompts_dir),
            ContextAnalystAgent(self.llm, self._logger("context_analyst"), self.prompts_dir),
            CriticAgent(self.llm, self._logger("critic"), self.prompts_dir),
            PhilosopherAgent(self.llm, self._logger("philosopher"), self.prompts_dir),
        ]
        self.editor = EditorAgent(self.llm, self._logger("editor"), self.prompts_dir)

        self.graph = self._build_graph()

    def _logger(self, name: str) -> logging.Logger:
        return logging.getLogger(f"deep_reading.{name}")

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(WorkflowState)

        graph.add_node("orchestrator", self._node_orchestrator)
        graph.add_node("specialists", self._node_specialists)
        graph.add_node("editor", self._node_editor)
        graph.add_node("quality", self._node_quality)
        graph.add_node("save", self._node_save)

        graph.set_entry_point("orchestrator")
        graph.add_edge("orchestrator", "specialists")
        graph.add_edge("specialists", "editor")
        graph.add_edge("editor", "quality")
        graph.add_edge("quality", "save")
        graph.add_edge("save", END)

        return graph.compile()

    @staticmethod
    def _ensure_file_logger(log_path: Path) -> None:
        root = logging.getLogger("deep_reading")
        for handler in root.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_path.resolve()):
                return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        )
        root.setLevel(logging.DEBUG)
        root.addHandler(file_handler)

    def _node_orchestrator(self, state: WorkflowState) -> WorkflowState:
        user_input = state["user_input"]
        parsed = self.orchestrator.parse_input(user_input)
        output_path = parsed.get("output_path") or str(
            build_output_path(
                self.output_dir,
                parsed["book"],
                parsed["chapter"],
                parsed["event"],
            )
        )
        log_path = Path(state.get("log_path") or make_log_path(self.logs_dir, parsed["event"]))
        self._ensure_file_logger(log_path)
        return {
            **state,
            "book": parsed["book"],
            "chapter": parsed["chapter"],
            "event": parsed["event"],
            "output_path": output_path,
            "log_path": str(log_path),
            "sections": [],
        }

    def _node_specialists(self, state: WorkflowState) -> WorkflowState:
        book, chapter, event = state["book"], state["chapter"], state["event"]

        def run_agent(agent):
            return agent.run(book, chapter, event)

        with ThreadPoolExecutor(max_workers=len(self.specialists)) as executor:
            sections = list(executor.map(run_agent, self.specialists))

        return {**state, "sections": sections}

    def _node_editor(self, state: WorkflowState) -> WorkflowState:
        markdown = self.editor.run(
            state["book"],
            state["chapter"],
            state["event"],
            state["sections"],
        )
        return {**state, "final_markdown": markdown}

    def _node_quality(self, state: WorkflowState) -> WorkflowState:
        report = run_quality_checks(
            state["final_markdown"],
            expected_sections=self.config.rules.get("sections", []),
            required_frontmatter=self.config.rules.get("required_frontmatter", []),
        )
        return {
            **state,
            "quality_report": {"passed": report.passed, "issues": report.issues},
        }

    def _node_save(self, state: WorkflowState) -> WorkflowState:
        path = Path(state["output_path"])
        save_markdown(path, state["final_markdown"])
        self._logger("workflow").info("Saved markdown to %s", path)

        report = state.get("quality_report", {})
        if not report.get("passed"):
            self._logger("workflow").warning(
                "Quality check issues: %s", report.get("issues")
            )
        return state

    def run(self, user_input: str) -> WorkflowState:
        return self.graph.invoke({"user_input": user_input})


def run_workflow(user_input: str) -> WorkflowState:
    workflow = DeepReadingWorkflow()
    return workflow.run(user_input)
