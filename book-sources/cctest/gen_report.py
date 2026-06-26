#!/usr/bin/env python3
"""Generate final comprehensive HTML report from scan results + semantic observations"""
import json
from pathlib import Path

with open('/tmp/scan_results.json', encoding='utf-8') as f:
    results = json.load(f)

# Manual semantic review findings per column (from direct reading)
SEMANTIC_NOTES = {
    "理财课": {
        "structural_pattern": "全专栏（57篇）frontmatter 缺少 created_at、source_agents 两个字段，属于批量性元数据缺失，疑似整批文章未经最终 frontmatter 补全流程。同时全专栏缺少 # 级大标题（均用 ## 开篇），以及缺少「参考来源」章节。内容质量本身较高，案例真实生动。",
        "sample_quality": "已读样本《ETF与场内基金》内容详实，金融逻辑准确，叙事案例有代入感，但「穷人思维/富人思维」框架在多篇反复出现，有模板化风险。"
    },
    "史记": {
        "structural_pattern": "「秦人立国与图霸」「秦扫六合与暴政」「商鞅变法」等章节组（共11篇）批量缺少 created_at 和 source_agents，说明这批文章是更早期生成的，未经最新 frontmatter 规范处理。",
        "sample_quality": "引用密度问题突出：《彭城之战》每千字5.6处行内引用，远超3处上限；《秦纪_火烧咸阳》5.3处。另有重复文件：「鸿门宴」「火烧咸阳」各有两个版本（新旧命名并存）。历史文章中出现「降维打击」现代术语（《彭城之战》）。"
    },
    "唐纪": {
        "structural_pattern": "「开元盛世」「武周代唐」章节组（共9篇）缺少 # 级标题，正文直接以 ## 开篇，标题层级倒置。重复文件：「纳谏与用人」有两版本（贞观之治_vs_唐纪七_命名）。",
        "sample_quality": "「底层逻辑」（《武周代唐_女主称帝》《武周代唐_神龙政变》）、「闭环」（《贞观之治_君臣共治》）出现在历史叙事中，属不当现代术语。「不是X而是Y」句式在《女主称帝》出现5次。"
    },
    "明纪": {
        "structural_pattern": "最严重问题：7个事件存在重复文件（「明纪三十X」旧命名与新章节命名并存），涉及张居正改革、万历怠政、东林党争、国本之争、萨尔浒之战、三大征共14个冗余文件，应清理旧命名文件。",
        "sample_quality": "引用密度普遍偏高（多篇超过4-5处/千字），《成化朝的隐患》5.3处为最高，《土木堡之变》4.3处、《夺门之变》4.6处。"
    },
    "孔子传": {
        "structural_pattern": "全专栏（26篇）批量缺少 source_agents 字段。有15篇缺少「参考来源」章节，说明孔子传是较早批次生成，流程未完善。1处内联跳转「详见下章」（《周游列国_见南子》）。",
        "sample_quality": "内容整体质量较好，史实引用翔实。《周游列国_见南子》出现「（详见下章）」跳转提示需清理。"
    },
    "宋纪": {
        "structural_pattern": "全专栏（33篇）存在大范围标题层级问题——正文缺少 # 级大标题，全部使用 ## 开篇，可能是整批生成时未按规范设置顶级标题。另有6处「不是X而是Y」过密（《海上之盟》8次为最高）。",
        "sample_quality": "历史叙事本身较为流畅，「底层逻辑」出现在《南宋衰亡_采石之战》。《南宋衰亡_端平入洛》缺少参考来源章节。"
    },
    "AI大模型学习": {
        "structural_pattern": "全专栏（37篇）缺少「参考来源」章节，部分篇目有标题层级混乱（多个#标题）。「不是X而是Y」句式在多篇超限，是该专栏最普遍的文风问题。",
        "sample_quality": "2处内联跳转「见第X章」（《提示词工程_任务与模型选型》《提示词工程_核心提示词技巧》），需清理。整体内容技术准确，案例生动，但参考来源普遍缺失。"
    },
    "论语": {
        "structural_pattern": "部分文章（9篇）缺少 created_at、source_agents 字段，为早期生成批次。引用密度极高：《孔子其人_孔子的一生》6.7处/千字，《教育之道_有教无类》4.2处/千字。",
        "sample_quality": "已读《孔子其人》：内容扎实，史料引用准确，但行内引用格式（——《论语·XXX》）密集，几乎每段都挂出处，阅读流感较差。需大幅疏减至文末统一来源。"
    },
    "睡眠与精力修复课": {
        "structural_pattern": "整体质量较好，仅有少量问题。「不是X而是Y」句式在4篇中超限，《日间快速修复_散步恢复法》有「值得注意的是」AI套路句式。",
        "sample_quality": "内容科学性有保障，叙事节奏较好。"
    },
    "职场沟通课": {
        "structural_pattern": "仅9条P2问题，均为「不是X而是Y」句式统计。整体质量较好。",
        "sample_quality": "结构规范，内容实用。"
    },
    "三国": {
        "structural_pattern": "仅1条P2问题（《黄巾之乱与董卓专权_天下大乱》「不是X而是Y」4次）。整体质量优秀。",
        "sample_quality": "历史叙事流畅，结构规范。"
    },
    "易经课": {
        "structural_pattern": "无机械扫描问题，整体质量最优。81篇全部通过。",
        "sample_quality": "规范性最好的专栏，frontmatter完整，结构一致。"
    },
    "资治通鉴": {
        "structural_pattern": "无机械扫描问题，整体质量优秀。50篇全部通过。",
        "sample_quality": "frontmatter完整，结构规范，引用克制。"
    },
    "锻炼养生课": {
        "structural_pattern": "无机械扫描问题。38篇全部通过。",
        "sample_quality": "生活健康类内容，规范性好。"
    },
    "饮食养生课": {
        "structural_pattern": "无机械扫描问题。42篇全部通过。",
        "sample_quality": "规范性好，内容实用。"
    },
    "饮食养生课第二版": {
        "structural_pattern": "无机械扫描问题。30篇全部通过。",
        "sample_quality": "第二版规范性好，对第一版有所改进。"
    },
}

