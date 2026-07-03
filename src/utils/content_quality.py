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
    check_ai_cliches,
    check_ai_tone,
    check_chapter_title_soul,
    check_mixed_language,
    check_modern_jargon,
    check_numeric_facts,
    check_sublimation_quota,
    strip_frontmatter,
)
from src.utils.consistency import check_consistency

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
    "王世贞",
    "唐顺之",
    "归有光",
    "梁启超",
    "钱穆",
    "吕思勉",
    "陈寅恪",
    "王国维",
    "章太炎",
]

# 占位段落提示
PLACEHOLDER_PATTERNS = [
    r"未找到",
    r"没有明确评语",
    r"暂无点评",
]

# 现代 AI 味句式：不是X，是Y（每篇上限 3 处）
SOFT_AI_PATTERN = re.compile(r"不是[^，。；！？\n]{1,15}[而并]{1,2}是[^，。；！？\n]{1,15}")

# 引用标注冗余：正文已写明出处（在《XX》里/中），句末又挂「大意据《XX》」
REDUNDANT_CITATION_PATTERN = re.compile(r"在《[^》]+》[里中][^。\n]*（大意据《[^》]+》）")

# 现代术语硬套（描述古代历史时禁用；现代语境建议替换）
MODERN_JARGON_TERMS = ["底层逻辑", "底层操作系统"]

# 现代职场/商科专栏中可接受的中英文行业通用词（不算中英文混杂）
MODERN_ENGLISH_WHITELIST = [
    "KPI", "OKR", "HR", "PR", "CEO", "CFO", "CTO", "COO",
    "offer", "bug", "BATNA", "CRIB", "PPT", "DNA", "ID",
    "APP", "API", "PDF", "MBA", "EMBA", "VIP",
    "360度",  # 360度评价
]

# knowledge 桶（技术教程/知识体系）中可接受的中英文技术术语白名单
# 扩展历史:初版 27 词(AI 大模型学习专栏);2026-06 全栈知识边界专栏扩展 ~60 词;
# 2026-06 全栈专栏质检阶段补 AI/ID/CI/CD/Zookeeper(BUG-027 教训延续:每开新 knowledge 桶专栏必须先扩展白名单)
KNOWLEDGE_TERMS_WHITELIST = [
    # 模型/算法类
    "Transformer", "Attention", "Token", "Tokenizer", "Embedding",
    "RAG", "LLM", "GPT", "BERT", "GPU", "CPU", "TPU",
    # AI 时代核心术语(全栈专栏质检阶段补,2026-06)
    "AI",
    # 接口/协议类
    "API", "REST", "GraphQL", "gRPC",
    # 存储/数据库类
    "SQL", "NoSQL", "ACID", "BASE", "CAP",
    "RDBMS", "BTree", "LSM", "MVCC",
    # 具体数据库产品(全栈专栏质检阶段补,2026-06:书名《高性能MySQL》/正文 MongoDB/PostgreSQL)
    "MySQL", "PostgreSQL", "MongoDB", "MariaDB",
    # Python 术语(全栈专栏质检阶段补,2026-06:模块 docstring 是 PEP 257 常态术语)
    "docstring",
    # 职务/角色名(全栈专栏质检阶段补,2026-06:后端 Lead 是行业通用职务)
    "Lead",
    # 编程语言类
    "Python", "Java", "Rust",
    # 容器与编排(全栈专栏扩展,2026-06)
    "Docker", "Kubernetes", "K8s",
    # Web 服务器与中间件
    "Nginx", "Kafka", "RabbitMQ", "Redis",
    # 中间件-分布式协调(全栈专栏质检阶段补,2026-06)
    "Zookeeper",
    # 网络协议
    "HTTP", "HTTPS", "TCP", "UDP", "TLS", "DNS", "CDN", "WebSocket",
    # 安全
    "JWT", "OAuth", "XSS", "CSRF",
    # 分布式
    "Raft", "Paxos",
    # DevOps
    "Jenkins", "GitLab", "GitHub",
    # DevOps 核心缩写(全栈专栏质检阶段补,2026-06)
    "CI", "CD",
    # AI 工程化
    "MCP",
    # 运行时
    "JVM", "GC", "GIL",
    # 框架
    "Spring", "Django", "Flask", "FastAPI", "Vue", "React", "Webpack", "Babel",
    # 架构方法
    "DDD", "TDD", "BDD", "ORM", "DAO",
    # 缓存
    "LRU", "LFU",
    # 渲染
    "SSR", "CSR", "SSG", "SPA",
    # 云服务
    "SaaS", "PaaS", "IaaS", "FaaS",
    # 监控
    "SLA", "SLO",
    # Python web 与前端基础
    "WSGI", "ASGI", "HTML", "CSS", "JSON", "XML", "DOM", "URL",
    # 通用标识/业务术语(全栈专栏质检阶段补,2026-06)
    "ID",
]

