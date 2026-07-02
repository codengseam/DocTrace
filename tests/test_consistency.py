"""一致性检测回归测试（v1.2 新增维度）。

覆盖四类矛盾检测的正反例：
1. 数值交叉矛盾（numeric_cross）：年龄-年份/在位时长/损失-剩余
2. 同事件异值（same_event_diff_value）：同引文异字数/同战役异兵力/同典故异出处
3. 实体别名冲突（entity_alias）：字号/谥号/籍贯冲突
4. 时间线倒置（timeline_inversion）：年份逆序且无倒叙标注

误报防护：
- 别名表（曹操↔孟德↔曹孟德 等合法指代不算矛盾）
- 倒叙标注词（"此前""回过头看"等不报）
- "继位时N岁" 与 "N岁继位" 两种语序都支持，且不吞数字
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from src.utils.consistency import (
    ConsistencyIssue,
    ConsistencyReport,
    check_consistency,
    check_numeric_cross_reference,
    check_same_event_diff_value,
    check_entity_alias_conflict,
    check_timeline_inversion,
    format_consistency_report,
)


# ---------------------------------------------------------------------------
# 1. 数值交叉矛盾
# ---------------------------------------------------------------------------

class TestNumericCrossReference:
    """数值交叉矛盾：年龄-年份/在位时长/损失-剩余的数学矛盾。"""

    def test_age_year_contradiction(self):
        """年龄与生年/继位年矛盾应报 P0。"""
        text = """# 曹操
曹操生于前155年，前140年继位时25岁，明显与生年矛盾。
"""
        issues = check_numeric_cross_reference(text)
        # 应至少检测到 1 个 P0 矛盾
        p0_issues = [i for i in issues if i.severity == "P0" and i.type == "numeric_cross"]
        assert len(p0_issues) >= 1, f"应检测到年龄-年份矛盾，实际: {issues}"
        assert "15" in p0_issues[0].message  # 应 15 岁
        assert "25" in p0_issues[0].message  # 文中称 25 岁

    def test_age_year_consistent(self):
        """年龄与生年/继位年一致，不报。

        关键回归：'继位时N岁' 不应吞数字（之前非贪婪 \\S{0,3}? 把 15 吞成 5）。
        """
        text = """# 曹操
曹操生于前155年，前140年继位时15岁，于220年去世。
"""
        issues = check_numeric_cross_reference(text)
        age_issues = [
            i for i in issues
            if i.type == "numeric_cross" and "年龄" in i.message
        ]
        assert len(age_issues) == 0, f"年龄一致不应报错，实际: {age_issues}"

    def test_age_year_consistent_arabic_year(self):
        """公元年龄一致，不报。"""
        text = """# 李世民
李世民生于598年，626年即位时28岁。
"""
        issues = check_numeric_cross_reference(text)
        age_issues = [
            i for i in issues
            if i.type == "numeric_cross" and "年龄" in i.message
        ]
        assert len(age_issues) == 0, f"年龄一致不应报错，实际: {age_issues}"

    def test_reign_duration_contradiction(self):
        """在位年数与继位/去世年矛盾应报 P0。"""
        text = """# 汉武帝
汉武帝于前141年继位，前87年去世，在位30年。
"""
        issues = check_numeric_cross_reference(text)
        dur_issues = [
            i for i in issues
            if i.type == "numeric_cross" and "在位" in i.message
        ]
        assert len(dur_issues) >= 1, f"应检测到在位年数矛盾，实际: {issues}"
        # 实际在位 54 年，文中称 30 年
        assert "54" in dur_issues[0].message
        assert "30" in dur_issues[0].message

    def test_reign_duration_consistent(self):
        """在位年数与继位/去世年一致，不报。"""
        text = """# 汉武帝
汉武帝于前141年继位，前87年去世，在位54年。
"""
        issues = check_numeric_cross_reference(text)
        dur_issues = [
            i for i in issues
            if i.type == "numeric_cross" and "在位" in i.message
        ]
        assert len(dur_issues) == 0, f"在位年数一致不应报错，实际: {dur_issues}"

    def test_loss_remaining_contradiction(self):
        """损失-剩余数学矛盾应报 P0。"""
        text = """# 战役
三万大军出征，损失一万，只剩一万。
"""
        issues = check_numeric_cross_reference(text)
        loss_issues = [
            i for i in issues
            if i.type == "numeric_cross" and "损失" in i.message
        ]
        assert len(loss_issues) >= 1, f"应检测到损失-剩余矛盾，实际: {issues}"

    def test_no_year_claim_no_false_positive(self):
        """没有生年/继位年声明，不应误报年龄矛盾。"""
        text = """# 简介
曹操是一位雄才大略的政治家。
他统一了北方。
"""
        issues = check_numeric_cross_reference(text)
        age_issues = [
            i for i in issues
            if i.type == "numeric_cross" and "年龄" in i.message
        ]
        assert len(age_issues) == 0, f"无年份声明不应误报，实际: {age_issues}"


# ---------------------------------------------------------------------------
# 2. 同事件异值
# ---------------------------------------------------------------------------

class TestSameEventDiffValue:
    """同事件异值：同引文异字数/同战役异兵力/同典故异出处。"""

    def test_same_quote_diff_char_count(self):
        """同引文两次出现，字数标注不一致应报 P0。"""
        text = """# 论语
