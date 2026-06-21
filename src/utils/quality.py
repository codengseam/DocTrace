from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class QualityReport:
    passed: bool
    issues: list[str]


def check_structure(content: str, expected_sections: list[str]) -> list[str]:
    issues = []
    for section in expected_sections:
        if section not in content:
            issues.append(f"缺少章节：{section}")
    if "结语" not in content and "总结" not in content:
        issues.append("缺少结语/总结")
    return issues


def check_frontmatter(content: str, required_keys: list[str]) -> list[str]:
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


def check_ai_flavor(content: str) -> list[str]:
    patterns = [
        r"我们可以看到",
        r"这告诉我们",
        r"值得注意的是",
        r"综上所述",
        r"\b(importantly|significantly)\b",
        r"让我们",
        r"不难发现",
        r"从某种意义上说",
    ]
    issues = []
    for pat in patterns:
        if re.search(pat, content, re.IGNORECASE):
            issues.append(f"疑似 AI 味句式：{pat}")
    return issues


def check_chinese_english_mix(content: str) -> list[str]:
    issues = []
    if re.search(r"[\u4e00-\u9fff][a-zA-Z]|[a-zA-Z][\u4e00-\u9fff]", content):
        issues.append("发现中英文混杂")
    return issues


def check_citations(content: str) -> list[str]:
    issues = []
    if "《" not in content and "原文" not in content:
        issues.append("缺少古籍/原文引用标记")
    return issues


def run_quality_checks(
    content: str,
    expected_sections: list[str] | None = None,
    required_frontmatter: list[str] | None = None,
) -> QualityReport:
    expected_sections = expected_sections or []
    required_frontmatter = required_frontmatter or []
    issues: list[str] = []
    issues.extend(check_frontmatter(content, required_frontmatter))
    issues.extend(check_structure(content, expected_sections))
    issues.extend(check_ai_flavor(content))
    issues.extend(check_chinese_english_mix(content))
    issues.extend(check_citations(content))
    return QualityReport(passed=len(issues) == 0, issues=issues)