# 现代职场专栏中过于敏感、易误报的 AI 味模式（由 check_soft_ai_pattern 等专项接管）
MODERN_AI_OVERSTRICT_PATTERNS = [
    r"不是.*而是",        # 「不是X而是Y」常见中文判断句，已由 check_soft_ai_pattern 控量
    r"他不是.*是",        # 同上
    r"容易被忽略",        # 常见中文，非AI套路
    r"可见",              # 常见中文，非AI套路
    r"第[一二三四五六]层", # 分点结构常见，非AI套路
    r"最关键的.*是",      # 常见中文，非AI套路
    r"这说明",            # 常见中文，非AI套路
    r"这事说明",          # 常见中文，非AI套路
]

# 常见错别字
COMMON_TYPOS = {
    "做为": "作为",
    "按耐": "按捺",
    "交待": "交代",
    "既使": "即使",
    "那怕": "哪怕",
    "必竞": "毕竟",
    "凑和": "凑合",
    "甘败下风": "甘拜下风",
    "一愁莫展": "一筹莫展",
    "美仑美奂": "美轮美奂",
    "不径而走": "不胫而走",
    "黄梁美梦": "黄粱美梦",
    "竭泽而鱼": "竭泽而渔",
    "棉薄之力": "绵薄之力",
    "墨守陈规": "墨守成规",
    "磬竹难书": "罄竹难书",
    "趋之若骛": "趋之若鹜",
    "声名雀起": "声名鹊起",
    "谈笑风声": "谈笑风生",
    "委屈求全": "委曲求全",
    "不能自己": "不能自已",
    "一如继往": "一如既往",
    "仗义直言": "仗义执言",
    "走头无路": "走投无路",
    "饮鸠止渴": "饮鸩止渴",
    "顶力相助": "鼎力相助",
    "不加思索": "不假思索",
    "按步就班": "按部就班",
}

@dataclass
class ContentQualityReport:
    """内容质检报告。"""

    passed: bool
    score: int
    issues: List[str] = field(default_factory=list)
    details: Dict[str, List[str]] = field(default_factory=dict)


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
    body = strip_frontmatter(content)
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
    """启发式检查关键年份是否给出。

    仅对 narrative 桶调用（modern/knowledge 在 run_content_quality_checks 中按 archetype 跳过）。
    """
    body = strip_frontmatter(content)
    if not YEAR_PATTERN.search(body):
        return ["正文未检测到关键年份/时间标注，请确认是否需要补充"]
    return []


def check_famous_critics(content: str) -> List[str]:
    """启发式检查是否有非司马光名家。

    仅对 narrative 桶调用（modern/knowledge 在 run_content_quality_checks 中按 archetype 跳过）。
    """
    body = strip_frontmatter(content)

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
    body = strip_frontmatter(content)
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
    pattern = re.compile(r"（[^）]*(?:见|详见|参见)[^）]*(?:章|前文|上文|下文/后文|讲故事|讲事情|相关章节|此处不赘)[^）]*）")
    for match in pattern.finditer(content):
        issues.append(f"疑似跨章跳转提示：{match.group()}")
    return issues


def check_mixed_language_knowledge(content: str) -> List[str]:
    """knowledge 桶版中英文混杂检查，剔除技术术语白名单。"""
    body = strip_frontmatter(content)
    cleaned = body
    # 按长度降序替换，避免短词部分替换长词（如 Token 先替换会破坏 Tokenizer）
    for word in sorted(KNOWLEDGE_TERMS_WHITELIST, key=len, reverse=True):
        cleaned = cleaned.replace(word, "×" * len(word))
    matches = re.findall(r"[\u4e00-\u9fff]+[a-zA-Z]{2,}", cleaned)
    if matches:
        return [f"检测到可能的中英文混杂：{matches[:3]}"]
    return []


