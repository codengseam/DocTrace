"""公共测试 fixture。"""
import tempfile

import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """启用 Mock 模式，无需 API Key，并将日志重定向到临时目录。"""
    monkeypatch.setenv("DEEP_READING_MOCK", "1")

    # 将日志目录重定向到临时目录，避免污染真实 logs/
    tmpdir = tempfile.mkdtemp()

    def fake_load_config():
        return {
            "output_dir": "output",
            "logs": {"base_dir": tmpdir},
            "quality_check": {
                "required_sections": [
                    "讲事情",
                    "讲人物",
                    "讲背景",
                    "讲道理",
                    "问道悟道",
                    "结语",
                ],
            },
            # 阶段3：section_templates 与 quality_check.required_sections 同步
            "section_templates": {
                "narrative": [
                    "讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语",
                ],
                "modern": ["入戏", "破题", "方法论", "避坑", "践行"],
                "knowledge": ["概念", "原理", "实践", "速查/自测"],
            },
        }

    try:
        import src.core.workflow  # noqa: F401
        monkeypatch.setattr("src.core.workflow.load_config", fake_load_config)
    except ImportError:
        pass  # 环境缺少 langgraph 等依赖时，不阻塞无需 workflow 的测试
    yield