前文写道：「君君臣臣」这四个字。
后文又写：「君君臣臣」这五个字。
"""
        issues = check_same_event_diff_value(text)
        char_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "字数" in i.message
        ]
        assert len(char_issues) >= 1, f"应检测到同引文异字数，实际: {issues}"
        assert "君君臣臣" in char_issues[0].message

    def test_same_quote_same_char_count(self):
        """同引文两次出现，字数标注一致，不报。"""
        text = """# 论语
前文写道：「君君臣臣」这四个字。
后文又写：「君君臣臣」这四个字。
"""
        issues = check_same_event_diff_value(text)
        char_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "字数" in i.message
        ]
        assert len(char_issues) == 0, f"字数一致不应报错，实际: {char_issues}"

    def test_same_battle_diff_troops(self):
        """同战役两次出现，兵力不同应报 P1。"""
        text = """# 赤壁之战
前文记载：赤壁之战，曹操率二十万大军南下。
后文又写：赤壁之战，曹操率八十万大军南下。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "兵力" in i.message
        ]
        assert len(battle_issues) >= 1, f"应检测到同战役异兵力，实际: {issues}"
        assert "赤壁之战" in battle_issues[0].message

    def test_same_idiom_diff_source(self):
        """同典故两次出现，出处不一致应报 P1。"""
        text = """# 典故
前文写道：「唇亡齿寒」出自《左传》。
后文又写：「唇亡齿寒」语出《谷梁传》。
"""
        issues = check_same_event_diff_value(text)
        idiom_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "典故" in i.message
        ]
        assert len(idiom_issues) >= 1, f"应检测到同典故异出处，实际: {issues}"

    def test_different_idiom_same_source_no_false_positive(self):
        """不同典故各自有出处，不算同典故异出处。"""
        text = """# 典故
「唇亡齿寒」出自《左传》。
「退避三舍」出自《左传》。
"""
        issues = check_same_event_diff_value(text)
        idiom_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "典故" in i.message
        ]
        assert len(idiom_issues) == 0, f"不同典故不算矛盾，实际: {idiom_issues}"


# ---------------------------------------------------------------------------
# 3. 实体别名冲突
# ---------------------------------------------------------------------------

class TestEntityAliasConflict:
    """实体别名冲突：字号/谥号/籍贯冲突。"""

    def test_zi_conflict(self):
        """字号冲突应报 P0。"""
        text = """# 曹操
前文写道：曹操字孟德。
后文又说：曹操字子建。
"""
        issues = check_entity_alias_conflict(text)
        zi_issues = [
            i for i in issues
            if i.type == "entity_alias" and "字" in i.message
        ]
        assert len(zi_issues) >= 1, f"应检测到字号冲突，实际: {issues}"

    def test_zi_consistent(self):
        """字号一致不报。"""
        text = """# 曹操
前文写道：曹操字孟德。
后文又写：曹操字孟德。
"""
        issues = check_entity_alias_conflict(text)
        zi_issues = [
            i for i in issues
            if i.type == "entity_alias" and "字" in i.message
        ]
        assert len(zi_issues) == 0, f"字号一致不应报错，实际: {zi_issues}"

    def test_native_place_conflict(self):
        """籍贯冲突应报 P1。"""
        text = """# 曹操
前文写道：曹操，沛国谯县人。
后文又说：曹操，沛国相县人。
"""
        issues = check_entity_alias_conflict(text)
        place_issues = [
            i for i in issues
            if i.type == "entity_alias" and "籍贯" in i.message
        ]
        assert len(place_issues) >= 1, f"应检测到籍贯冲突，实际: {issues}"

    def test_legitimate_alias_no_false_positive(self):
        """合法别名（曹操/孟德/曹孟德）不算矛盾。"""
        text = """# 曹操
曹操字孟德，沛国谯县人。
曹孟德雄才大略，统一北方。
孟德生于前155年。
"""
        issues = check_entity_alias_conflict(text)
        # 不应有任何 entity_alias 问题
        alias_issues = [i for i in issues if i.type == "entity_alias"]
        assert len(alias_issues) == 0, f"合法别名不应报错，实际: {alias_issues}"


# ---------------------------------------------------------------------------
# 4. 时间线倒置
# ---------------------------------------------------------------------------

class TestTimelineInversion:
    """时间线倒置：年份逆序且无倒叙标注。"""

    def test_year_inversion(self):
        """年份逆序且无倒叙标注应报 P2。"""
        text = """# 三国大事记

## 讲事情

建安十三年，赤壁之战爆发。
建安十二年，隆中对提出。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [
            i for i in issues
            if i.type == "timeline_inversion"
        ]
        assert len(inv_issues) >= 1, f"应检测到时间线倒置，实际: {issues}"

    def test_year_increasing_no_false_positive(self):
        """年份递增不报。"""
        text = """# 三国大事记

## 讲事情

建安十二年，隆中对提出。
建安十三年，赤壁之战爆发。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [
            i for i in issues
            if i.type == "timeline_inversion"
        ]
        assert len(inv_issues) == 0, f"年份递增不应报错，实际: {inv_issues}"

    def test_flashback_marker_exemption(self):
        """含倒叙标注词不报。"""
        text = """# 三国大事记

## 讲事情

建安十三年，赤壁之战爆发。
回顾此前，建安十二年，隆中对提出。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [
            i for i in issues
            if i.type == "timeline_inversion"
        ]
        assert len(inv_issues) == 0, f"倒叙标注应豁免，实际: {inv_issues}"

    def test_absolute_year_inversion(self):
        """公元年份逆序也应报。"""
        text = """# 大事记