def _filter_numeric_manual(manual_review: List[dict], archetype: str) -> List[dict]:
    """按 archetype 过滤 check_numeric_facts 的 manual_review 误标。

    narrative 桶：保留全部（N年前后/N岁/N品官 在古籍中需核验是否记错）
    modern/knowledge 桶：过滤 N年前后/N岁（现代语境"10年前""30岁"是正常表达）
    """
    if archetype == "narrative":
        return manual_review
    return [
        item for item in manual_review
        if not re.match(r"\d+年[前后]", item["pattern"])
        and not re.match(r"\d+岁", item["pattern"])
    ]


def _check_soul_dimension(content: str, cliches_result: dict) -> List[str]:
    """灵魂维度自动检查（content-quality.md §9.1/9.2/9.3/9.4）。

    §9.1 灵魂三问用启发式近似（无需 LLM，纯 AI 闭环）：
    - 活人测试：检测两难困境词 + 标签词密度
    - 洞察独家性：检测绝对化"正确废话"词
    - 底色敬畏感：检测戏谑/爽化词

    §9.2/9.3/9.4 已实现：
    - §9.2 AI 套话黑名单（命中 ≥3 次扣 5 分）
    - §9.3 数字事实硬错误（每项扣 3 分，上限 15）
    - §9.4 章回体灵魂标题（单标题 <3 分需重写，每个低分标题扣 2 分）

    cliches_result 复用主流程已跑的 check_ai_cliches 结果，避免重复扫描。
    """
    issues: List[str] = []
    body = strip_frontmatter(content)

    # §9.1 灵魂三问启发式近似
    issues.extend(_check_soul_three_questions(body))

    # §9.2 AI 套话黑名单
    if cliches_result["level"] == "warning":
        issues.append(
            f"灵魂维度-§9.2 AI套话黑名单命中 {cliches_result['count']} 次"
        )
    # §9.3 数字事实硬错误（auto_errors 已在 truth 维度逐条记录，
    # 这里只做灵魂维度的"是否命中"信号——命中任一即触发灵魂扣分）
    numeric_result = check_numeric_facts(body)
    if numeric_result["auto_errors"]:
        issues.append(
            f"灵魂维度-§9.3 数字事实硬错误 {len(numeric_result['auto_errors'])} 项"
        )
    # §9.4 章回体灵魂标题：提取所有 ## 小标题，单标题 <3 分记为问题
    # section_template 必需短标题（结语/问道/讲道理等结构标签）跳过检查，
    # 它们是章节结构必需，非内容标题，check_chapter_title_soul 会误判为事件标签。
    _SECTION_TEMPLATE_TITLES = {
        "讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语",
        "入戏", "破题", "方法论", "避坑", "践行",
        "概念", "原理", "实践", "速查", "自测", "速查/自测",
    }
    title_pattern = re.compile(r"^##\s+(.+?)$", re.MULTILINE)
    low_score_titles = 0
    for m in title_pattern.finditer(body):
        raw_title = m.group(1).strip()
        # 剥离 "序号、" 前缀（如 "一、备棺" → "备棺"）
        title_text = re.sub(r"^[\d一二三四五六七八九十百]+[、.]\s*", "", raw_title)
        if title_text in _SECTION_TEMPLATE_TITLES:
            continue
        result = check_chapter_title_soul(title_text)
        if result["score"] < 3:
            low_score_titles += 1
            issues.append(
                f"灵魂维度-§9.4 标题灵魂不足（{result['score']}分）：{raw_title}"
            )
    return issues


# --- §9.1 灵魂三问启发式 -----------------------------------------------
# 三问无正则可完美近似，但可用启发式做粗略自动评分让闭环跑通：
# - 活人测试：无两难词 + 标签词密集 → 人物是标签而非活人
# - 洞察独家性：绝对化"正确废话"词密集 → 洞察不独家
# - 底色敬畏感：戏谑/爽化词命中 → 缺敬畏感
_DILEMMA_WORDS = re.compile(r"两难|进退|取舍|抉择|左右为难|进退维谷|骑虎难下|举棋不定")
_LABEL_WORDS = re.compile(r"奸臣|忠臣|伟人|明君|昏君|暴君|昏庸|英明|昏聩|贤明|佞臣")
_ABSOLUTE_WORDS = re.compile(r"任何|所有|一切|总是|必然|都会|都是|从来|永远|毫无例外")
_FLIPPANT_WORDS = re.compile(r"哈哈|233|666|牛逼|卧槽|我去|6666|草|艹|哈哈|呵呵|笑死|赢麻|爽翻|炸裂")


