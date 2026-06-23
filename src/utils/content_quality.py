"""内容质检扩展工具。

在 quality.py 已有检测基础上，新增内容质检四维度检测：
- 真实性：关键要素检查（年份、名家、出处等）
- 可读性：重复检测、语言风格
- 顺序：叙事顺序检查
- 引用克制：内联引用清理、行内引用密度、文末来源
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from src.utils.quality import (
    check_ai_tone,
    check_modern_jargon,
    check_mixed_language,
    check_sublimation_quota,
)

# 内联跳转引用（必须清理）
INLINE_REF_PATTERNS = [
    r"（见讲故事）",
    r"（见讲事情）",
    r"（详见[^）]*章[^）]*）",
    r"（详见下章）",
    r"（见上文）",
    r"（见前文）",
]

# 行内古籍引用（——《XX·XX》）
BOOK_CITATION_PATTERN = re.compile(r"——《[^》]+》")

# 关键年份/时间提示（公元前/公元后/前 XXX 年）
YEAR_PATTERN = re.compile(r"前?\d+\s*年")

# 名家名单（用于真实性启发式检测）
FAMOUS_CRITICS = [
    "司马光",
    "司马迁",
    "王夫之",
    "胡三省",
    "贾谊",
    "苏轼",
    "王安石",
    "顾炎武",
    "柳宗元",
    "扬雄",
    "班固",
    "范晔",
    "陈寿",
    "刘知几",
    "章学诚",
]

# 占位段落提示
PLACEHOLDER_PATTERNS = [
    r"未找到",
    r"没有明确评语",
    r"暂无点评",
]

@dataclass
class ContentQualityReport:
    """内容质检报告。"""

    passed: bool
    score: int
    issues: List[str] = field(default_factory=list)
    details: Dict[str, List[str]] = field(default_factory=dict)


def _strip_frontmatter(content: str) -> str:
    """去掉 YAML frontmatter，返回正文。"""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            return content[end + 3 :].strip()
    return content.strip()


def _extract_title(content: str) -> str:
    """从 YAML frontmatter 中提取 title。"""
    if not content.startswith("---"):
        return ""
    end = content.find("---", 3)
    if end <= 0:
        return ""
    fm = content[3:end]
    match = re.search(r"^title:\s*(.+)$", fm, re.MULTILINE)
    return match.group(1).strip() if match else ""


def count_chinese_chars(text: str) -> int:
    """统计中文字符数。"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def check_inline_references(content: str) -> List[str]:
    """检查并返回内联跳转引用。"""
    issues = []
    for pattern in INLINE_REF_PATTERNS:
        matches = re.findall(pattern, content)
        for match in matches:
            issues.append(f"内联跳转引用：{match}")
    return issues


def check_citation_density(content: str, max_per_1k: int = 3) -> List[str]:
    """检查行内古籍引用密度。

    规则：每 max_per_1k 中文字符不超过 1 处「——《XX》」式引用。
    """
    body = _strip_frontmatter(content)
    # 去掉文末来源区域
    ref_split = re.split(r"\n##?\s*参考来源", body)
    narrative = ref_split[0] if ref_split else body

    matches = BOOK_CITATION_PATTERN.findall(narrative)
    if not matches:
        return []

    char_count = count_chinese_chars(narrative)
    if char_count == 0:
        return []

    limit = max(1, (char_count / 1000) * max_per_1k)
    if len(matches) > limit:
        return [
            f"行内引用密度偏高：{len(matches)} 处/约 {char_count} 字，"
            f"超过每千字 {max_per_1k} 处的建议值"
        ]
    return []


def check_sources_section(content: str) -> List[str]:
    """检查文末是否有参考来源。"""
    issues = []
    if not re.search(r"##?\s*参考来源", content):
        issues.append("缺少「参考来源」章节")
    return issues


def check_years_present(content: str) -> List[str]:
    """启发式检查关键年份是否给出。"""
    if _is_philosophy_or_classic(_extract_title(content)):
        return []
    body = _strip_frontmatter(content)
    if not YEAR_PATTERN.search(body):
        return ["正文未检测到关键年份/时间标注，请确认是否需要补充"]
    return []


def check_famous_critics(content: str) -> List[str]:
    """启发式检查是否有非司马光名家。

    对哲学/经典解读类内容，不强制要求历史名家点评。
    """
    if _is_philosophy_or_classic(_extract_title(content)):
        return []
    body = _strip_frontmatter(content)

    found = [name for name in FAMOUS_CRITICS if name in body]

    issues = []
    if "司马光" not in body and "臣光曰" not in body and "司马迁" not in body:
        issues.append("未检测到司马光/臣光曰/司马迁等核心名家点评")

    non_simaguang = [n for n in found if n not in ("司马光", "司马迁")]
    if len(non_simaguang) < 2:
        issues.append(f"非司马光/司马迁名家数量不足（当前 {len(non_simaguang)} 位）")

    return issues


def check_placeholder_sections(content: str) -> List[str]:
    """检查是否有占位段落。"""
    issues = []
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, content):
            issues.append(f"检测到占位表述：{pattern}")
    return issues


