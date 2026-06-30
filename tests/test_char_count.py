"""字数事实核对回归测试（BUG-038）。

字数是确定性事实，不交给会数错 token 的 LLM。
覆盖三种模式 + 中文数字 + 序号排除 + frontmatter 跳过 + quality.py 联动。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src" / "utils"))

import check_char_count as c
from quality import check_numeric_facts


# ---------------------------------------------------------------------------
# strip_punct / cn_to_int 基础函数
# ---------------------------------------------------------------------------

def test_strip_punct_excludes_punctuation():
    """标点、空白、Markdown 符号不计入字数。"""
    assert c.strip_punct("你好世") == "你好世"
    assert c.strip_punct("你好，世界。") == "你好世界"
    assert c.strip_punct("「太子」") == "太子"
    assert c.strip_punct("**就高不就低**") == "就高不就低"
    assert c.strip_punct("高筑墙，广积粮，缓称王") == "高筑墙广积粮缓称王"
    assert c.strip_punct("") == ""
    assert c.strip_punct("，，。！！") == ""


def test_cn_to_int_arabic():
    assert c.cn_to_int("3") == 3
    assert c.cn_to_int("12") == 12


def test_cn_to_int_single():
    assert c.cn_to_int("三") == 3
    assert c.cn_to_int("八") == 8
    assert c.cn_to_int("两") == 2


def test_cn_to_int_compound():
    assert c.cn_to_int("十二") == 12
    assert c.cn_to_int("二十") == 20
    assert c.cn_to_int("二十三") == 23
    assert c.cn_to_int("一百") == 100
    assert c.cn_to_int("一百二十") == 120
    assert c.cn_to_int("十个") == 10


def test_cn_to_int_unparseable():
    assert c.cn_to_int("") == -1


# ---------------------------------------------------------------------------
# check_text 三种模式
# ---------------------------------------------------------------------------

def test_check_text_pattern_a_arabic():
    """模式A 阿拉伯数字：5个字：你好世（实际3字）应报错。"""
    errors = c.check_text("这段话有个5个字：你好世，明显数错了。")
    assert len(errors) == 1
    assert errors[0]["expected"] == 5
    assert errors[0]["actual"] == 3
    assert errors[0]["pattern_type"] == "A"


def test_check_text_pattern_a_cn_digit():
    """模式A 中文数字：三个字：项羽破（实际3字）不应报；三个字：项羽破釜（4字）应报。"""
    assert c.check_text("三个字：项羽破") == []
    errors = c.check_text("三个字：项羽破釜")
    assert len(errors) == 1
    assert errors[0]["expected"] == 3
    assert errors[0]["actual"] == 4


def test_check_text_pattern_b_quoted_cn():
    """模式B 中文数字：「太子」这三个字（实际2字）应报错。"""
    errors = c.check_text("「太子」这三个字")
    assert len(errors) == 1
    assert errors[0]["expected"] == 3
    assert errors[0]["actual"] == 2
    assert errors[0]["pattern_type"] == "B"


def test_check_text_pattern_b_double_quote_with_period():
    """模式B 引号后句号再'这N个字'：「X」。这八个字（实际10字）应报错。"""
    errors = c.check_text("\u201c非刘氏而王，天下共击之\u201d。这八个字是白马之盟")
    assert len(errors) == 1
    assert errors[0]["expected"] == 8
    assert errors[0]["actual"] == 10
    assert errors[0]["pattern_type"] == "B"


def test_check_text_pattern_b_correct_count():
    """模式B 正确字数不报：「太子」这两个字。"""
    assert c.check_text("「太子」这两个字") == []
    assert c.check_text("\u201c发愤著书\u201d这四个字") == []


def test_check_text_pattern_c_quoted():
    """模式C：三个字：「太子」（实际2字）应报错。"""
    errors = c.check_text("三个字：「太子」")
    assert len(errors) == 1
    assert errors[0]["expected"] == 3
    assert errors[0]["actual"] == 2
    assert errors[0]["pattern_type"] == "C"


def test_check_text_pattern_c_quoted_with_comma():
    """模式C 引文含逗号：九个字：「高筑墙，广积粮，缓称王」（实际9字）不应报。"""
    assert c.check_text('九个字：\u201c高筑墙，广积粮，缓称王\u201d') == []


def test_check_text_skips_frontmatter():
    """frontmatter 内的数字不应触发。"""
    text = "---\ntitle: 测试\nword_count: 5\n---\n\n正文内容。"
    assert c.check_text(text) == []


def test_check_text_skips_ordinal():
    """'第N个字'是序号（第一/第二/第三），不是字数声称，不报。"""
    assert c.check_text("第一个字：不妄求") == []
    assert c.check_text("第二个字：不妄言") == []


def test_check_text_empty_punct_only_skipped():
    """引文为空或纯标点（如 Markdown **）跳过，不误报。"""
    assert c.check_text("四个字：\n\n> 「大壮」") == []
    assert c.check_text("十二个字：**") == []


# ---------------------------------------------------------------------------
# check_file / check_dir
# ---------------------------------------------------------------------------

def test_check_file(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("「太子」这三个字", encoding="utf-8")
    errors = c.check_file(md)
    assert len(errors) == 1
    assert errors[0]["expected"] == 3
    assert errors[0]["actual"] == 2
    assert "file" in errors[0]


def test_check_dir(tmp_path):
    (tmp_path / "a.md").write_text("「太子」这三个字", encoding="utf-8")
    (tmp_path / "b.md").write_text("「太子」这两个字", encoding="utf-8")
    errors = c.check_dir(tmp_path)
    assert len(errors) == 1
    assert errors[0]["expected"] == 3


# ---------------------------------------------------------------------------
# quality.py check_numeric_facts 联动
# ---------------------------------------------------------------------------

def test_quality_check_numeric_facts_pattern_a_compat():
    """BUG-026 契约：5个字：你好世（5≠3）仍检测。"""
    result = check_numeric_facts("这段话有个5个字：你好世，明显数错了。")
    assert len(result["auto_errors"]) == 1
    assert result["auto_errors"][0]["expected"] == 5
    assert result["auto_errors"][0]["actual"] == 3


def test_quality_check_numeric_facts_pattern_b():
    """模式B：「太子」这三个字（2≠3）应检测。"""
    result = check_numeric_facts("「太子」这三个字")
    assert any(e["pattern_type"] == "B" for e in result["auto_errors"])
    b_err = [e for e in result["auto_errors"] if e["pattern_type"] == "B"][0]
    assert b_err["expected"] == 3
    assert b_err["actual"] == 2


def test_quality_check_numeric_facts_pattern_c():
    """模式C：三个字：「太子」（2≠3）应检测。"""
    result = check_numeric_facts("三个字：「太子」")
    assert any(e["pattern_type"] == "C" for e in result["auto_errors"])


def test_quality_check_numeric_facts_cn_digit():
    """中文数字：八个字："天下号恸，如丧考妣"（8=8）不应报错。"""
    result = check_numeric_facts('八个字：\u201c天下号恸，如丧考妣\u201d')
    assert result["auto_errors"] == []


def test_quality_check_numeric_facts_skips_ordinal():
    """'第N个字'序号不报。"""
    result = check_numeric_facts("第一个字：不妄求")
    assert result["auto_errors"] == []


def test_quality_check_numeric_facts_manual_review_unchanged():
    """N 年前/N 岁/N 品官 仍进 manual_review。

    manual_review 正则只匹配阿拉伯数字（"20 年前"/"30 岁"/"3 品官"），
    不匹配中文数字（"二十年前"/"三十岁"）——这与 BUG-026 原始契约一致：
    时间/年龄/官品是历史事实，需要 Agent 人工核对，不强制走自动解析。
    本测试改用阿拉伯数字以验证 manual_review 路径仍生效。
    """
    text = "20年前他30岁，官至3品官。"
    result = check_numeric_facts(text)
    reasons = [m["reason"] for m in result["manual_review"]]
    assert any("时间跨度" in r for r in reasons)
    assert any("生卒年" in r for r in reasons)
    assert any("职官" in r for r in reasons)
