from src.core.workflow import build_workflow


def test_workflow_compiles():
    app = build_workflow()
    assert app is not None