def _filter_natural_expressions(issues: List[str], content: str) -> List[str]:
    """过滤 AI 句式检测中的自然口语表达误报。"""
    filtered = []
    for issue in issues:
        # "他不是 X，是 Y" 类：若 X 是常见自然词，通常是口语判断句
        if "他不是.*是" in issue:
            # 简单采样：若正文中包含 "他不是不知道/不是不懂/不是不傻/不是死记" 等，视为自然表达
            natural_hints = [
                "他不是不知道",
                "他不是不懂",
                "他不是不",
                "他不是死记",
                "他不是没",
            ]
            if any(hint in content for hint in natural_hints):
                continue
        filtered.append(issue)
    return filtered


def check_internal_repetition(content: str) -> List[str]:
    """检测单章节内重复的古文/金句。

    简单启发式：连续出现 2 次及以上的古文引用视为重复。
    """
    body = _strip_frontmatter(content)
    quotes = re.findall(r"「([^」]{5,30})」", body)
    seen = set()
    dupes = set()
    for q in quotes:
        if q in seen:
            dupes.add(q)
        seen.add(q)
    return [f"单章内重复古文/金句：{q}" for q in dupes]


def check_cross_chapter_jump(content: str) -> List[str]:
    """检查是否用括号引导读者看其他章节。

    只匹配明确跳转意图的括号提示，避免把古籍引用括号误判。
    """
    issues = []
    # 匹配：见/详见/参见 + 章/前文/上文/下文/后文/讲故事/讲事情
    pattern = re.compile(r"（[^）]*(?:见|详见|参见)[^）]*(?:章|前文|上文|下文|后文|讲故事|讲事情|相关章节|此处不赘)[^）]*）")
    for match in pattern.finditer(content):
        issues.append(f"疑似跨章跳转提示：{match.group()}")
    return issues


def _is_philosophy_or_classic(book_or_title: str) -> bool:
    """判断是否为哲学/经典解读类内容，不强制要求历史年份。"""
    keywords = ["论语", "孔子传", "孟子", "大学", "中庸", "道德经", "庄子", "墨子", "荀子"]
    return any(k in book_or_title for k in keywords)


def check_temporal_order(content: str) -> List[str]:
    """启发式检查叙事顺序。

    对历史叙事类内容，检查讲事情段落是否包含时间标注。
    对论语、孔子传等哲学/经典解读类内容跳过此检查。
    """
    if _is_philosophy_or_classic(_extract_title(content)):
        return []
    body = _strip_frontmatter(content)
    sections = re.split(r"\n## ", body)
    issues = []
    for section in sections:
        if section.startswith("讲事情"):
            if not YEAR_PATTERN.search(section):
                issues.append("讲事情段落缺少明确时间/年份标注")
            break
    return issues


def run_content_quality_checks(content: str) -> ContentQualityReport:
    """运行完整内容质检，返回报告与分数。"""
    issues: List[str] = []
    details: Dict[str, List[str]] = {}

    # 1. 真实性
    details["truth"] = []
    details["truth"].extend(check_years_present(content))
    details["truth"].extend(check_famous_critics(content))
    details["truth"].extend(check_placeholder_sections(content))

    # 2. 可读性（复用并扩展 quality.py）
    details["readability"] = []
    ai_tone_issues = check_ai_tone(content)
    ai_tone_issues = _filter_natural_expressions(ai_tone_issues, content)
    details["readability"].extend(ai_tone_issues)
    details["readability"].extend(check_modern_jargon(content))
    details["readability"].extend(check_mixed_language(content))
    details["readability"].extend(check_sublimation_quota(content))
    details["readability"].extend(check_internal_repetition(content))

    # 3. 顺序
    details["sequence"] = []
    details["sequence"].extend(check_temporal_order(content))

    # 4. 引用克制
    details["citation"] = []
    details["citation"].extend(check_inline_references(content))
    details["citation"].extend(check_cross_chapter_jump(content))
    details["citation"].extend(check_citation_density(content))
    details["citation"].extend(check_sources_section(content))

    for key in details:
        issues.extend(details[key])

    # 计分：从 100 起扣
    score = 100
    score -= min(20, len(details["truth"]) * 5)      # 真实性问题每项扣 5 分，上限 20
    score -= min(20, len(details["readability"]) * 2) # 可读性问题每项扣 2 分，上限 20
    score -= min(10, len(details["sequence"]) * 5)    # 顺序问题每项扣 5 分，上限 10
    score -= min(15, len(details["citation"]) * 3)    # 引用问题每项扣 3 分，上限 15
    score = max(0, score)

    return ContentQualityReport(
        passed=score >= 85,
        score=score,
        issues=issues,
        details=details,
    )


def format_report(report: ContentQualityReport) -> str:
    """将报告格式化为 Markdown。"""
    lines = [
        "## 内容质检报告",
        "",
        f"- **总分**：{report.score}/100",
        f"- **评级**：{'优秀' if report.score >= 90 else '合格' if report.score >= 85 else '不合格，须修复'}",
        "",
        "### 问题分布",
    ]
    for category, items in report.details.items():
        label = {"truth": "真实性", "readability": "可读性", "sequence": "顺序", "citation": "引用克制"}.get(
            category, category
        )
        lines.append(f"\n#### {label}（{len(items)} 项）")
        if items:
            for item in items:
                lines.append(f"- ❌ {item}")
        else:
            lines.append("- ✅ 无问题")
    if report.issues:
        lines.extend([
            "",
            "### 修复建议",
            "",
            "请按 `.trae/rules/content-quality.md` 中的修复优先级逐项处理。",
        ])
    return "\n".join(lines)
