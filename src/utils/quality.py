import re
from typing import Dict, List

AI_PATTERNS = [
    r"我们可以看到",
    r"这告诉我们",
    r"总而言之",
    r"综上所述",
    r"值得注意的是",
    r"不难发现",
    r"从这个角度来看",
]


def check_structure(content: str, required_sections: List[str]) -> List[str]:
    issues = []
    for section in required_sections:
        if section not in content:
            issues.append(f"缺少章节：{section}")
    return issues


def check_ai_tone(content: str) -> List[str]:
    issues = []
    for pattern in AI_PATTERNS:
        if re.search(pattern, content):
            issues.append(f"疑似 AI 味句式：{pattern}")
    return issues


def check_mixed_language(content: str) -> List[str]:
    issues = []
    # 简单检查中英混杂：中文后紧跟英文单词（专有名词除外可后续优化）
    matches = re.findall(r"[\u4e00-\u9fff]+[a-zA-Z]{2,}", content)
    if matches:
        issues.append("检测到可能的中英文混杂")
    return issues


def run_quality_check(content: str, required_sections: List[str]) -> Dict[str, List[str]]:
    return {
        "structure": check_structure(content, required_sections),
        "ai_tone": check_ai_tone(content),
        "mixed_language": check_mixed_language(content),
    }
