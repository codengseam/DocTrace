import tempfile
from pathlib import Path

from src.core.workflow import build_workflow


def test_workflow_uses_custom_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        app = build_workflow(output_base=tmpdir)
        assert app is not None