def _check_soul_three_questions(body: str) -> List[str]:
    """§9.1 灵魂三问启发式近似（纯 AI 闭环，无需 LLM）。

    Returns:
        issues 列表，每项为扣分触发说明。
    """
    issues: List[str] = []

    # §9.1.1 活人测试：无两难困境词 + 标签词密集 → 人物是标签
    has_dilemma = bool(_DILEMMA_WORDS.search(body))
    label_count = len(_LABEL_WORDS.findall(body))
    if not has_dilemma and label_count >= 3:
        issues.append(
            f"灵魂维度-§9.1 活人测试失败：无两难困境词，标签词密集（{label_count}次），人物是标签"
        )

    # §9.1.2 洞察独家性：绝对化"正确废话"词密集 → 洞察不独家
    # 阈值 5：叙述性历史文本常含"任何/所有"等词描述规律，3 太敏感误判黄金样本
    absolute_count = len(_ABSOLUTE_WORDS.findall(body))
    if absolute_count >= 5:
        issues.append(
            f"灵魂维度-§9.1 洞察独家性失败：绝对化词密集（{absolute_count}次），疑似正确废话"
        )

    # §9.1.3 底色敬畏感：戏谑/爽化词命中 → 缺敬畏感
    flippant_hits = _FLIPPANT_WORDS.findall(body)
    if flippant_hits:
        issues.append(
            f"灵魂维度-§9.1 底色敬畏感失败：戏谑/爽化词命中 {len(flippant_hits)} 次"
        )
    return issues


def check_soft_ai_pattern(content: str, max_count: int = 3) -> List[str]:
    """检查「不是X，是Y」软性 AI 句式是否超过上限。"""
    body = strip_frontmatter(content)
    matches = SOFT_AI_PATTERN.findall(body)
    if len(matches) > max_count:
        return [
            f"「不是X，是Y」句式偏多：{len(matches)} 处，建议不超过 {max_count} 处"
        ]
    return []


def check_redundant_citation(content: str) -> List[str]:
    """检查引用标注冗余：正文已写明出处，句末又挂「大意据《XX》」。"""
    body = strip_frontmatter(content)
    matches = REDUNDANT_CITATION_PATTERN.findall(body)
    return [f"引用标注冗余：正文已写明出处，句末又挂「大意据《XX》」"] if matches else []


def check_modern_jargon_terms(content: str) -> List[str]:
    """检查现代术语硬套（底层逻辑、底层操作系统等）。"""
    body = strip_frontmatter(content)
    issues = []
    for term in MODERN_JARGON_TERMS:
        if term in body:
            count = body.count(term)
            issues.append(f"现代术语硬套：「{term}」出现 {count} 处，建议替换为更朴素表达")
    return issues


def check_mixed_language_modern(content: str) -> List[str]:
    """现代职场专栏版中英文混杂检查，剔除行业通用词白名单。"""
    body = strip_frontmatter(content)
    # 先把白名单词替换为占位，避免误报
    cleaned = body
    for word in MODERN_ENGLISH_WHITELIST:
        cleaned = cleaned.replace(word, "×" * len(word))
    matches = re.findall(r"[\u4e00-\u9fff]+[a-zA-Z]{2,}", cleaned)
    if matches:
        return [f"检测到可能的中英文混杂：{matches[:3]}"]
    return []


def filter_ai_tone_for_modern(issues: List[str]) -> List[str]:
    """现代职场专栏过滤掉过于敏感、易误报的 AI 味模式。"""
    filtered = []
    for issue in issues:
        # issue 形如 "疑似 AI 味句式：不是.*而是"
        if "疑似 AI 味句式：" not in issue:
            filtered.append(issue)
            continue
        pattern = issue.split("：", 1)[1]
        if pattern in MODERN_AI_OVERSTRICT_PATTERNS:
            continue
        filtered.append(issue)
    return filtered


