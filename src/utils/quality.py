import re
from dataclasses import dataclass, field
from typing import Dict, List


AI_PATTERNS = [
    r"我们可以看到",
    r"这告诉我们",
    r"总而言之",
    r"综上所述",
    r"值得注意的是",
    r"不难发现",
    r"从这个角度来看",
    r"让我们",
    r"从某种意义上说",
]


@dataclass
class QualityReport:
    """质量检查报告。"""
    passed: bool
    issues: List[str] = field(default_factory=list)


def check_structure(content: str, required_sections: List[str]) -> List[str]:
    """检查正文是否包含所有必需章节。"""
    issues = []
    for section in required_sections:
        if section not in content:
            issues.append(f"缺少章节：{section}")
    return issues


def check_ai_tone(content: str) -> List[str]:
    """检查 AI 味句式。"""
    issues = []
    for pattern in AI_PATTERNS:
        if re.search(pattern, content):
            issues.append(f"疑似 AI 味句式：{pattern}")
    return issues


# 别名，与 src/cli/ 实现保持一致
check_ai_flavor = check_ai_tone


def check_mixed_language(content: str) -> List[str]:
    """检查中英文混杂（专有名词除外）。"""
    issues = []
    matches = re.findall(r"[\u4e00-\u9fff]+[a-zA-Z]{2,}", content)
    if matches:
        issues.append("检测到可能的中英文混杂")
    return issues


# 别名
check_chinese_english_mix = check_mixed_language


def check_frontmatter(content: str, required_keys: List[str]) -> List[str]:
    """检查 frontmatter 是否包含所有必需字段。"""
    issues = []
    if not content.startswith("---"):
        issues.append("缺少 frontmatter")
        return issues
    end = content.find("---", 3)
    fm = content[3:end] if end > 0 else ""
    for key in required_keys:
        if f"{key}:" not in fm:
            issues.append(f"frontmatter 缺少 {key}")
    return issues


def check_citations(content: str) -> List[str]:
    """检查引用标记。"""
    issues = []
    if "《" not in content and "原文" not in content:
        issues.append("缺少古籍/原文引用标记")
    return issues


def run_quality_check(content: str, required_sections: List[str]) -> Dict[str, List[str]]:
    """运行质量检查，返回分类问题字典（旧接口，保持向后兼容）。"""
    return {
        "structure": check_structure(content, required_sections),
        "ai_tone": check_ai_tone(content),
        "mixed_language": check_mixed_language(content),
    }


def run_quality_checks(
    content: str,
    expected_sections: List[str] | None = None,
    required_frontmatter: List[str] | None = None,
) -> QualityReport:
    """运行完整质量检查，返回 QualityReport（新接口）。

    检查项：frontmatter 完整性、结构完整性、AI 味句式、中英文混杂、引用标记。
    """
    expected_sections = expected_sections or []
    required_frontmatter = required_frontmatter or []
    issues: List[str] = []
    issues.extend(check_frontmatter(content, required_frontmatter))
    issues.extend(check_structure(content, expected_sections))
    issues.extend(check_ai_tone(content))
    issues.extend(check_mixed_language(content))
    issues.extend(check_citations(content))
    return QualityReport(passed=len(issues) == 0, issues=issues)