def severity_badge(sev, inline=False):
    colors = {"P0": "#dc2626", "P1": "#ea580c", "P2": "#ca8a04"}
    color = colors.get(sev, "#6b7280")
    return f'<span class="badge" style="background:{color}">{sev}</span>'

def build_report(results):
    total_files = sum(r["summary"]["total_files"] for r in results.values())
    total_issues = sum(r["summary"]["total_issues"] for r in results.values())
    total_dups = sum(r["summary"]["duplicates"] for r in results.values())
    total_p1 = sum(r["summary"]["p1"] for r in results.values())
    total_p2 = sum(r["summary"]["p2"] for r in results.values())

    sections = ""
    for col_name, data in sorted(results.items()):
        s = data["summary"]
        sem = SEMANTIC_NOTES.get(col_name, {})

        if s["p0"] > 0 or s["duplicates"] > 0:
            status_cls, status_text = "status-red", "🔴 严重问题"
        elif s["p1"] > 0:
            status_cls, status_text = "status-orange", "🟠 有问题"
        elif s["p2"] > 0:
            status_cls, status_text = "status-yellow", "🟡 轻微问题"
        else:
            status_cls, status_text = "status-green", "✅ 通过"

        # Duplicates
        dup_html = ""
        if data["duplicates"]:
            dup_rows = "".join(
                f"<tr><td>🔴 <strong>{ev}</strong></td><td>{', '.join(fnames)}</td></tr>"
                for ev, fnames in data["duplicates"].items()
            )
            dup_html = f"""
            <div class="section-block dup-block">
              <div class="block-title">🔴 重复文件（需立即清理）</div>
              <table class="small-table"><thead><tr><th>重复事件</th><th>文件列表</th></tr></thead>
              <tbody>{dup_rows}</tbody></table>
            </div>"""

        # Issue table
        issue_html = ""
        if data["files"]:
            # Group by type
            by_type = {}
            for fname, issues in data["files"].items():
                for iss in issues:
                    t = iss["type"]
                    if t not in by_type:
                        by_type[t] = []
                    by_type[t].append((fname, iss["severity"], iss["detail"]))

            rows = ""
            for fname, issues in sorted(data["files"].items()):
                for iss in issues:
                    rows += f"""<tr>
                      <td class="fname">{fname}</td>
                      <td>{severity_badge(iss['severity'])}</td>
                      <td class="issue-type">{iss['type']}</td>
                      <td class="issue-detail">{iss['detail']}</td>
                    </tr>"""

            # Summary by type
            type_summary = " ".join(
                f'<span class="tag-issue">{t} ×{len(v)}</span>'
                for t, v in sorted(by_type.items(), key=lambda x: -len(x[1]))
            )
            issue_html = f"""
            <div class="section-block">
              <div class="block-title">🔍 机械扫描问题明细（共 {sum(len(v) for v in data['files'].values())} 条）</div>
              <div class="type-tags">{type_summary}</div>
              <table class="issues-table">
                <thead><tr><th>文件</th><th>级别</th><th>类型</th><th>详情</th></tr></thead>
                <tbody>{rows}</tbody>
              </table>
            </div>"""

        # Semantic notes
        sem_html = ""
        if sem:
            sem_html = f"""
            <div class="section-block sem-block">
              <div class="block-title">🧠 语义分析观察</div>
              <p><strong>结构性规律：</strong>{sem.get('structural_pattern','')}</p>
              <p style="margin-top:8px"><strong>内容质量：</strong>{sem.get('sample_quality','')}</p>
            </div>"""

        sections += f"""
        <div class="col-section" id="col-{col_name}">
          <div class="col-header" onclick="toggle(this)">
            <div class="col-left">
              <span class="col-name">📚 {col_name}</span>
              <span class="{status_cls} status-tag">{status_text}</span>
            </div>
            <div class="col-right">
              <span class="stat">{s['total_files']} 篇</span>
              {"<span class='stat stat-dup'>重复 "+str(s['duplicates'])+"</span>" if s['duplicates'] else ""}
              {"<span class='stat stat-p1'>P1: "+str(s['p1'])+"</span>" if s['p1'] else ""}
              {"<span class='stat stat-p2'>P2: "+str(s['p2'])+"</span>" if s['p2'] else ""}
              <span class="chevron">▼</span>
            </div>
          </div>
          <div class="col-body">
            {dup_html}
            {sem_html}
            {issue_html if issue_html else '<div class="ok-box">✅ 无机械扫描问题</div>'}
          </div>
        </div>"""

    # Overview summary table
    overview_rows = ""
    for col_name, data in sorted(results.items()):
        s = data["summary"]
        if s["p0"] > 0 or s["duplicates"] > 0: icon = "🔴"
        elif s["p1"] > 0: icon = "🟠"
        elif s["p2"] > 0: icon = "🟡"
        else: icon = "🟢"
        overview_rows += f"""<tr onclick="goTo('{col_name}')" style="cursor:pointer">
          <td>{icon} <a href="#col-{col_name}" style="color:inherit;text-decoration:none">{col_name}</a></td>
          <td class="num">{s['total_files']}</td>
          <td class="num {'red' if s['duplicates'] else ''}">{s['duplicates']}</td>
          <td class="num {'orange' if s['p1'] else ''}">{s['p1']}</td>
          <td class="num {'yellow' if s['p2'] else ''}">{s['p2']}</td>
          <td class="num">{s['total_issues']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HaloRead 专栏质量全面审查报告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Helvetica Neue",sans-serif;background:#f0f4f8;color:#1a202c;line-height:1.6;font-size:14px}}
a{{color:#4f46e5}}
.header{{background:linear-gradient(135deg,#1e293b,#3730a3);color:#fff;padding:36px 32px 28px}}
.header h1{{font-size:1.9em;font-weight:800;letter-spacing:-.02em}}
.header .sub{{opacity:.7;margin-top:8px;font-size:.95em}}
.header .badge-row{{margin-top:16px;display:flex;gap:12px;flex-wrap:wrap}}
.hbadge{{background:rgba(255,255,255,.15);border-radius:20px;padding:4px 14px;font-size:.82em;font-weight:600}}
.container{{max-width:1200px;margin:0 auto;padding:24px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px}}
.kpi{{background:#fff;border-radius:12px;padding:18px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.kpi .num{{font-size:2.2em;font-weight:800;line-height:1.1}}
.kpi .lbl{{color:#64748b;font-size:.78em;margin-top:4px;font-weight:500}}
.kpi.red .num{{color:#dc2626}}
.kpi.orange .num{{color:#ea580c}}
.kpi.yellow .num{{color:#ca8a04}}
.kpi.green .num{{color:#16a34a}}
.section-card{{background:#fff;border-radius:12px;padding:22px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.section-card h2{{font-size:1.05em;font-weight:700;color:#334155;margin-bottom:14px}}
.overview-table{{width:100%;border-collapse:collapse;font-size:.85em}}
.overview-table th{{background:#f8fafc;padding:9px 12px;text-align:left;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0;white-space:nowrap}}
.overview-table td{{padding:8px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}}
.overview-table tr:last-child td{{border-bottom:none}}
.overview-table tr:hover td{{background:#f8fafc}}
.overview-table td.num{{text-align:center;font-weight:600}}
.overview-table td.red{{color:#dc2626}}
.overview-table td.orange{{color:#ea580c}}
.overview-table td.yellow{{color:#ca8a04}}
.agents-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}}
.agent-box{{background:#f8fafc;border-left:3px solid #6366f1;border-radius:6px;padding:10px 14px}}
.agent-name{{font-weight:700;font-size:.88em;color:#3730a3}}
.agent-cols{{color:#64748b;font-size:.78em;margin-top:3px}}
.col-section{{background:#fff;border-radius:12px;margin-bottom:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.col-header{{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;cursor:pointer;user-select:none;transition:background .12s}}
.col-header:hover{{background:#f8fafc}}
.col-left{{display:flex;align-items:center;gap:10px}}
.col-right{{display:flex;align-items:center;gap:10px;font-size:.82em;color:#64748b}}
.col-name{{font-weight:700;font-size:1em}}
.status-tag{{padding:2px 10px;border-radius:20px;font-size:.75em;font-weight:700}}
.status-red{{background:#fef2f2;color:#dc2626}}
.status-orange{{background:#fff7ed;color:#ea580c}}
.status-yellow{{background:#fefce8;color:#ca8a04}}
.status-green{{background:#f0fdf4;color:#16a34a}}
.stat{{padding:1px 8px;border-radius:4px;background:#f1f5f9}}
.stat-dup{{background:#fef2f2;color:#dc2626;font-weight:700}}
.stat-p1{{background:#fff7ed;color:#ea580c;font-weight:600}}
.stat-p2{{background:#fefce8;color:#ca8a04;font-weight:600}}
.chevron{{font-size:.75em;transition:transform .2s;color:#94a3b8}}
.col-header.open .chevron{{transform:rotate(180deg)}}
.col-body{{padding:0 20px 20px;display:none;border-top:1px solid #f1f5f9}}
.col-body.open{{display:block}}
.section-block{{margin-top:16px}}
.block-title{{font-weight:700;font-size:.9em;color:#334155;margin-bottom:10px;display:flex;align-items:center;gap:6px}}
.dup-block .block-title{{color:#dc2626}}
.sem-block{{background:#f0f9ff;border-radius:8px;padding:14px;border-left:3px solid #0ea5e9}}
.sem-block .block-title{{color:#0369a1}}
.sem-block p{{font-size:.85em;color:#475569;line-height:1.7}}
.small-table{{width:100%;border-collapse:collapse;font-size:.83em}}
.small-table th{{background:#fef2f2;padding:7px 10px;text-align:left;font-weight:600;color:#991b1b;border-bottom:1px solid #fecaca}}
.small-table td{{padding:7px 10px;border-bottom:1px solid #fff5f5;vertical-align:top}}
.issues-table{{width:100%;border-collapse:collapse;font-size:.82em;margin-top:10px}}
.issues-table th{{background:#f8fafc;padding:7px 10px;text-align:left;font-weight:600;color:#475569;border-bottom:1px solid #e2e8f0;white-space:nowrap}}
.issues-table td{{padding:6px 10px;border-bottom:1px solid #f8fafc;vertical-align:top}}
.issues-table tr:last-child td{{border-bottom:none}}
.fname{{font-family:"SF Mono",Monaco,monospace;font-size:.78em;color:#6366f1;word-break:break-all;max-width:240px}}
.issue-type{{font-weight:600;color:#374151;white-space:nowrap}}
.issue-detail{{color:#6b7280}}
.badge{{display:inline-block;color:#fff;font-size:.73em;padding:2px 7px;border-radius:3px;font-weight:700;white-space:nowrap}}
.type-tags{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}}
.tag-issue{{background:#f1f5f9;color:#475569;padding:2px 10px;border-radius:20px;font-size:.78em;font-weight:600}}
.ok-box{{background:#f0fdf4;color:#15803d;border-radius:8px;padding:12px 16px;font-weight:600;font-size:.88em;margin-top:12px}}
footer{{text-align:center;color:#94a3b8;font-size:.78em;padding:28px}}
@media(max-width:768px){{.kpi-grid{{grid-template-columns:repeat(2,1fr)}}.agents-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="header">
  <h1>🔍 HaloRead 专栏质量全面审查报告</h1>
  <div class="sub">5 组专家 Agent 并行分析 · 机械扫描 + 语义阅读双重覆盖</div>
  <div class="badge-row">
    <span class="hbadge">📅 生成时间：2026-06-26</span>
    <span class="hbadge">📚 16 个专栏</span>
    <span class="hbadge">📄 686 篇文章</span>
    <span class="hbadge">🤖 5 组 Agent 并行</span>
  </div>
</div>

<div class="container">

  <!-- KPI -->
  <div class="kpi-grid">
    <div class="kpi"><div class="num">{len(results)}</div><div class="lbl">专栏数</div></div>
    <div class="kpi"><div class="num">{total_files}</div><div class="lbl">文章总数</div></div>
    <div class="kpi red"><div class="num">{total_dups}</div><div class="lbl">重复事件数<br><small>（需清理）</small></div></div>
    <div class="kpi orange"><div class="num">{total_p1}</div><div class="lbl">P1 问题条数</div></div>
    <div class="kpi yellow"><div class="num">{total_p2}</div><div class="lbl">P2 问题条数</div></div>
  </div>

  <!-- Overview -->
  <div class="section-card">
    <h2>📊 专栏总览（点击行跳转详情）</h2>
    <table class="overview-table">
      <thead><tr><th>专栏名称</th><th>文章数</th><th>重复文件</th><th>P1问题</th><th>P2问题</th><th>总计</th></tr></thead>
      <tbody>{overview_rows}</tbody>
    </table>
  </div>

  <!-- Agent Groups -->
  <div class="section-card">
    <h2>🧑‍💼 5 组专家 Agent 分工</h2>
    <div class="agents-grid">
      <div class="agent-box"><div class="agent-name">📜 历史专家组A</div><div class="agent-cols">三国 · 史记 · 唐纪</div></div>
      <div class="agent-box"><div class="agent-name">📜 历史专家组B</div><div class="agent-cols">宋纪 · 明纪 · 资治通鉴</div></div>
      <div class="agent-box"><div class="agent-name">🧘 哲学文化组</div><div class="agent-cols">论语 · 孔子传 · 易经课</div></div>
      <div class="agent-box"><div class="agent-name">💼 职场技能组</div><div class="agent-cols">AI大模型学习 · 职场沟通课</div></div>
      <div class="agent-box"><div class="agent-name">🌿 生活养生组</div><div class="agent-cols">理财课 · 睡眠 · 锻炼 · 饮食（×2）</div></div>
    </div>
  </div>

  <!-- Summary of findings -->
  <div class="section-card">
    <h2>📋 核心问题归纳（按优先级）</h2>
    <table class="overview-table">
      <thead><tr><th>优先级</th><th>问题类型</th><th>受影响专栏</th><th>建议行动</th></tr></thead>
      <tbody>
        <tr><td>🔴 P0</td><td>重复文件（新旧命名并存）</td><td>明纪(7)、史记(2)、唐纪(1)</td><td>删除旧命名文件（明纪三十X_ 系列）</td></tr>
        <tr><td>🟠 P1</td><td>frontmatter 缺字段（created_at/source_agents）</td><td>理财课(57篇)、孔子传(26篇)、史记(11篇)、论语(9篇)</td><td>批量脚本补全 frontmatter</td></tr>
        <tr><td>🟠 P1</td><td>内联跳转提示（见下章/见上文）</td><td>AI大模型学习(2处)、孔子传(1处)</td><td>全局搜索替换清理</td></tr>
        <tr><td>🟠 P1</td><td>AI套路句式（我们可以看到/值得注意的是）</td><td>AI大模型学习、睡眠课各1处</td><td>逐篇修改</td></tr>
        <tr><td>🟡 P2</td><td>缺少「参考来源」章节</td><td>AI大模型学习(37篇全)、理财课(57篇全)、孔子传(15篇)</td><td>批量补全或确认豁免规则</td></tr>
        <tr><td>🟡 P2</td><td>标题层级问题（正文缺#标题或有多个#标题）</td><td>宋纪(33篇全缺)、唐纪(9篇)、理财课(57篇全缺)</td><td>批量检查正文首行标题</td></tr>
        <tr><td>🟡 P2</td><td>引用密度过高（>3处/千字）</td><td>史记(19篇)、明纪(13篇)、论语(4篇)、唐纪(1篇)</td><td>参照规范迁至文末</td></tr>
        <tr><td>🟡 P2</td><td>「不是X而是Y」句式过多（>3次/篇）</td><td>宋纪(7篇)、唐纪(4篇)、睡眠课(3篇)等共30余处</td><td>逐篇改写多样化表达</td></tr>
        <tr><td>🟡 P2</td><td>历史文中出现现代术语</td><td>史记「降维打击」、唐纪「底层逻辑/闭环」、宋纪「底层逻辑」</td><td>替换为朴素历史语言</td></tr>
      </tbody>
    </table>
  </div>

  <!-- Per-column sections -->
  {sections}

</div>
<footer>HaloRead 内容质量审查报告 · 机械扫描覆盖全部 {total_files} 篇 · 语义分析基于各专栏抽样阅读</footer>

<script>
function toggle(header){{
  header.classList.toggle('open');
  header.nextElementSibling.classList.toggle('open');
}}
function goTo(name){{
  const el=document.getElementById('col-'+name);
  if(el){{
    el.scrollIntoView({{behavior:'smooth',block:'start'}});
    const h=el.querySelector('.col-header');
    if(!h.classList.contains('open'))toggle(h);
  }}
}}
// Auto-open problem sections
document.querySelectorAll('.status-red,.status-orange').forEach(tag=>{{
  const sec=tag.closest('.col-section');
  if(sec){{
    const h=sec.querySelector('.col-header');
    h.classList.add('open');
    sec.querySelector('.col-body').classList.add('open');
  }}
}});
</script>
</body>
</html>"""
    return html

html = build_report(results)
out = Path("/mnt/user-data/outputs/haloread_issues_report.html")
out.write_text(html, encoding="utf-8")
print(f"Report written: {out}, size: {len(html)//1024}KB")
