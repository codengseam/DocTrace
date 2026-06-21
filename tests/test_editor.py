from unittest.mock import MagicMock, patch

from src.agents.editor import run
from src.core.state import AgentState


def test_editor_injects_rules():
    state: AgentState = {
        "book": "资治通鉴",
        "chapter": "周纪二",
        "event": "商鞅变法",
        "user_input": "",
        "output_path": "",
        "sections": {"讲事情": "故事内容"},
        "sources": {"讲事情": ["史记"]},
        "final_markdown": "",
        "errors": [],
    }
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = MagicMock(
        content='---\ntitle: 测试\n---\n\n# 标题\n\n正文'
    )

    with patch("src.agents.editor.create_llm", return_value=fake_llm):
        result = run(state)

    prompt = fake_llm.invoke.call_args[0][0]
    assert "项目规则" in prompt or "RULES" in prompt
    assert "讲事情" in prompt
    assert "故事内容" in prompt
    assert "# 标题" in result["final_markdown"]