## 讲事情

220年，曹操去世。
200年，官渡之战爆发。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [
            i for i in issues
            if i.type == "timeline_inversion"
        ]
        assert len(inv_issues) >= 1, f"公元年份逆序应报，实际: {issues}"


# ---------------------------------------------------------------------------
# 4.1 v1.2.1 误报豁免回归（基于全量扫描真实案例）
# ---------------------------------------------------------------------------

class TestV121FalsePositiveRegressions:
    """v1.2.1 新增误报豁免：基于全量扫描 output/ 发现的真实误报案例。

    覆盖：
    - 倒叙 marker 扩展：早在/早就/要讲清/得先讲清/已经X年了/话说回
    - 量词前缀"一个"：避免"一个六百年/一个十五年"被误判为年号
    - 时间范围结构"X年到Y年"：范围起点不作独立时间点
    - 攻防同句：A破B / A的N万被B的N万冲散，跨阵营不可比
    - 虚数前缀"数/几"：数十万人/几百万人 不参与精确比较
    - 同句窗口限定：避免跨句误抓邻战兵力
    """

    def test_flashback_zaizao_marker(self):
        """「早在X年」倒叙标记应豁免。"""
        text = """# 大事记

## 讲事情

元始四年，王莽征天下学者。
早在元始元年，王莽封安汉公。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [i for i in issues if i.type == "timeline_inversion"]
        assert len(inv_issues) == 0, f"早在应豁免，实际: {inv_issues}"

    def test_flashback_zaojiu_marker(self):
        """「早就」倒叙标记应豁免（区别于早在/早先）。"""
        text = """# 大事记

## 讲事情

大业十年，第三次征辽。
乱的种子，早就埋下了。大业七年，王薄起义。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [i for i in issues if i.type == "timeline_inversion"]
        assert len(inv_issues) == 0, f"早就应豁免，实际: {inv_issues}"

    def test_flashback_deixianjiang_marker(self):
        """「要讲清/得先讲清」叙事提示语应豁免。"""
        text = """# 大事记

## 讲事情

武德九年，玄武门之变爆发。
要讲清这一天的血，得先讲清武德年间的事。武德七年，杨文干事件。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [i for i in issues if i.type == "timeline_inversion"]
        assert len(inv_issues) == 0, f"要讲清/得先讲清应豁免，实际: {inv_issues}"

    def test_flashback_yijing_marker(self):
        """「已经X年了」回顾起点应豁免。"""
        text = """# 大事记

## 讲事情

前195年，刘邦过世。
刘邦已经十几年了——自前209年起兵，到前195年，整整十四年。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [i for i in issues if i.type == "timeline_inversion"]
        assert len(inv_issues) == 0, f"已经X年了应豁免，实际: {inv_issues}"

    def test_flashback_huashuohui_marker(self):
        """「话说回」分线索倒叙应豁免。"""
        text = """# 大事记

## 讲事情

964年，石重贵病死。
话说回耶律德光入汴后，947年三月仓皇北撤。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [i for i in issues if i.type == "timeline_inversion"]
        assert len(inv_issues) == 0, f"话说回应豁免，实际: {inv_issues}"

    def test_quantifier_prefix_yige_not_era(self):
        """「一个六百年/一个十五年」量词前缀不应被误判为年号。"""
        text = """# 秦亡

## 讲事情

一个六百年的秦国，一个十五年的秦朝，就这么亡了。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [i for i in issues if i.type == "timeline_inversion"]
        assert len(inv_issues) == 0, f"量词前缀'一个'不应报，实际: {inv_issues}"

    def test_time_range_xdao_y_skip_start(self):
        """「X年到Y年」时间范围起点不作独立时间点。"""
        text = """# 徐州之战

## 讲事情

太建十年，王轨发动反攻。
太建九年到十年这场徐州之战，把陈朝本钱输光。
"""
        issues = check_timeline_inversion(text)
        inv_issues = [i for i in issues if i.type == "timeline_inversion"]
        assert len(inv_issues) == 0, f"时间范围起点应豁免，实际: {inv_issues}"

    def test_attack_defense_active_voice_exemption(self):
        """主动语态攻防同句「A率N1万破B的N2万」不应报同战役异兵力。"""
        text = """# 彭城之战

## 讲事情

彭城之战，项羽率三万骑兵破刘邦五十六万大军。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "战役" in i.message
        ]
        assert len(battle_issues) == 0, f"主动攻防同句应豁免，实际: {battle_issues}"

    def test_attack_defense_passive_voice_exemption(self):
        """被动语态攻防同句「N2万被N1万打垮」不应报。"""
        text = """# 彭城之战

## 讲事情

彭城之战五十六万大军被项羽三万骑兵打垮。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "战役" in i.message
        ]
        assert len(battle_issues) == 0, f"被动攻防同句应豁免，实际: {battle_issues}"

    def test_attack_defense_chongsan_verb_exemption(self):
        """攻防动词「冲散」覆盖合肥之战误报。"""
        text = """# 合肥之战

## 讲事情

合肥之战，十万大军被张辽八百人冲散，成了笑柄。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "战役" in i.message
        ]
        assert len(battle_issues) == 0, f"冲散攻防应豁免，实际: {battle_issues}"

    def test_vague_number_shu_exemption(self):
        """虚数「数十万人」不参与精确兵力比较。"""
        text = """# 长平之战