def check_common_typos(content: str) -> List[str]:
    """检查常见错别字。"""
    body = strip_frontmatter(content)
    issues = []
    for wrong, right in COMMON_TYPOS.items():
        if wrong in body:
            issues.append(f"错别字：「{wrong}」应为「{right}」")
    return issues


def check_title_hierarchy(content: str) -> List[str]:
    """检查标题层级：正文章节标题不应高于「## 参考来源」。

    若正文出现「^# 」（一级标题）且同时有「## 参考来源」，提示层级倒置。
    """
    body = strip_frontmatter(content)
    has_h1_chapter = bool(re.search(r"^# [^#]", body, re.MULTILINE))
    has_h2_sources = bool(re.search(r"^##\s*参考来源", body))
    # 允许首个 # 作为文档大标题
    h1_count = len(re.findall(r"^# [^#]", body, re.MULTILINE))
    if has_h2_sources and h1_count > 1:
        return ["标题层级倒置：正文用「#」而参考来源用「##」，建议章节统一为「##」"]
    return []


def check_temporal_order(content: str) -> List[str]:
    """启发式检查叙事顺序。

    仅对 narrative 桶调用（modern/knowledge 在 run_content_quality_checks 中按 archetype 跳过）。
    """
    body = strip_frontmatter(content)
    # 用 (?:^|\n) 匹配首段（strip 后 body 以 ## 开头，首个 ## 前无 \n）
    sections = re.split(r"(?:^|\n)## ", body)
    issues = []
    for section in sections:
        if section.startswith("讲事情"):
            if not YEAR_PATTERN.search(section):
                issues.append("讲事情段落缺少明确时间/年份标注")
            break
    return issues


