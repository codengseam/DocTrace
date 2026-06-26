from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

# 显性 AI 套路句式
AI_PATTERNS_EXPLICIT = [
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

# 软性 AI 套路句式（LoopAgent 第1章测评后新增）
AI_PATTERNS_SOFT = [
    r"这件事说明",
    r"这是典型的",
    r"这是他的.*面",
    r"从结果看.*但从格局看",
    r"不是偶然",
    r"容易被忽略",
    r"最关键的.*是",
    r"与.*一脉相承",
    r"放到今天依然成立",
    r"这条规律到今天没变",
    r"这不是.*是.*式重新定义",
    r"原文大意是",
    r"核心论点是",
    r"还有一层背景容易被忽略",
    # 第2章测评后新增
    r"不是.*而是",  # 「不是X而是Y」句式
    r"他不是.*是",  # 「他不是X，是Y」
    r"这说明",
    r"这话提醒我们",
    r"可见",  # 「可见」作段尾总结
    r"第[一二三四五六]层",  # 分点骨架
    r"经得起反复咀嚼",
    # 第5章测评后新增
    r"这事说明",  # 「这事说明」软性AI套路
    r"还有一层背景须交代",  # 模板过渡
    r"另有一层.*须说明",  # 模板过渡
    # 第6章测评后新增
    r"再说一层背景",  # 模板过渡
    r"这道理在历史上反复应验",  # 模板过渡
    r"这道理在历史上也有映照",  # 模板过渡
    r"这道理.*也懂",  # 模板过渡
    r"这思路在后世也有人用",  # 模板过渡
]

# 现代学科术语（历史叙事中禁用）
MODERN_JARGON = [
    r"博弈论",
    r"坐标系",
    r"放大器",
    r"最小获胜联盟",
    r"零和博弈",
    r"底层逻辑",
    r"纳什均衡",
    r"帕累托",
    # 第2章测评后新增
    r"方法论",
    r"资产",  # 「信用是最贵的资产」
    r"润滑剂",
    r"精算师",
    r"效率极高",
    r"效率极低",
    r"死穴",  # 偏现代口语术语
    r"模式",  # 「能臣靠明主模式」
    # 第4章测评后新增
    r"天使投资",
    r"社会流动",
    r"常设机构",
    r"约束机制",
    r"纸面实力",
    r"外交战",
    r"硬道理",
    r"扎心",
    r"资本",  # 「翻身的唯一资本」现代用法
    r"缩影",
    r"教科书级",
    r"大洗牌",
    # 第5章测评后新增
    r"智商.*掉线",  # 网络流行语
    r"话术",  # 偏现代词
]

AI_PATTERNS = AI_PATTERNS_EXPLICIT + AI_PATTERNS_SOFT

# 别名，与历史实现保持一致
check_ai_flavor = None  # 在 check_ai_tone 定义后设置


@dataclass
class QualityReport:
    """质量检查报告。"""
    passed: bool
    issues: List[str] = field(default_factory=list)


def check_structure(content: str, required_sections: List[str]) -> List[str]:
    """检查正文是否包含所有必需章节。"""
    issues = []
    for section in required_sections:
        if f"## {section}" not in content:
            issues.append(f"缺少章节：{section}")
    return issues


def check_ai_tone(content: str) -> List[str]:
    """检查 AI 味句式。"""
    issues = []
    for pattern in AI_PATTERNS:
        if re.search(pattern, content):
            issues.append(f"疑似 AI 味句式：{pattern}")
    return issues


check_ai_flavor = check_ai_tone


def check_modern_jargon(content: str) -> List[str]:
    """检测历史叙事中硬塞的现代学科术语。"""
    issues = []
    for pattern in MODERN_JARGON:
        if re.search(pattern, content):
            issues.append(f"历史叙事中疑似硬塞现代术语：{pattern}")
    return issues


def check_mixed_language(content: str) -> List[str]:
    """检查中英文混杂（专有名词除外）。"""
    issues = []
    matches = re.findall(r"[\u4e00-\u9fff]+[a-zA-Z]{2,}", content)
    if matches:
        issues.append("检测到可能的中英文混杂")
    return issues


check_chinese_english_mix = check_mixed_language


def check_sublimation_quota(content: str) -> List[str]:
    """检测段尾升华是否超额（讲人物/讲背景/讲道理段尾不应升华）。"""
    issues = []
    # 简单启发式：检查讲人物段尾是否有定性句
    for section in ["讲人物", "讲背景", "讲道理"]:
        # 匹配该段到下一个二级标题之间的内容
        pattern = rf"## {section}.*?(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            tail = match.group().strip().split("\n")[-3:]
            tail_text = "".join(tail)
            # 检测段尾定性升华
            sublimation_markers = ["这是他的", "这是典型的", "一脉相承", "放到今天"]
            for marker in sublimation_markers:
                if marker in tail_text:
                    issues.append(f"{section}段尾疑似升华：{marker}")
    return issues


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
    cliche_report = check_ai_cliches(content)
    cliche_issues = (
        [f"AI 套话黑名单命中 {cliche_report['count']} 次：{', '.join(cliche_report['hits'])}"]
        if cliche_report["level"] == "warning"
        else []
    )
    numeric_report = check_numeric_facts(content)
    numeric_issues = [
        f"数字事实硬错误：{e['pattern']}（期望 {e['expected']}，实际 {e['actual']}）"
        for e in numeric_report["auto_errors"]
    ]
    return {
        "structure": check_structure(content, required_sections),
        "ai_tone": check_ai_tone(content),
        "modern_jargon": check_modern_jargon(content),
        "mixed_language": check_mixed_language(content),
        "sublimation_quota": check_sublimation_quota(content),
        "ai_cliches": cliche_issues,
        "numeric_facts": numeric_issues,
    }


def run_quality_checks(
    content: str,
    expected_sections: List[str] | None = None,
    required_frontmatter: List[str] | None = None,
) -> QualityReport:
    """运行完整质量检查，返回 QualityReport（新接口）。

    检查项：frontmatter 完整性、结构完整性、AI 味句式、现代术语、
    中英文混杂、引用标记、段尾升华配额、AI 套话黑名单、数字事实硬错误。

    注：check_numeric_facts 的 manual_review 项（N 年前/N 岁/N 品官）
    仅标记不判定，需由 content_reviewer Agent 复核，不计入此处 issues。
    """
    expected_sections = expected_sections or []
    required_frontmatter = required_frontmatter or []
    issues: List[str] = []
    issues.extend(check_frontmatter(content, required_frontmatter))
    issues.extend(check_structure(content, expected_sections))
    issues.extend(check_ai_tone(content))
    issues.extend(check_modern_jargon(content))
    issues.extend(check_mixed_language(content))
    issues.extend(check_citations(content))
    issues.extend(check_sublimation_quota(content))

    cliche_report = check_ai_cliches(content)
    if cliche_report["level"] == "warning":
        issues.append(
            f"AI 套话黑名单命中 {cliche_report['count']} 次：{', '.join(cliche_report['hits'])}"
        )

    numeric_report = check_numeric_facts(content)
    for e in numeric_report["auto_errors"]:
        issues.append(
            f"数字事实硬错误：{e['pattern']}（期望 {e['expected']}，实际 {e['actual']}）"
        )

    return QualityReport(passed=len(issues) == 0, issues=issues)


# AI 套话黑名单（LoopAgent 沉淀：命中 ≥ 3 次判定为 warning）
AI_CLICHES_BLACKLIST = [
    "综上所述",
    "历史的车轮",
    "让我们看到",
    "以史为鉴",
    "在历史的长河中",
    "不禁让人深思",
    "宛如一颗璀璨的明珠",
    "时代的缩影",
    "深刻地揭示了",
    "正确废话",
    "放之四海而皆准",
]


def check_ai_cliches(text: str) -> dict:
    """检查 AI 套话黑名单。命中 ≥ 3 次返回 warning。

    Returns:
        {"count": int, "hits": [str], "level": "ok"|"warning"}
    """
    hits: List[str] = []
    count = 0
    for phrase in AI_CLICHES_BLACKLIST:
        occurrences = text.count(phrase)
        if occurrences > 0:
            count += occurrences
            hits.append(phrase)
    level = "warning" if count >= 3 else "ok"
    return {"count": count, "hits": hits, "level": level}


def check_numeric_facts(text: str) -> dict:
    """检测数字事实硬错误。

    目前能自动检测的：
    - "N 个字：X" 或 "N 个字，X" 但 len(X) != N

    需要人工/Agent 复核的（本函数只标记，不判定）：
    - "N 年前/N 年后" 模式
    - "N 岁" 模式
    - "N 品官" 模式

    Returns:
        {
            "auto_errors": [{"pattern": "...", "expected": N, "actual": M}, ...],
            "manual_review": [{"pattern": "...", "snippet": "...", "reason": "..."}, ...],
        }
    """
    errors: List[dict] = []
    manual: List[dict] = []

    # 1. 自动检测："N 个字：X" 或 "N 个字，X"
    for m in re.finditer("(\\d+)个字[：:，,]\\s*[\"'\u201c\u201d]?([^\"'\u201c\u201d，。！？\\n]{1,20})", text):
        n = int(m.group(1))
        x = m.group(2).strip().strip('"\'""')
        actual = len(x)
        if actual != n:
            errors.append({"pattern": m.group(0), "expected": n, "actual": actual})

    # 2. 标记需人工复核："N 年前/N 年后"
    for m in re.finditer(r'(\d+)年[前后]', text):
        manual.append({"pattern": m.group(0), "snippet": text[max(0, m.start() - 20):m.end() + 20], "reason": "需核对实际时间跨度"})

    # 3. 标记需人工复核："N 岁"
    for m in re.finditer(r'(\d+)岁', text):
        manual.append({"pattern": m.group(0), "snippet": text[max(0, m.start() - 20):m.end() + 20], "reason": "需核对人物生卒年"})

    # 4. 标记需人工复核："N 品官"
    for m in re.finditer(r'([一二三四五六七八九十\d]+)品官', text):
        manual.append({"pattern": m.group(0), "snippet": text[max(0, m.start() - 20):m.end() + 20], "reason": "需核对职官记录"})

    return {"auto_errors": errors, "manual_review": manual}


def check_chapter_title_soul(title: str) -> dict:
    """章回体灵魂标题三维度评分。

    检测 4 种坏模式（详见 .trae/skills/chapter-title-soul/SKILL.md）：
    1. 事件标签（≤2 字动宾，如"备棺""上疏"）
    2. 数字+量词（如"九个字""八十五天"）
    3. 孤立物件指代（如"那支流矢""那封信"）
    4. 装饰性诗化（如"龙湾的退潮""风雨欲来"）

    Args:
        title: 单个小标题文本（不含 "## 序号、" 前缀）

    Returns:
        {"score": 0-5, "reasons": [...]}
        score < 3 表示需重写
    """
    if not title or not title.strip():
        return {"score": 0, "reasons": ["空标题"]}

    title = title.strip()
    reasons: List[str] = []
    score = 5  # 满分起点

    # 坏模式 1: 数字+量词（九个字/八十五天/二十七年/三万人）
    if re.match(r"^[一二三四五六七八九十百千万千两\d]+个?[字天年人里]$", title):
        return {"score": 1, "reasons": ["数字+量词模式：信息密度不足，只点对象数量不点意义"]}

    # 坏模式 2: 孤立物件指代（那支流矢/那封信/那把刀/那道旨意）
    if re.match(r"^那[支把道封个名家员本]", title):
        return {"score": 1, "reasons": ["孤立物件指代：只点物件不点意义"]}

    # 坏模式 3: 事件标签（≤2 字动宾）
    if len(title) <= 2:
        return {"score": 2, "reasons": ["事件标签：标题过短，疑似事件名而非灵魂点睛"]}

    # 好模式命中检测
    good_patterns = [
        (r"不.{0,2}不", "双重否定句式：指向必然性"),
        (r"不是.+是", "颠覆句式：指向冲突"),
        (r"必", "必然性词"),
        (r"(替|免|压|撬|挡|忍)不了?|不住", "收束词：指向命运"),
        (r"而已", "反差词：指向吊诡"),
        (r"赢了|输了", "反差对比"),
        (r"陪葬|悖论|讽刺|荒唐", "悖论词"),
        (r"必须死|必须杀|亡国", "命运教训词"),
    ]
    good_hits = 0
    for pattern, desc in good_patterns:
        if re.search(pattern, title):
            good_hits += 1
            reasons.append(f"好模式命中：{desc}")

    # 坏模式 4: 四字景物装饰性短语（风雨欲来/潮起潮落/落花流水）
    # 注意：不自动扣分"XX的YY"结构，因为很多好标题用"的"字点反差
    # （如"举人的命""干净的武器""纸糊的盛世"），自动检测误判率过高
    verb_words = r"[是必输赢死亡替挡不住不了守护杀战败胜]"
    if len(title) == 4 and good_hits == 0:
        if re.search(r"[风雨潮花水月云雪山河春秋]", title) and not re.search(verb_words, title):
            score = min(score, 2)
            reasons.append("装饰性诗化：四字景物短语，信息密度不足")

    # 无坏模式且无好模式：根据长度判断
    if not reasons and good_hits == 0:
        if len(title) >= 3:
            score = 3  # 中长标题默认承载信息
        else:
            score = 2

    # 有好模式但被坏模式扣分：好模式补救
    if good_hits > 0 and score < 5:
        score = min(5, score + good_hits)

    return {"score": max(0, min(5, score)), "reasons": reasons if reasons else ["无扣分"]}