## 讲事情

白起临死说：长平之战，赵卒降者数十万人，我诈而尽坑之。
后来史书又记：长平之战坑杀四十万。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "战役" in i.message
        ]
        # 虚数"数十万"被跳过，只剩"四十万"一处，不构成"异值"
        assert len(battle_issues) == 0, f"虚数应豁免，实际: {battle_issues}"

    def test_vague_number_ji_exemption(self):
        """虚数「几百万」不参与精确兵力比较。"""
        text = """# 长平之战

## 讲事情

长平之战坑杀四十万。战国死了几百万人，死在白起手里的过半。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "战役" in i.message
        ]
        assert len(battle_issues) == 0, f"虚数'几百万'应豁免，实际: {battle_issues}"

    def test_sentence_boundary_window_exemption(self):
        """同句窗口限定：跨句的兵力不误抓。"""
        text = """# 长平之战

## 讲事情

长平之战坑杀四十万。战国死了几百万人，这是白起的罪。
"""
        issues = check_same_event_diff_value(text)
        # "战国死了几百万人" 在新句中，应被句末标点截断，不与"长平之战"关联
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "战役" in i.message
        ]
        assert len(battle_issues) == 0, f"跨句应不抓，实际: {battle_issues}"

    def test_real_troop_contradiction_still_detected(self):
        """真实同战役异兵力（无攻防动词、无虚数）仍应报。"""
        text = """# 长平之战

## 讲事情

据《史记》记载，长平之战坑杀四十万人。
可《战国策》却说，长平之战坑杀三十万人。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "战役" in i.message
        ]
        assert len(battle_issues) >= 1, f"真实异兵力应报，实际: {battle_issues}"


# ---------------------------------------------------------------------------
# 5. 综合入口 + archetype 路由
# ---------------------------------------------------------------------------

class TestCheckConsistencyEntryPoint:
    """check_consistency 主入口 + archetype 路由。"""

    def test_consistency_report_passed_property(self):
        """ConsistencyReport.passed：得分 ≥ 7/10 才通过。"""
        # 无问题 → passed=True, score=10
        clean_text = "# 标题\n这是一段没有矛盾的文本。\n"
        report = check_consistency(clean_text, archetype="narrative")
        assert report.passed is True
        assert report.score == 10

    def test_consistency_report_score_property(self):
        """ConsistencyReport.score：P0 扣 5（封顶 10），P1 扣 3（封顶 6），P2 扣 2（封顶 4）。"""
        # 制造 1 个 P0 矛盾
        text = """# 测试
曹操生于前155年，前140年继位时25岁。
"""
        report = check_consistency(text, archetype="narrative")
        # 应有 1 个 P0，score = 10 - 5 = 5，passed=False（5 < 7）
        assert report.score == 5, f"P0 应扣 5 分，实际 score={report.score}"
        assert report.passed is False, f"score=5 < 7，应不通过"

    def test_archetype_routing_narrative(self):
        """narrative archetype 应跑全部 4 类检测。"""
        text = """# 测试
曹操生于前155年，前140年继位时25岁。
「君君臣臣」这四个字，「君君臣臣」这五个字。
"""
        report = check_consistency(text, archetype="narrative")
        assert len(report.issues) >= 2, f"应检测到 2+ 类矛盾，实际: {report.issues}"

    def test_archetype_routing_modern(self):
        """modern archetype 跳过时间线倒置，但 3 个 detector 仍运行。"""
        # 含时间线倒置 + 同引文异字数（numeric_cross 无年龄年份声明不会报）
        text = """# 职场沟通

## 讲事情

2024年，小王升职。
2020年，小王入职。
「闭环」这四个字，「闭环」这五个字。
"""
        report = check_consistency(text, archetype="modern")
        assert isinstance(report, ConsistencyReport)
        # modern 跳过 timeline_inversion → details["timeline_inversion"] 应为空
        assert len(report.details["timeline_inversion"]) == 0, (
            f"modern 应跳过时间线倒置，实际: {report.details['timeline_inversion']}"
        )
        # 但 same_event_diff_value 仍应检测到（同引文异字数）
        assert len(report.details["same_event_diff_value"]) >= 1, (
            f"modern 仍应跑 same_event_diff_value，实际: {report.details['same_event_diff_value']}"
        )
        # numeric_cross / entity_alias 的 detector 仍运行（即使无问题，details 键存在）
        assert "numeric_cross" in report.details
        assert "entity_alias" in report.details

    def test_archetype_routing_knowledge(self):
        """knowledge archetype 跳过时间线倒置，但 3 个 detector 仍运行。"""
        text = """# MySQL 索引

## 讲事情

2024年，InnoDB 发布新版本。
2020年，MySQL 8.0 发布。
「B+树」这四个字，「B+树」这五个字。
"""
        report = check_consistency(text, archetype="knowledge")
        assert isinstance(report, ConsistencyReport)
        # knowledge 跳过 timeline_inversion
        assert len(report.details["timeline_inversion"]) == 0, (
            f"knowledge 应跳过时间线倒置，实际: {report.details['timeline_inversion']}"
        )
        # same_event_diff_value 仍应检测到
        assert len(report.details["same_event_diff_value"]) >= 1, (
            f"knowledge 仍应跑 same_event_diff_value，实际: {report.details['same_event_diff_value']}"
        )
        # 3 个 detector 的 details 键均存在
        assert "numeric_cross" in report.details
        assert "entity_alias" in report.details

    def test_archetype_routing_narrative_runs_timeline(self):
        """narrative archetype 应运行全部 4 个 detector（含 timeline_inversion）。"""
        text = """# 大事记

## 讲事情

220年，曹操去世。
200年，官渡之战爆发。
"""
        report = check_consistency(text, archetype="narrative")
        # narrative 应检测到 timeline_inversion
        assert len(report.details["timeline_inversion"]) >= 1, (
            f"narrative 应跑时间线倒置检测，实际: {report.details['timeline_inversion']}"
        )

    def test_archetype_routing_modern_runs_numeric_cross(self):
        """modern 桶应运行 numeric_cross detector（注入损失-剩余矛盾证明 detector 真正运行）。

        区别于仅断言 details 键存在（键在 check_consistency 入口处静态初始化，与
        detector 是否运行无关），这里注入真实矛盾并断言检出，证明 detector 确实执行。
        """
        text = """# 职场复盘

## 讲事情

三万大军出征，损失一万，只剩一万。
"""
        report = check_consistency(text, archetype="modern")
        # numeric_cross detector 应检出损失-剩余矛盾（3万 - 1万 ≠ 1万）
        assert len(report.details["numeric_cross"]) >= 1, (
            f"modern 应运行 numeric_cross 并检出损失-剩余矛盾，实际: {report.details['numeric_cross']}"
        )