def run_content_quality_checks(content: str, archetype: str = "narrative") -> ContentQualityReport:
    """运行完整内容质检，返回报告与分数。

    按 archetype 路由规则集（design.md §8）：
    - narrative：古籍专属规则全开（年份/名家/时间线/现代术语禁用）
    - modern/knowledge：跳过古籍专属规则，放宽 AI 味检测，用对应桶白名单
    - 通用检查（check_ai_cliches / check_numeric_facts auto）全桶都跑
    - numeric manual_review 按 archetype 过滤误标（narrative 保留，modern/knowledge 过滤 N年前后/N岁）
    """
    issues: List[str] = []
    details: Dict[str, List[str]] = {}

    # archetype 合法性校验（fail-fast 优于静默误路由）
    # fiction 桶（"七实三虚"小说）按 modern 分支处理：跳过古籍专属规则，
    # 放宽 AI 味检测，用 modern 桶白名单（与 consistency.py 路由一致）
    if archetype not in ("narrative", "modern", "knowledge", "fiction"):
        raise ValueError(
            f"archetype 必须是 narrative/modern/knowledge/fiction 之一，收到：{archetype!r}"
        )

    is_non_narrative = archetype in ("modern", "knowledge", "fiction")

    # 1. 真实性
    details["truth"] = []
    # narrative 桶才检查年份/名家/时间线（古籍专属，modern/knowledge 跳过）
    if archetype == "narrative":
        details["truth"].extend(check_years_present(content))
        details["truth"].extend(check_famous_critics(content))
    details["truth"].extend(check_placeholder_sections(content))
    details["truth"].extend(check_common_typos(content))

    # check_numeric_facts（通用，全桶都跑；禁区红线：quality.py 内部零改动，调用层按 archetype 过滤 manual_review）
    # 注意：strip frontmatter 避免 frontmatter 中的数字（如 sort:1）被误标
    numeric_result = check_numeric_facts(strip_frontmatter(content))
    for err in numeric_result["auto_errors"]:
        details["truth"].append(
            f"数字事实硬错误：{err['pattern']}（应为 {err['expected']}，实际 {err['actual']}）"
        )
    for item in _filter_numeric_manual(numeric_result["manual_review"], archetype):
        details["truth"].append(
            f"数字事实需人工复核：{item['pattern']}（{item['reason']}）"
        )

    # 2. 可读性（复用并扩展 quality.py）
    details["readability"] = []
    ai_tone_issues = check_ai_tone(content)
    ai_tone_issues = _filter_natural_expressions(ai_tone_issues, content)
    # modern/knowledge 桶放宽 AI 味检测（过滤过于敏感的模式，由 check_soft_ai_pattern 等专项接管控量）
    if is_non_narrative:
        ai_tone_issues = filter_ai_tone_for_modern(ai_tone_issues)
    details["readability"].extend(ai_tone_issues)
    # check_modern_jargon（quality.py 古籍向，禁用「底层逻辑」等词）仅 narrative 桶跑
    if archetype == "narrative":
        details["readability"].extend(check_modern_jargon(content))
    # 中英文混杂检查按桶选白名单
    # fiction 桶用 modern 白名单（商战小说含 Standard Oil/John D. Rockefeller 等英文术语）
    if archetype in ("modern", "fiction"):
        details["readability"].extend(check_mixed_language_modern(content))
    elif archetype == "knowledge":
        details["readability"].extend(check_mixed_language_knowledge(content))
    else:
        details["readability"].extend(check_mixed_language(content))
    details["readability"].extend(check_sublimation_quota(content))
    # check_internal_repetition 仅 narrative 桶跑(BUG-027 教训延续):
    # knowledge 桶用「」做中英对照/章节标题引用是常态,会被误报为"古文/金句重复";
    # modern 桶同理(职场课可能引用书名「XXX」)。古文金句重复只针对历史叙事。
    if archetype == "narrative":
        details["readability"].extend(check_internal_repetition(content))
    details["readability"].extend(check_soft_ai_pattern(content))
    details["readability"].extend(check_modern_jargon_terms(content))
    details["readability"].extend(check_title_hierarchy(content))

    # check_ai_cliches（通用，全桶都跑；命中 ≥3 次为 warning）
    cliches_result = check_ai_cliches(strip_frontmatter(content))
    if cliches_result["level"] == "warning":
        details["readability"].append(
            f"AI套话黑名单命中 {cliches_result['count']} 次：{cliches_result['hits']}"
        )

    # 3. 顺序（narrative 桶才检查历史时间线）
    details["sequence"] = []
    if archetype == "narrative":
        details["sequence"].extend(check_temporal_order(content))

    # 4. 引用克制
    details["citation"] = []
    details["citation"].extend(check_inline_references(content))
    details["citation"].extend(check_cross_chapter_jump(content))
    details["citation"].extend(check_citation_density(content))
    details["citation"].extend(check_sources_section(content))
    details["citation"].extend(check_redundant_citation(content))

    # 5. 灵魂维度（content-quality.md §9.2/9.3/9.4 自动部分；§9.1 三问仍需人工）
    details["soul"] = _check_soul_dimension(content, cliches_result)

    # 6. 一致性维度（consistency-rules.md §2，前后矛盾/数据交叉矛盾/实体不一致）
    # v1.2 新增：补齐"前后矛盾"检测缺口，纯规则无需 LLM
    consistency_report = check_consistency(content, archetype=archetype)
    details["consistency"] = [
        f"[{issue.severity}] {issue.message}" for issue in consistency_report.issues
    ]

    for key in details:
        issues.extend(details[key])

    # 计分：从 100 起扣（六维度，v1.2 新增 consistency 维度）
    score = 100
    score -= min(20, len(details["truth"]) * 5)            # 真实性问题每项扣 5 分，上限 20
    score -= min(20, len(details["readability"]) * 2)      # 可读性问题每项扣 2 分，上限 20
    score -= min(10, len(details["sequence"]) * 5)         # 顺序问题每项扣 5 分，上限 10
    score -= min(15, len(details["citation"]) * 3)         # 引用问题每项扣 3 分，上限 15
    score -= min(15, len(details["soul"]) * 3)             # 灵魂问题每项扣 3 分，上限 15
    # 一致性维度：用 ConsistencyReport.score（0-10）的反向作为扣分（10 分制）
    score -= (10 - consistency_report.score)
    score = max(0, score)

    return ContentQualityReport(
        passed=score >= 85 and consistency_report.passed,
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
        label = {
            "truth": "真实性",
            "readability": "可读性",
            "sequence": "顺序",
            "citation": "引用克制",
            "soul": "灵魂",
            "consistency": "一致性",
        }.get(category, category)
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
            "请按 `.trae/skills/deep-reading/content-quality.md` 中的修复优先级逐项处理。",
        ])
    return "\n".join(lines)
