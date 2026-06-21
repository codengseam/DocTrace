import subprocess
import sys
import tempfile
from pathlib import Path


def test_main_stub_generates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable,
                "src/main.py",
                "--book", "资治通鉴",
                "--chapter", "周纪二",
                "--event", "商鞅变法",
                "--stub",
                "--output-dir", tmpdir,
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        output_path = Path(tmpdir) / "资治通鉴" / "周纪二_商鞅变法.md"
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "讲事情" in content
        assert "讲人物" in content


def test_main_stub_with_user_input_parses_slots():
    """stub 模式结合 --input 时，应能从输入中解析书名/章节/事件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable,
                "src/main.py",
                "--input", "资治通鉴 周纪二 商鞅变法",
                "--stub",
                "--output-dir", tmpdir,
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        output_path = Path(tmpdir) / "资治通鉴" / "周纪二_商鞅变法.md"
        assert output_path.exists(), f"输出文件不存在: {output_path}\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_main_stub_missing_params_errors():
    """stub 模式缺少 book/chapter/event 时应返回非零。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable,
                "src/main.py",
                "--input", "只有一句话",
                "--stub",
                "--output-dir", tmpdir,
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