# ---------------------------------------------------------------------------
# 6. 集成层：content_quality.py 联动
# ---------------------------------------------------------------------------

class TestContentQualityIntegration:
    """content_quality.py 应将 consistency 维度纳入 6 维度评分。"""

    def test_consistency_dimension_in_details(self):
        """run_content_quality_checks 的 details 应包含 consistency 键。"""
        from src.utils.content_quality import run_content_quality_checks
        text = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

曹操生于前155年，前140年继位时25岁。
"""
        report = run_content_quality_checks(text, archetype="narrative")
        assert "consistency" in report.details, "details 应包含 consistency 键"
        # 应至少有 1 个一致性问题
        assert len(report.details["consistency"]) >= 1, f"应检测到一致性问题，实际: {report.details['consistency']}"

    def test_consistency_dimension_clean(self):
        """无矛盾内容，consistency 维度应为空列表。"""
        from src.utils.content_quality import run_content_quality_checks
        text = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

这是一段没有矛盾的简短文本。
"""
        report = run_content_quality_checks(text, archetype="narrative")
        assert "consistency" in report.details
        assert len(report.details["consistency"]) == 0, f"无矛盾不应有问题，实际: {report.details['consistency']}"

    def test_consistency_score_impact(self):
        """有 P0 一致性问题时，总分应扣分（10 - score）。"""
        from src.utils.content_quality import run_content_quality_checks
        text_dirty = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

曹操生于前155年，前140年继位时25岁。
"""
        text_clean = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

这是一段没有矛盾的简短文本。
"""
        dirty = run_content_quality_checks(text_dirty, archetype="narrative")
        clean = run_content_quality_checks(text_clean, archetype="narrative")
        # 有矛盾的总分应低于无矛盾的
        assert dirty.score < clean.score, (
            f"有矛盾应扣分: dirty={dirty.score}, clean={clean.score}"
        )


# ---------------------------------------------------------------------------
# 6.1 集成层门控边界测试（P1-2：passed = score >= 85 and consistency.passed）
# ---------------------------------------------------------------------------

class TestIntegrationGateBoundary:
    """集成层双门控：passed = score >= 85 AND consistency_report.passed。

    门控逻辑（content_quality.py:704）：
        passed = score >= 85 and consistency_report.passed

    任意一门不满足即 passed=False。本类锁定 AND 语义，防止后续重构改为 OR 或去掉一致性门控。
    """

    def test_gate_both_pass_clean_content(self):
        """干净内容：score >= 85 且 consistency 通过 → passed=True。"""
        from src.utils.content_quality import run_content_quality_checks
        # 构造完整 narrative 内容：含年份、名家点评、参考来源，避免 truth/citation 扣分
        text = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

## 讲事情

建安十三年，赤壁之战爆发。

司马光在《资治通鉴》中评价此事。司马迁亦有所记载。钱穆与陈寅恪亦有论述。

