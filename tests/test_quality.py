from src.utils.quality import run_quality_check


def test_quality_check_detects_missing_section():
    content = "## 讲事情\n\n内容"
    result = run_quality_check(content, ["讲事情", "讲人物"])
    assert len(result["structure"]) == 1
    assert "讲人物" in result["structure"][0]


def test_quality_check_detects_ai_tone():
    content = "我们可以看到，这件事很重要。"
    result = run_quality_check(content, ["讲事情"])
    assert len(result["ai_tone"]) > 0


def test_quality_check_passes_clean_content():
    content = "## 讲事情\n\n这是故事内容。"
    result = run_quality_check(content, ["讲事情"])
    assert result["structure"] == []
    assert result["ai_tone"] == []
