"""一致性检测工具：检测 AI 生成内容的前后矛盾、数据交叉矛盾、实体不一致。

四类检测（详见 .trae/skills/content-review/rules/consistency-rules.md）：
1. 数值交叉矛盾（numeric_cross）：年龄-年份/在位时长/损失-剩余的数学矛盾
2. 同事件异值（same_event_diff_value）：同引文异字数/同战役异兵力/同典故异出处
3. 实体别名冲突（entity_alias）：字号/谥号/籍贯冲突
4. 时间线倒置（timeline_inversion）：年份逆序且无倒叙标注

设计原则：
- 纯规则，无需 LLM，结果可复现（与 check_char_count.py 同一信源哲学）
- 误报优先于漏报：宁可标记需人工复核，也不静默放过
- 与 quality.py 的 check_numeric_facts 互补：前者查单处数字对错，本模块查多个数字之间打架
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from src.utils.quality import _cn_to_int, _strip_punct_for_char_count, strip_frontmatter


# --- 数据结构 -----------------------------------------------------------------

@dataclass
class ConsistencyIssue:
    """单个一致性问题。"""

    type: str  # "numeric_cross" | "same_event_diff_value" | "entity_alias" | "timeline_inversion"
    severity: str  # "P0" | "P1" | "P2"
    message: str
    snippet: str
    locations: List[int] = field(default_factory=list)  # 行号列表


@dataclass
class ConsistencyReport:
    """一致性检测报告。"""

    issues: List[ConsistencyIssue] = field(default_factory=list)
    details: Dict[str, List[ConsistencyIssue]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """一致性维度通过门槛：得分 ≥ 7/10。"""
        return self.score >= 7

    @property
    def score(self) -> int:
        """一致性维度得分（0-10）。

        按类扣分封顶（与 consistency-rules.md §三 对齐）：
        - P0：每个扣 5 分，该类合计上限 10 分
        - P1：每个扣 3 分，该类合计上限 6 分
        - P2：每个扣 2 分，该类合计上限 4 分
        - 维度地板 0 分
        """
        p0_deduction = min(10, 5 * sum(1 for i in self.issues if i.severity == "P0"))
        p1_deduction = min(6, 3 * sum(1 for i in self.issues if i.severity == "P1"))
        p2_deduction = min(4, 2 * sum(1 for i in self.issues if i.severity == "P2"))
        return max(0, 10 - p0_deduction - p1_deduction - p2_deduction)


# --- 辅助函数 -----------------------------------------------------------------

def _line_of(text: str, pos: int) -> int:
    """根据字符位置反推行号（1-based）。"""
    return text.count("\n", 0, pos) + 1


def _parse_year(year_str: str) -> int:
    """解析年份为整数。支持：前170年=-170，公元140年=140，140年=140。

    无法解析返回 None。
    """
    if not year_str:
        return None
    s = year_str.strip()
    is_bc = False
    if s.startswith("前") or s.startswith("公元前"):
        is_bc = True
        s = re.sub(r"^(前|公元前)", "", s)
    # 去掉"年"字
    s = s.replace("年", "").strip()
    # 尝试阿拉伯数字
    if s.isdigit():
        return -int(s) if is_bc else int(s)
    # 尝试中文数字
    n = _cn_to_int(s)
    if n >= 0:
        return -n if is_bc else n
    return None


# --- 常见实体别名表（用于实体一致性检测） -----------------------------------

# v1.3 路标：别名归一化未启用。
# 当前 check_entity_alias_conflict 按 surface form 匹配（"曹操字孟德" 与 "曹操字子建" 报冲突），
# 尚未做别名归一（"曹孟德字X" 与 "曹操字Y" 视为同一实体）。本表保留 16 条常见别名作为
# v1.3 别名归一化的数据源，并被 checklist.md 引用为合法指代参考。在 v1.3 启用前，本表
# 不被任何函数引用——这是有意保留的预留数据，非沉默死代码。
ENTITY_ALIASES: Dict[str, List[str]] = {
    "曹操": ["孟德", "曹孟德", "魏武帝", "阿瞒"],
    "刘备": ["玄德", "刘玄德", "先主", "昭烈帝"],
    "诸葛亮": ["孔明", "诸葛孔明", "卧龙", "卧龙先生", "丞相", "武侯"],
    "关羽": ["云长", "关云长", "关公", "汉寿亭侯"],
    "张飞": ["翼德", "张翼德", "燕人"],
    "孙权": ["仲谋", "孙仲谋", "吴主", "大帝"],
    "司马懿": ["仲达", "司马仲达", "宣帝"],
    "司马光": ["君实", "温公", "涑水先生"],
    "司马迁": ["子长", "太史公"],
    "李世民": ["太宗", "唐太宗", "贞观"],
    "李世勣": ["徐世勣", "徐茂功", "茂功", "李勣"],
    "魏徵": ["魏征", "玄成", "郑国公"],
    "赵匡胤": ["太祖", "宋太祖", "香孩儿"],
    "王安石": ["介甫", "王介甫", "半山", "临川先生"],
    "苏轼": ["子瞻", "东坡", "苏东坡", "东坡居士"],
    "海瑞": ["汝贤", "刚峰", "海刚峰"],
}


# --- 1. 数值交叉矛盾 ---------------------------------------------------------

def check_numeric_cross_reference(content: str) -> List[ConsistencyIssue]:
    """检测数值交叉矛盾：年龄-年份/在位时长/损失-剩余的数学矛盾。

    检测模式：
    - 生年 + 继位年 + 年龄 → 验证 age = |reign - birth|
    - 继位年 + 去世年 + 在位年数 → 验证 duration = |death - reign|
    - 总数 + 损失 + 剩余 → 验证 remaining = total - loss
    """
    body = strip_frontmatter(content)
    issues: List[ConsistencyIssue] = []

    # 提取生年/卒年/继位年（全局，假设单篇主要讲一个人物）
    birth_years = _extract_year_mentions(body, [r"生于(前\d+|公元前\d+|\d+)年", r"出生[于在](前\d+|公元前\d+|\d+)年"])
    death_years = _extract_year_mentions(body, [
        r"卒于(前\d+|公元前\d+|\d+)年",
        r"去世[于在](前\d+|公元前\d+|\d+)年",
        r"病逝[于在](前\d+|公元前\d+|\d+)年",
        r"(前\d+|公元前\d+|\d+)年(?:去世|病逝|驾崩|崩)",
    ])
    reign_years = _extract_year_mentions(body, [
        r"(前\d+|公元前\d+|\d+)年(?:继位|即位|登基|称帝|称王|即皇帝位)",
        r"继位[于时](前\d+|公元前\d+|\d+)年",
    ])

    # 提取年龄声明（支持 "N岁继位" 和 "继位时N岁" 两种语序）
    # 注意：filler 仅允许 [之又又] 等连接虚词，禁止 \S（避免吞掉 "15" 中的 "1"）
    age_patterns = [
        r"(\d+)岁(?:继位|即位|登基|称帝|称王|即位|主政|亲政)",
        r"(?:继位|即位|登基|称帝|称王|主政|亲政)时[之又]?(\d+)岁",
        r"(\d+)岁(?:时|那年|时便)",
    ]
    age_claims = _extract_numeric_claims(body, age_patterns)

    # 提取在位年数
    reign_duration_claims = _extract_numeric_claims(body, [r"在位(\d+)年", r"在位(?:共|长达)?(\d+)年"])

    # 检查 1: 年龄 = |继位年 - 生年|
    if birth_years and reign_years and age_claims:
        birth_year = birth_years[0]["value"]
        reign_year = reign_years[0]["value"]
        expected_age = abs(reign_year - birth_year)
        for age_claim in age_claims:
            actual_age = age_claim["value"]
            if actual_age != expected_age and expected_age > 0:
                snippet = f"生于{abs(birth_year)}年({'前' if birth_year < 0 else ''}) + {'前' if reign_year < 0 else ''}{abs(reign_year)}年继位 → 应 {expected_age} 岁，文中称 {actual_age} 岁"
                issues.append(ConsistencyIssue(
                    type="numeric_cross",
                    severity="P0",
                    message=f"年龄与生年/继位年数学矛盾：{snippet}",
                    snippet=snippet,
                    locations=[age_claim["line"]],
                ))
                break  # 同类矛盾只报一次，避免刷屏

    # 检查 2: 在位年数 = |去世年 - 继位年|
    if reign_years and death_years and reign_duration_claims:
        reign_year = reign_years[0]["value"]
        death_year = death_years[0]["value"]
        expected_duration = abs(death_year - reign_year)
        for dur_claim in reign_duration_claims:
            actual_duration = dur_claim["value"]
            if actual_duration != expected_duration and expected_duration > 0:
                snippet = f"{'前' if reign_year < 0 else ''}{abs(reign_year)}年继位 + {'前' if death_year < 0 else ''}{abs(death_year)}年去世 → 应在位 {expected_duration} 年，文中称 {actual_duration} 年"
                issues.append(ConsistencyIssue(
                    type="numeric_cross",
                    severity="P0",
                    message=f"在位年数与继位/去世年数学矛盾：{snippet}",
                    snippet=snippet,
                    locations=[dur_claim["line"]],
                ))
                break

    # 检查 3: 损失-剩余数学矛盾（局部上下文窗口）
    loss_pattern = re.compile(r"损失(?:了)?(\d+万?千?百?|[\u4e00-\u9fff]{1,4})")
    remaining_pattern = re.compile(r"剩(?:下|余)?(?:\d+万?千?百?|[\u4e00-\u9fff]{1,4})")
    # 这个检查较复杂，需要 total-loss-remaining 三者共现，启发式：找"损失"和"剩"在同一句或相邻句
    for m in re.finditer(r"([一二三四五六七八九十百千万两\d]+万人?)[，,。；]?(?:[^。！？\n]{0,30})?损失(?:了)?([一二三四五六七八九十百千万两\d]+万人?)[，,。；]?(?:[^。！？\n]{0,30})?剩(?:下|余)?([一二三四五六七八九十百千万两\d]+万人?)", body):
        total = _cn_to_int(m.group(1).replace("万", "").replace("人", ""))
        loss = _cn_to_int(m.group(2).replace("万", "").replace("人", ""))
        remaining = _cn_to_int(m.group(3).replace("万", "").replace("人", ""))
        if total >= 0 and loss >= 0 and remaining >= 0:
            # 归一化万人/千人（启发式：含"万"则 ×10000）
            t_mul = 10000 if "万" in m.group(1) else 1
            l_mul = 10000 if "万" in m.group(2) else 1
            r_mul = 10000 if "万" in m.group(3) else 1
            total *= t_mul
            loss *= l_mul
            remaining *= r_mul
            if total - loss != remaining and total > 0:
                snippet = m.group(0)[:80]
                line = _line_of(body, m.start())
                issues.append(ConsistencyIssue(
                    type="numeric_cross",
                    severity="P0",
                    message=f"损失-剩余数学矛盾：{total} - {loss} ≠ {remaining}（应为 {total - loss}）",
                    snippet=snippet,
                    locations=[line],
                ))

    return issues


def _extract_year_mentions(body: str, patterns: List[str]) -> List[dict]:
    """提取年份声明，返回 [{value, line, snippet}]。"""
    results = []
    for pattern in patterns:
        for m in re.finditer(pattern, body):
            year_val = _parse_year(m.group(1))
            if year_val is not None:
                results.append({
                    "value": year_val,
                    "line": _line_of(body, m.start()),
                    "snippet": m.group(0),
                })
    return results


def _extract_numeric_claims(body: str, patterns: List[str]) -> List[dict]:
    """提取数值声明，返回 [{value, line, snippet}]。"""
    results = []
    for pattern in patterns:
        for m in re.finditer(pattern, body):
            raw = m.group(1)
            val = _cn_to_int(raw) if not raw.isdigit() else int(raw)
            if val >= 0:
                results.append({
                    "value": val,
                    "line": _line_of(body, m.start()),
                    "snippet": m.group(0),
                })
    return results


# --- 2. 同事件异值 -----------------------------------------------------------

def check_same_event_diff_value(content: str) -> List[ConsistencyIssue]:
    """检测同事件异值：同引文异字数/同战役异兵力/同典故异出处。

    与 check_char_count.py 的区别：前者查单处字数对错，本函数查跨段同引文字数是否前后不一。
    """
    body = strip_frontmatter(content)
    issues: List[ConsistencyIssue] = []

    # 检查 1: 同引文异字数
    # 提取所有 "「X」这 N 个字" 模式，按引文 X 分组，检查 N 是否一致
    # 注意：跨段一致性比较的是"声明值"之间是否一致，不跳过单处字数错误
    # （单处字数错误由 check_char_count.py 覆盖，跨段不一致由本函数覆盖）
    quote_char_pattern = re.compile(
        r"[「『\"]([^」』\"]{1,30})[」』\"][\s。，；—…、\-]{0,5}这?\s*([一二三四五六七八九十百千万两\d]+)\s*个字"
    )
    quote_char_counts: Dict[str, List[dict]] = {}
    for m in quote_char_pattern.finditer(body):
        quote_text = m.group(1)
        count_raw = m.group(2)
        count = _cn_to_int(count_raw) if not count_raw.isdigit() else int(count_raw)
        if count < 0:
            continue
        quote_char_counts.setdefault(quote_text, []).append({
            "claimed_count": count,
            "line": _line_of(body, m.start()),
            "snippet": m.group(0),
        })

    for quote, claims in quote_char_counts.items():
        if len(claims) < 2:
            continue
        counts = {c["claimed_count"] for c in claims}
        if len(counts) > 1:
            # 同引文不同字数声明
            lines = [c["line"] for c in claims]
            snippet = f"引文「{quote}」出现 {len(claims)} 次，字数声明不一致：{sorted(counts)}"
            issues.append(ConsistencyIssue(
                type="same_event_diff_value",
                severity="P0",
                message=f"同引文异字数：{snippet}",
                snippet=snippet,
                locations=lines,
            ))

    # 检查 2: 同战役异兵力
    # 提取 "X之战" + 附近 "N万大军/N万人/N千兵马" 等兵力数字
    battle_pattern = re.compile(r"([\u4e00-\u9fff]{2,6}(?:之战|之役|战役|大战))")
    troop_pattern = re.compile(r"([一二三四五六七八九十百千万两\d]+万?(?:人|大军|兵马|铁骑|骑兵|步卒))")
    # 攻防动词：同窗口内若同时出现 2+ 兵力数字 + 攻防动词，
    # 视为"攻方破守方"句式（两个数字分属不同阵营），不参与"同战役异兵力"比较。
    # 覆盖两种语态：
    #   主动："X之战，A率N1万破B的N2万"
    #   被动："X之战N2万被A的N1万打垮" / "X之战N2万被A的N1万冲散"
    # 攻防动词：保留单字根词即可覆盖其多字组合（"破"覆盖"大破/攻破/击破"，
    # "溃"覆盖"击溃"，"歼"覆盖"全歼"，"覆"覆盖"覆灭"），避免子串冗余。
    _ATTACK_DEFENSE_VERBS = (
        "破", "败", "擒", "灭", "斩", "打垮", "溃", "歼",
        "覆", "冲散", "击退", "杀退", "杀散", "冲垮",
    )
    # 虚数前缀：以"数/几"开头的兵力数字是虚指（"数十万人"/"几百万人"），非精确兵力，
    # 跨段比较虚数与实数无意义，统一跳过
    _VAGUE_NUMBER_PREFIXES = ("数", "几")
    # 虚数后缀：数字末尾含"余/来/多"的是虚指（"三十余万"/"二十来万"/"三十多万"），非精确兵力
    _VAGUE_NUMBER_SUFFIXES = ("余", "来", "多")
    # 句末标点：用于限定同句窗口，避免跨句误抓
    _SENTENCE_END = "。！？!?\n"

    battle_troops: Dict[str, List[dict]] = {}
    for bm in battle_pattern.finditer(body):
        battle_name = bm.group(1)
        # 兵力数字通常跟在战役名之后（"X之战，Y率N万大军"），
        # 向前看 15 字符；不向后看，避免多战一句中误抓邻战兵力
        window_start = bm.end()
        raw_window_end = min(len(body), bm.end() + 15)
        # 限定同句：窗口内若遇句末标点，截断到第一个句末标点之前
        sentence_end_pos = -1
        for i in range(window_start, raw_window_end):
            if body[i] in _SENTENCE_END:
                sentence_end_pos = i
                break
        window_end = sentence_end_pos if sentence_end_pos >= 0 else raw_window_end
        window = body[window_start:window_end]
        window_matches = list(troop_pattern.finditer(window))
        # 攻防句式豁免：窗口内 2+ 兵力数字 + 攻防动词 → 跨阵营不可比，整窗跳过
        if len(window_matches) >= 2 and any(verb in window for verb in _ATTACK_DEFENSE_VERBS):
            continue
        for tm in window_matches:
            raw = tm.group(1)
            # 虚数豁免：以"数/几"开头的是虚指（"数十万人"），不参与跨段比较
            if raw.startswith(_VAGUE_NUMBER_PREFIXES):
                continue
            # 1. 先剥离单位后缀（大军/兵马/人 等），保留"万"
            unit_stripped = re.sub(r"(大军|兵马|铁骑|骑兵|步卒|人)$", "", raw)
            # 2. 再剥离"万"，记录是否含万
            has_wan = "万" in unit_stripped
            num_part = unit_stripped.replace("万", "")
            # 3. 解析数字（_cn_to_int 不识别"万"作乘数，需先剥离）
            # 虚数后缀豁免：末尾含"余/来/多"的是虚指（"三十余万"），不参与跨段比较
            if num_part and num_part[-1] in _VAGUE_NUMBER_SUFFIXES:
                continue
            val = _cn_to_int(num_part) if not num_part.isdigit() else int(num_part)
            if val < 0:
                continue
            # 误报防护：兵力数字 < 100 几乎不可能是兵力（"五十二" 可能是 "五十二里" 误抓）
            mul = 10000 if has_wan else 1
            if val * mul < 100:
                continue
            battle_troops.setdefault(battle_name, []).append({
                "troops": val * mul,
                "line": _line_of(body, window_start + tm.start()),
                "snippet": tm.group(0),
            })

    for battle, claims in battle_troops.items():
        if len(claims) < 2:
            continue
        troops = {c["troops"] for c in claims}
        if len(troops) > 1:
            lines = [c["line"] for c in claims]
            snippet = f"{battle}兵力声明不一致：{sorted(troops)}"
            issues.append(ConsistencyIssue(
                type="same_event_diff_value",
                severity="P1",
                message=f"同战役异兵力：{snippet}",
                snippet=snippet,
                locations=lines,
            ))

    # 检查 3: 同典故异出处
    # "「X」出自《Y》" / "「X」语出《Y》" / "「X」见《Y》"
    quote_source_pattern = re.compile(
        r"[「『\"]([^」』\"]{2,15})[」』\"]\s*(?:出自|语出|语本|见于?|见|载于)\s*《([^》]+)》"
    )
    quote_sources: Dict[str, List[dict]] = {}
    for m in quote_source_pattern.finditer(body):
        quote = m.group(1)
        source = m.group(2)
        quote_sources.setdefault(quote, []).append({
            "source": source,
            "line": _line_of(body, m.start()),
            "snippet": m.group(0),
        })

    for quote, claims in quote_sources.items():
        if len(claims) < 2:
            continue
        sources = {c["source"] for c in claims}
        if len(sources) > 1:
            lines = [c["line"] for c in claims]
            snippet = f"典故「{quote}」出处不一致：{sorted(sources)}"
            issues.append(ConsistencyIssue(
                type="same_event_diff_value",
                severity="P1",
                message=f"同典故异出处：{snippet}",
                snippet=snippet,
                locations=lines,
            ))

    return issues


# --- 3. 实体别名冲突 ---------------------------------------------------------

def check_entity_alias_conflict(content: str) -> List[ConsistencyIssue]:
    """检测实体别名冲突：字号/谥号/籍贯冲突。

    检测模式：
    - "X字Y" 结构化声明 → 同一 X 不应有不同 Y
    - "X谥Y" / "X的谥号是Y" → 同一 X 谥号一致
    - "X，A地人" → 同一 X 籍贯一致
    """
    body = strip_frontmatter(content)
    issues: List[ConsistencyIssue] = []

    # 提取"字"声明：X字Y / X，字Y
    # 字号一般 1-2 字（孟德/玄成/辅机/孔明），3 字极少（曹孟德=姓名连字，不在此列）
    # 要求字号后跟句读或连接词，避免 "字玄成须" 误抓 "玄成须"
    zi_pattern = re.compile(
        r"([\u4e00-\u9fff]{2,4})[，,]?\s*字\s*([\u4e00-\u9fff]{1,2})(?=[，,。；：\s、与和及或/）】\"])"
    )
    shi_pattern = re.compile(
        r"([\u4e00-\u9fff]{2,4})(?:的)?谥(?:号[为是曰])?\s*([\u4e00-\u9fff]{1,4}[王帝公侯伯])(?=[，,。；：\s、与和及或/）】\"])"
    )
    # 籍贯声明：严格匹配三种结构，避免误报
    # 1) X，Y[县州]人 - 名字+逗号+地名+人
    # 2) X是Y[县州]人 - 名字+是+地名+人
    # 3) Y[县州]人X - 地名+人+名字（濮州人王仙芝）
    native_pattern = re.compile(
        r"([\u4e00-\u9fff]{2,4})(?:[，,]|是)\s*([\u4e00-\u9fff]{2,6}[县州]人)(?=[，,。；：\s、与和及或/）】\"])"
        r"|"
        r"([\u4e00-\u9fff]{2,6}[县州]人)([\u4e00-\u9fff]{2,4})(?=[，,。；：\s、与和及或/）】\"])"
    )

    entity_zi: Dict[str, List[dict]] = {}
    entity_shi: Dict[str, List[dict]] = {}
    entity_native: Dict[str, List[dict]] = {}

    for m in zi_pattern.finditer(body):
        name = m.group(1)
        zi = m.group(2)
        # 排除常见误匹配（"另外字" "数字" "四个字" "两个字" 等）
        # 数字量词误抓：含中文数字/量词前缀的不是人名
        excluded_names = {
            "另外", "数字", "汉字", "名字", "八字", "十字", "字体", "字母",
            "两个", "三个", "四个", "五个", "六个", "七个", "八个", "九个", "十个",
            "这个数", "那个数", "前一个", "后一个", "上一字", "下一字",
            "前面字", "后面字", "上面字", "下面字", "一段字", "一句字",
            "百字", "千字", "万字", "一个汉", "两个汉", "几个汉",
        }
        if name in excluded_names:
            continue
        # 数字开头的"X个"也不算人名
        if re.match(r"^[一二三四五六七八九十百千万两]\s*个?$", name):
            continue
        entity_zi.setdefault(name, []).append({
            "value": zi,
            "line": _line_of(body, m.start()),
            "snippet": m.group(0),
        })

    for m in shi_pattern.finditer(body):
        name = m.group(1)
        shi = m.group(2)
        entity_shi.setdefault(name, []).append({
            "value": shi,
            "line": _line_of(body, m.start()),
            "snippet": m.group(0),
        })

    for m in native_pattern.finditer(body):
        # 三种匹配模式：group(1)+group(2) 或 group(3)+group(4)
        if m.group(1) and m.group(2):
            # 模式1/2: X(，/是)Y[县州]人 → name=Y[县州]人
            name = m.group(1)
            native = m.group(2)
        elif m.group(3) and m.group(4):
            # 模式3: Y[县州]人X → name=X, native=Y[县州]人
            name = m.group(4)
            native = m.group(3)
        else:
            continue
        if name in ("这位", "此人", "先生", "其中", "当时", "后来", "等等", "如今", "那时"):
            continue
        # 排除过于通用的"名字"误抓（"其中县" "如今县" 等）
        if len(name) < 2:
            continue
        entity_native.setdefault(name, []).append({
            "value": native,
            "line": _line_of(body, m.start()),
            "snippet": m.group(0),
        })

    # 检查字号冲突
    for name, claims in entity_zi.items():
        if len(claims) < 2:
            continue
        zis = {c["value"] for c in claims}
        if len(zis) > 1:
            lines = [c["line"] for c in claims]
            snippet = f"{name}的字号声明不一致：{sorted(zis)}"
            issues.append(ConsistencyIssue(
                type="entity_alias",
                severity="P0",
                message=f"字号冲突：{snippet}",
                snippet=snippet,
                locations=lines,
            ))

    # 检查谥号冲突
    for name, claims in entity_shi.items():
        if len(claims) < 2:
            continue
        shis = {c["value"] for c in claims}
        if len(shis) > 1:
            lines = [c["line"] for c in claims]
            snippet = f"{name}的谥号声明不一致：{sorted(shis)}"
            issues.append(ConsistencyIssue(
                type="entity_alias",
                severity="P0",
                message=f"谥号冲突：{snippet}",
                snippet=snippet,
                locations=lines,
            ))

    # 检查籍贯冲突
    for name, claims in entity_native.items():
        if len(claims) < 2:
            continue
        natives = {c["value"] for c in claims}
        if len(natives) > 1:
            lines = [c["line"] for c in claims]
            snippet = f"{name}的籍贯声明不一致：{sorted(natives)}"
            issues.append(ConsistencyIssue(
                type="entity_alias",
                severity="P1",
                message=f"籍贯冲突：{snippet}",
                snippet=snippet,
                locations=lines,
            ))

    return issues


# --- 4. 时间线倒置 -----------------------------------------------------------

# 倒叙标注词（出现这些词则不报时间线倒置）
# 覆盖五类合法倒叙结构：
#   1. 显式回顾词：此前/之前/回顾/回过头...
#   2. 时间相对表述：上一年/前一年/X年前/多年前
#   3. 早字系列：早在/早先/早就（"早就埋下了"等倒叙提示）
#   4. 叙事提示语：得先讲清/要讲清/话说回/话说当年/前因/来龙去脉/起因还得从/往前推
#   5. 句式：要理解X得先Y / 已经X年了（"已经十几年了"回顾起点）
_FLASHBACK_MARKERS = re.compile(
    r"此前|之前|回顾|回过头|当年早些时候|更早|在此之[前先]|"
    r"上一年|前一年|三年前|两年前|一年前|多年前|"
    r"早[在先就]|"
    r"得先讲清|要讲清|先把镜头拉回|话说回|话说当年|"
    r"前因|来龙去脉|起因还得从|往前推|"
    r"要理解.{0,8}得先|"
    r"已经.{0,4}年"
)


def check_timeline_inversion(content: str) -> List[ConsistencyIssue]:
    """检测时间线倒置：讲事情段落年份逆序且无倒叙标注。

    仅对 narrative 桶有意义（modern/knowledge 通常无年份序列）。

    支持两种年份格式：
    - 绝对年份：前170年 / 公元前140年 / 140年（按数值比较）
    - 年号年份：建安十三年 / 元封元年（同年号内按年数比较）
    """
    body = strip_frontmatter(content)
    issues: List[ConsistencyIssue] = []

    # 时间线倒置只在 narrative 桶的"讲事情"段落检查
    # （modern/knowledge 桶常讨论未来计划/历史回顾，年份序列不代表叙事顺序）
    # 若无 ## 讲事情 段落，跳过检测（避免对整文误报）
    section_match = re.search(r"##\s*讲事情(.*?)(?=\n##\s|\Z)", body, re.DOTALL)
    if not section_match:
        return issues

    section = section_match.group(1)
    section_offset = section_match.start(1)

    # 提取年份：绝对年份 + 年号年份
    abs_year_pattern = re.compile(r"(公元前\d+|前\d+|\d{1,4})年")
    era_year_pattern = re.compile(r"([\u4e00-\u9fff]{2,4}?)([一二三四五六七八九十百两\d]+)年")

    years: List[dict] = []
    seen_positions: set = set()

    # 先提取绝对年份
    for m in abs_year_pattern.finditer(section):
        year_val = _parse_year(m.group(1))
        if year_val is None:
            continue
        years.append({
            "value": year_val,
            "era": None,
            "pos": m.start(),
            "line": _line_of(body, section_offset + m.start()),
            "snippet": m.group(0),
        })
        seen_positions.add((m.start(), m.end()))

    # 再提取年号年份（跳过已被绝对年份匹配的位置）
    # 非年号前缀黑名单：避免 "不过五十一年" "大约三年" 等持续时间被误判为年号年份
    # "一个" 入黑名单：避免 "一个六百年的秦国/一个十五年的秦朝" 中量词前缀被误判为年号
    non_era_prefixes = {
        "不过", "大约", "共计", "前后", "持续", "历经", "经过",
        "不到", "近", "约", "只", "仅仅", "整整", "至少",
        "如今", "当时", "此前", "其中", "不过来", "之后",
        "一个",
    }
    # 时间范围结构识别："X年到Y年" / "X至Y年" 中的 X 是范围起点，不作独立时间点
    # 例：太建九年到十年这场徐州之战 → "太建九年" 跳过，避免与"太建十年"误报逆序
    range_followed_pattern = re.compile(r"(到|至)([一二三四五六七八九十百两\d]+)年")
    for m in era_year_pattern.finditer(section):
        if (m.start(), m.end()) in seen_positions:
            continue
        era = m.group(1)
        year_raw = m.group(2)
        year_val = _cn_to_int(year_raw) if not year_raw.isdigit() else int(year_raw)
        if year_val < 0:
            continue
        if not era or era == "前":
            continue
        if era in non_era_prefixes:
            continue
        # 时间范围起点豁免：若该年份紧跟 "到/至 + 年份"，视为范围表述，跳过
        if range_followed_pattern.match(section, m.end()):
            continue
        years.append({
            "value": year_val,
            "era": era,
            "pos": m.start(),
            "line": _line_of(body, section_offset + m.start()),
            "snippet": m.group(0),
        })

    if len(years) < 2:
        return issues

    # 按 pos 排序（文中出现顺序）
    years.sort(key=lambda y: y["pos"])

    # 检查年份是否单调递增
    # - 绝对年份（era=None）：按 value 比较
    # - 同年号年份（era 相同）：按 value 比较
    # - 不同年号：跳过比较（无法确定先后）
    for i in range(1, len(years)):
        prev = years[i - 1]
        curr = years[i]
        if prev["era"] != curr["era"]:
            continue
        if curr["value"] < prev["value"]:
            window_start = max(0, prev["pos"] - 100)
            window_end = min(len(section), curr["pos"] + 50)
            window = section[window_start:window_end]
            if _FLASHBACK_MARKERS.search(window):
                continue
            snippet = f"年份逆序：{prev['snippet']}（行{prev['line']}）→ {curr['snippet']}（行{curr['line']}），且无倒叙标注"
            issues.append(ConsistencyIssue(
                type="timeline_inversion",
                severity="P2",
                message=f"时间线倒置：{snippet}",
                snippet=snippet,
                locations=[prev["line"], curr["line"]],
            ))

    return issues


# --- 主入口 ------------------------------------------------------------------

def check_consistency(content: str, archetype: str = "narrative") -> ConsistencyReport:
    """运行完整一致性检测，返回报告。

    按 archetype 路由：
    - narrative：四类全检（古籍有时间线/年份/字号等结构化声明）
    - modern/knowledge/fiction：跳过时间线倒置（现代文/小说无年份序列），其余仍检
      fiction 桶是"七实三虚"小说（如洛克菲勒商战），无古籍年份序列/字号结构，
      按 modern 分支处理（与 content_quality.py 路由一致）。
    """
    # archetype 合法性校验（与 content_quality.py 统一，fail-fast 优于静默误路由）
    if archetype not in ("narrative", "modern", "knowledge", "fiction"):
        raise ValueError(
            f"archetype 必须是 narrative/modern/knowledge/fiction 之一，收到：{archetype!r}"
        )
    issues: List[ConsistencyIssue] = []

    issues.extend(check_numeric_cross_reference(content))
    issues.extend(check_same_event_diff_value(content))
    issues.extend(check_entity_alias_conflict(content))
    if archetype == "narrative":
        issues.extend(check_timeline_inversion(content))

    details: Dict[str, List[ConsistencyIssue]] = {
        "numeric_cross": [],
        "same_event_diff_value": [],
        "entity_alias": [],
        "timeline_inversion": [],
    }
    for issue in issues:
        if issue.type in details:
            details[issue.type].append(issue)

    return ConsistencyReport(issues=issues, details=details)


def format_consistency_report(report: ConsistencyReport) -> str:
    """将一致性报告格式化为 Markdown。"""
    type_labels = {
        "numeric_cross": "数值交叉矛盾",
        "same_event_diff_value": "同事件异值",
        "entity_alias": "实体别名冲突",
        "timeline_inversion": "时间线倒置",
    }
    lines = [
        "## 一致性检测报告",
        "",
        f"- **得分**：{report.score}/10",
        f"- **评级**：{'通过' if report.passed else '未通过'}",
        f"- **问题总数**：{len(report.issues)}",
        "",
    ]
    for issue_type, label in type_labels.items():
        type_issues = report.details.get(issue_type, [])
        lines.append(f"### {label}（{len(type_issues)} 项）")
        if type_issues:
            for issue in type_issues:
                lines.append(f"- [{issue.severity}] {issue.message}")
                if issue.locations:
                    lines.append(f"  - 位置：行 {issue.locations}")
        else:
            lines.append("- ✅ 无问题")
        lines.append("")
    return "\n".join(lines)