## 参考来源
- 司马光《资治通鉴》
- 司马迁《史记》
"""
        report = run_content_quality_checks(text, archetype="narrative")
        assert report.score >= 85, f"干净内容应 score>=85，实际: {report.score}, issues: {report.issues}"
        assert len(report.details["consistency"]) == 0, "干净内容应无一致性问题"
        assert report.passed is True, f"双门控均通过应 passed=True，实际: {report.passed}"

    def test_gate_consistency_veto(self):
        """一致性 P0 否决：即使 score >= 85，consistency 不通过 → passed=False。"""
        from src.utils.content_quality import run_content_quality_checks
        # 干净内容 + 一个 P0 一致性矛盾（年龄-年份）
        text = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

曹操生于前155年，前140年继位时25岁。
"""
        report = run_content_quality_checks(text, archetype="narrative")
        # 应有 P0 一致性问题
        assert len(report.details["consistency"]) >= 1, "应有 P0 一致性问题"
        # 一致性维度未通过（P0 扣 5 分 → score=5 < 7）
        # 关键断言：即使总分可能 >= 85，一致性门控也否决
        assert report.passed is False, (
            f"一致性 P0 应否决 passed（即使 score={report.score}），实际 passed={report.passed}"
        )

    def test_gate_score_below_85_veto(self):
        """总分 < 85 否决：即使 consistency 通过，score < 85 → passed=False。"""
        from src.utils.content_quality import run_content_quality_checks
        # 用 9 个不同的 AI_PATTERNS_EXPLICIT 套路句式：check_ai_tone 对每个 pattern
        # 用 re.search 返回 1 个 issue，共 9 个可读性问题 → 扣 18 分（上限 20）→
        # readability 维度已足以驱动 score < 85（100-18=82<85，不依赖 truth/citation）。
        cliches = "\n".join([
            "我们可以看到，这是第一点。",
            "这告诉我们一个道理。",
            "总而言之，事情就是这样。",
            "综上所述，结论成立。",
            "值得注意的是，细节决定成败。",
            "不难发现，规律在此。",
            "从这个角度来看，一切清晰。",
            "让我们回顾一下历史。",
            "从某种意义上说，这就是答案。",
        ])
        text = f"""---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

{cliches}
"""
        report = run_content_quality_checks(text, archetype="narrative")
        # 9 个不同 AI 套路句式应产生 >= 9 个可读性问题（readability 维度单独驱动）
        assert len(report.details["readability"]) >= 9, (
            f"9 个 AI 套路句式应产生 >=9 个可读性问题，实际: {len(report.details['readability'])}"
        )
        # readability 维度驱动 score < 85
        assert report.score < 85, f"9 个可读性问题应拉低 score<85，实际: {report.score}"
        # 一致性应通过（无矛盾）
        assert len(report.details["consistency"]) == 0, "无矛盾内容一致性应通过"
        # 关键断言：score < 85 否决，即使 consistency 通过
        assert report.passed is False, (
            f"score={report.score} < 85 应否决 passed（即使 consistency 通过），实际 passed={report.passed}"
        )

    def test_gate_and_logic_verified(self):
        """直接验证 AND 语义：passed == (score >= 85) and (consistency 无 P0)。"""
        from src.utils.content_quality import run_content_quality_checks
        # 用两份内容验证 AND 真值表
        clean = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

简短文本。
"""
        dirty = """---
title: 测试
book: 测试
chapter: 测试
event: 测试
sort: 1
chapter_sort: 1
---

# 测试

曹操生于前155年，前140年继位时25岁。
"""
        clean_report = run_content_quality_checks(clean, archetype="narrative")
        dirty_report = run_content_quality_checks(dirty, archetype="narrative")
        # AND 语义：passed 当且仅当 score>=85 且 consistency 无 P0/P1 阻断
        clean_expected = clean_report.score >= 85 and len([
            i for i in clean_report.details["consistency"]
        ]) == 0
        assert clean_report.passed == clean_expected, (
            f"clean: passed={clean_report.passed}, expected={clean_expected}, "
            f"score={clean_report.score}"
        )
        # dirty 有 P0 consistency → 一致性门控不通过 → passed=False（无论 score）
        assert dirty_report.passed is False, (
            f"dirty 有 P0 一致性应 passed=False，实际 passed={dirty_report.passed}, "
            f"score={dirty_report.score}"
        )


# ---------------------------------------------------------------------------
# 7. ConsistencyReport 按类扣分封顶 + passed 门槛（P2-14）
# ---------------------------------------------------------------------------

class TestConsistencyReportScoring:
    """ConsistencyReport.score/passed 的按类封顶与门槛逻辑。"""

    def _make_report(self, severities: list[str]) -> ConsistencyReport:
        """构造指定 severity 列表的 ConsistencyReport。"""
        issues = [
            ConsistencyIssue(type="test", severity=s, message=f"test-{i}", snippet="")
            for i, s in enumerate(severities)
        ]
        return ConsistencyReport(issues=issues)

    def test_empty_report(self):
        """空报告：score=10, passed=True。"""
        r = self._make_report([])
        assert r.score == 10
        assert r.passed is True

    def test_one_p0(self):
        """1 个 P0：score=5, passed=False（5 < 7）。"""
        r = self._make_report(["P0"])
        assert r.score == 5
        assert r.passed is False

    def test_two_p0_capped(self):
        """2 个 P0：扣分封顶 10，score=0, passed=False。"""
        r = self._make_report(["P0", "P0"])
        assert r.score == 0
        assert r.passed is False

    def test_three_p0_capped_at_10(self):
        """3 个 P0：扣分仍封顶 10（非 15），score=0。"""
        r = self._make_report(["P0", "P0", "P0"])
        assert r.score == 0

    def test_one_p1(self):
        """1 个 P1：score=7, passed=True（7 >= 7）。"""
        r = self._make_report(["P1"])
        assert r.score == 7
        assert r.passed is True

    def test_two_p1_capped(self):
        """2 个 P1：扣分封顶 6，score=4, passed=False。"""
        r = self._make_report(["P1", "P1"])
        assert r.score == 4
        assert r.passed is False

    def test_three_p1_capped_at_6(self):
        """3 个 P1：扣分仍封顶 6（非 9），score=4。"""
        r = self._make_report(["P1", "P1", "P1"])
        assert r.score == 4

    def test_one_p2(self):
        """1 个 P2：score=8, passed=True。"""
        r = self._make_report(["P2"])
        assert r.score == 8
        assert r.passed is True

    def test_two_p2_capped(self):
        """2 个 P2：扣分封顶 4，score=6, passed=False（6 < 7）。"""
        r = self._make_report(["P2", "P2"])
        assert r.score == 6
        assert r.passed is False

    def test_three_p2_capped_at_4(self):
        """3 个 P2：扣分仍封顶 4（非 6），score=6。"""
        r = self._make_report(["P2", "P2", "P2"])
        assert r.score == 6

    def test_mixed_p1_p2(self):
        """1 P1 + 1 P2：score=10-3-2=5, passed=False。"""
        r = self._make_report(["P1", "P2"])
        assert r.score == 5
        assert r.passed is False


# ---------------------------------------------------------------------------
# 8. archetype 校验与路由反向断言（P2-13）
# ---------------------------------------------------------------------------

class TestArchetypeValidation:
    """archetype 合法性校验 + 路由行为。"""

    def test_invalid_archetype_raises(self):
        """非法 archetype 应 raise ValueError（fail-fast）。

        v1.2.2 起 fiction 合法（按 modern 分支处理），改用真正非法值。
        """
        with pytest.raises(ValueError, match="archetype"):
            check_consistency("# 测试\n无矛盾文本。", archetype="poetry")

    def test_invalid_archetype_empty_raises(self):
        """空字符串 archetype 应 raise。"""
        with pytest.raises(ValueError, match="archetype"):
            check_consistency("# 测试\n无矛盾文本。", archetype="")

    def test_fiction_archetype_accepted(self):
        """v1.2.2: fiction archetype 应被接受（按 modern 分支处理，不 raise）。

        回归 BUG-044：修复前 fiction 在 consistency.py/content_quality.py 抛 ValueError，
        导致洛克菲勒专栏（archetype: fiction）无法跑质检。
        """
        report = check_consistency("# 洛克菲勒\n1865 年拍卖 72500 美元。", archetype="fiction")
        assert report is not None
        assert report.score >= 7  # 无矛盾，应通过

    def test_fiction_skips_timeline_inversion(self):
        """v1.2.2: fiction archetype 应跳过时间线倒置（与 modern 一致）。"""
        text = """# 小说

## 讲事情

1865 年，洛克菲勒买下炼油厂。
1863 年，洛克菲勒合伙创业。
"""
        report = check_consistency(text, archetype="fiction")
        timeline_issues = [i for i in report.issues if i.type == "timeline_inversion"]
        assert len(timeline_issues) == 0, f"fiction 应跳过时间线，实际报: {timeline_issues}"

    def test_fiction_still_detects_numeric_cross(self):
        """v1.2.2: fiction archetype 仍应检测数值交叉矛盾（与 modern 一致）。"""
        text = """# 小说
三万大军出征，损失一万，只剩一万。
"""
        report = check_consistency(text, archetype="fiction")
        numeric_issues = [i for i in report.issues if i.type == "numeric_cross"]
        assert len(numeric_issues) >= 1, f"fiction 应检测数值矛盾，实际: {numeric_issues}"

    def test_modern_skips_timeline_inversion(self):
        """modern archetype 应跳过时间线倒置检测。"""
        # 这段文本在 narrative 下会报时间线倒置（年份逆序无倒叙标注）
        text = """# 测试
建安十三年，赤壁之战爆发。
建安十二年，隆中对提出。
"""
        report_modern = check_consistency(text, archetype="modern")
        timeline_issues = [i for i in report_modern.issues if i.type == "timeline_inversion"]
        assert len(timeline_issues) == 0, f"modern 应跳过时间线，实际报: {timeline_issues}"

    def test_knowledge_skips_timeline_inversion(self):
        """knowledge archetype 应跳过时间线倒置检测。"""
        text = """# 测试
2025年，项目启动。
2023年，需求调研。
"""
        report_knowledge = check_consistency(text, archetype="knowledge")
        timeline_issues = [i for i in report_knowledge.issues if i.type == "timeline_inversion"]
        assert len(timeline_issues) == 0, f"knowledge 应跳过时间线，实际报: {timeline_issues}"

    def test_narrative_detects_timeline_inversion(self):
        """narrative archetype 应检测时间线倒置。"""
        text = """# 测试

## 讲事情

建安十三年，赤壁之战爆发。
建安十二年，隆中对提出。
"""
        report_narrative = check_consistency(text, archetype="narrative")
        timeline_issues = [i for i in report_narrative.issues if i.type == "timeline_inversion"]
        assert len(timeline_issues) >= 1, f"narrative 应检测时间线倒置，实际: {timeline_issues}"


# ---------------------------------------------------------------------------
# 9. 虚数后缀豁免（P2-10）
# ---------------------------------------------------------------------------

class TestVagueNumberSuffixExemption:
    """虚数后缀（余/来/多）应豁免同战役异兵力比较。"""

    def test_yu_suffix_exemption(self):
        """'三十余万' 与 '三十万' 不算矛盾（'余'是虚指）。"""
        text = """# 战役
前文记载：赤壁之战，曹操率三十余万大军南下。
后文又写：赤壁之战，曹操率三十万大军南下。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "兵力" in i.message
        ]
        assert len(battle_issues) == 0, f"'余'后缀应豁免，实际报: {battle_issues}"

    def test_lai_suffix_exemption(self):
        """'二十来万' 与 '二十万' 不算矛盾（'来'是虚指）。"""
        text = """# 战役
前文记载：合肥之战，孙权率二十来万大军北上。
后文又写：合肥之战，孙权率二十万大军北上。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "兵力" in i.message
        ]
        assert len(battle_issues) == 0, f"'来'后缀应豁免，实际报: {battle_issues}"

    def test_duo_suffix_exemption(self):
        """'三十多万' 与 '三十万' 不算矛盾（'多'是虚指）。"""
        text = """# 战役
前文记载：官渡之战，袁绍率三十多万大军南下。
后文又写：官渡之战，袁绍率三十万大军南下。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "兵力" in i.message
        ]
        assert len(battle_issues) == 0, f"'多'后缀应豁免，实际报: {battle_issues}"

    def test_precise_number_still_detected(self):
        """精确数字（无虚数后缀）的矛盾仍应被检测。"""
        text = """# 战役
前文记载：赤壁之战，曹操率二十万大军南下。
后文又写：赤壁之战，曹操率八十万大军南下。
"""
        issues = check_same_event_diff_value(text)
        battle_issues = [
            i for i in issues
            if i.type == "same_event_diff_value" and "兵力" in i.message
        ]
        assert len(battle_issues) >= 1, f"精确数字矛盾应被检测，实际: {battle_issues}"


# ---------------------------------------------------------------------------
# 10. 边界用例（P2-11）
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """边界用例：空输入/无讲事情段落/单字段 frontmatter。"""

    def test_empty_content(self):
        """空内容不应崩溃，应返回空报告。"""
        report = check_consistency("", archetype="narrative")
        assert isinstance(report, ConsistencyReport)
        assert len(report.issues) == 0
        assert report.score == 10

    def test_whitespace_only(self):
        """纯空白内容不应崩溃。"""
        report = check_consistency("   \n\n   \n", archetype="narrative")
        assert isinstance(report, ConsistencyReport)
        assert len(report.issues) == 0

    def test_no_jiangshiqing_section(self):
        """无'讲事情'段落时，时间线检测不应崩溃。"""
        text = """# 测试

## 讲人物

曹操字孟德。

## 讲道理

以史为鉴。
"""
        report = check_consistency(text, archetype="narrative")
        assert isinstance(report, ConsistencyReport)

    def test_frontmatter_only_no_closing(self):
        """frontmatter 未闭合（无结束---）不应崩溃。"""
        text = "---\ntitle: 测试\n这条 frontmatter 没有闭合"
        report = check_consistency(text, archetype="narrative")
        assert isinstance(report, ConsistencyReport)

    def test_single_line_content(self):
        """单行内容不应崩溃。"""
        report = check_consistency("曹操生于前155年。", archetype="narrative")
        assert isinstance(report, ConsistencyReport)


# ---------------------------------------------------------------------------
# 11. format_consistency_report 格式化测试（P2-1）
# ---------------------------------------------------------------------------

class TestFormatConsistencyReport:
    """format_consistency_report：将 ConsistencyReport 格式化为 Markdown。"""

    def test_empty_report_format(self):
        """空报告应包含得分 10/10 和"通过"评级。"""
        report = ConsistencyReport(issues=[])
        text = format_consistency_report(report)
        assert "10/10" in text
        assert "通过" in text
        assert "问题总数" in text

    def test_report_with_p0_issue(self):
        """含 P0 问题的报告应包含"未通过"和问题消息。"""
        issue = ConsistencyIssue(
            type="numeric_cross",
            severity="P0",
            message="年龄与生年矛盾：应 15 岁，文中称 25 岁",
            snippet="测试",
            locations=[3],
        )
        report = ConsistencyReport(
            issues=[issue],
            details={"numeric_cross": [issue]},
        )
        text = format_consistency_report(report)
        assert "未通过" in text
        assert "年龄与生年矛盾" in text
        assert "数值交叉矛盾" in text
        # locations 渲染分支：locations=[3] 应输出"位置：行 [3]"
        assert "位置：行 [3]" in text, f"应渲染 locations，实际: {text}"

    def test_report_with_multiple_types(self):
        """含多类问题的报告应包含所有类型标签。"""
        issues = [
            ConsistencyIssue(type="numeric_cross", severity="P0", message="矛盾1", snippet=""),
            ConsistencyIssue(type="same_event_diff_value", severity="P1", message="矛盾2", snippet=""),
            ConsistencyIssue(type="entity_alias", severity="P1", message="矛盾3", snippet=""),
            ConsistencyIssue(type="timeline_inversion", severity="P2", message="矛盾4", snippet=""),
        ]
        report = ConsistencyReport(
            issues=issues,
            details={
                "numeric_cross": [issues[0]],
                "same_event_diff_value": [issues[1]],
                "entity_alias": [issues[2]],
                "timeline_inversion": [issues[3]],
            },
        )
        text = format_consistency_report(report)
        assert "数值交叉矛盾" in text
        assert "同事件异值" in text
        assert "实体别名冲突" in text
        assert "时间线倒置" in text

    def test_report_score_reflected(self):
        """报告得分应反映在格式化输出中。"""
        # 2 个 P0 → score=0
        issues = [
            ConsistencyIssue(type="test", severity="P0", message="t1", snippet=""),
            ConsistencyIssue(type="test", severity="P0", message="t2", snippet=""),
        ]
        report = ConsistencyReport(issues=issues)
        text = format_consistency_report(report)
        assert "0/10" in text
        assert "未通过" in text
