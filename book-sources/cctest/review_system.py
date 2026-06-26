"""
HaloRead 多 Agent 并行内容审查系统
5 组专家 Agent 并行审查 16 个专栏 686 篇文章
"""

import os
import re
import json
import asyncio
import time
from pathlib import Path
from collections import defaultdict
import anthropic

OUTPUT_DIR = Path("/home/claude/HaloRead/output")
REPORT_PATH = Path("/home/claude/haloread_issues_report.html")

client = anthropic.Anthropic()

# ═══════════════════════════════════════════════════════════════
# 1. 本地机械扫描（不需要 API）
# ═══════════════════════════════════════════════════════════════

AI_PHRASES = [
    "综上所述", "我们可以看到", "这告诉我们", "不难发现",
    "值得注意的是", "由此可见", "这充分说明", "在这里我们",
    "正如前文所述", "综上可知", "通过以上分析",
    "这一点非常重要", "需要指出的是",
]

MODERN_TERMS_IN_HISTORY = [
    "底层逻辑", "坐标系", "博弈论", "生态位",
    "操作系统", "底层操作", "赛道", "闭环",
    "降维打击", "护城河",
]

TYPOS = {
    "做为": "作为", "按耐": "按捺", "交待": "交代",
    "既使": "即使", "那怕": "哪怕", "必竞": "毕竟",
    "凑和": "凑合", "甘败下风": "甘拜下风",
    "一愁莫展": "一筹莫展", "美仑美奂": "美轮美奂",
    "不径而走": "不胫而走", "黄梁美梦": "黄粱美梦",
    "竭泽而鱼": "竭泽而渔", "棉薄之力": "绵薄之力",
    "墨守陈规": "墨守成规", "磬竹难书": "罄竹难书",
    "趋之若骛": "趋之若鹜", "声名雀起": "声名鹊起",
    "谈笑风声": "谈笑风生", "委屈求全": "委曲求全",
    "不能自己": "不能自已", "一如继往": "一如既往",
    "走头无路": "走投无路", "饮鸠止渴": "饮鸩止渴",
    "顶力相助": "鼎力相助", "不加思索": "不假思索",
    "按步就班": "按部就班",
}

INLINE_JUMP_PATTERNS = [
    r"（见讲故事）", r"（见讲事情）", r"（详见下章）",
    r"（见上文）", r"（见前文）", r"（见第.*?章）",
]

HISTORY_COLUMNS = {"三国", "史记", "唐纪", "宋纪", "明纪", "资治通鉴", "孔子传", "论语"}


def load_frontmatter(content):
    """Parse YAML frontmatter"""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    yaml_str = content[3:end].strip()
    meta = {}
    for line in yaml_str.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    body = content[end + 3:].strip()
    return meta, body


def scan_file_local(filepath):
    """Local mechanical scan of a single file"""
    issues = []
    content = filepath.read_text(encoding="utf-8")
    meta, body = load_frontmatter(content)

    # ── Frontmatter completeness ──
    required_fields = ["title", "book", "chapter", "event", "sort", "chapter_sort", "created_at", "source_agents"]
    missing = [f for f in required_fields if f not in meta]
    if missing:
        issues.append({"severity": "P1", "type": "frontmatter缺字段", "detail": f"缺少字段: {', '.join(missing)}"})

    # ── Common typos ──
    for wrong, right in TYPOS.items():
        if wrong in body:
            issues.append({"severity": "P1", "type": "错别字", "detail": f"「{wrong}」应为「{right}」"})

    # ── AI phrases ──
    ai_hits = [p for p in AI_PHRASES if p in body]
    if ai_hits:
        issues.append({"severity": "P1", "type": "AI套路句式", "detail": f"出现: {', '.join(ai_hits)}"})

    # ── Modern terms in history ──
    col = meta.get("book", "")
    if col in HISTORY_COLUMNS:
        term_hits = [t for t in MODERN_TERMS_IN_HISTORY if t in body]
        if term_hits:
            issues.append({"severity": "P2", "type": "历史文中现代术语", "detail": f"出现: {', '.join(term_hits)}"})

    # ── Inline jumps ──
    jump_hits = []
    for pat in INLINE_JUMP_PATTERNS:
        if re.search(pat, body):
            jump_hits.append(pat.strip("（）()"))
    if jump_hits:
        issues.append({"severity": "P1", "type": "内联跳转提示", "detail": f"出现: {', '.join(jump_hits)}"})

    # ── Citation density ──
    citations = re.findall(r"——《[^》]+》", body)
    words = len(body)
    if words > 0 and len(citations) > (words / 1000) * 3 + 1:
        issues.append({"severity": "P2", "type": "引用密度过高", "detail": f"每千字引用 {len(citations)/(words/1000):.1f} 处（上限3处）"})

    # ── Missing reference section ──
    if "## 参考来源" not in body and "## 参考资料" not in body and "参考来源" not in body:
        if len(body) > 500:
            issues.append({"severity": "P2", "type": "缺少参考来源", "detail": "未找到「参考来源」章节"})

    # ── Heading level check ──
    h1_count = len(re.findall(r"^# ", body, re.MULTILINE))
    if h1_count == 0:
        issues.append({"severity": "P2", "type": "标题层级问题", "detail": "正文中缺少 # 级标题"})
    elif h1_count > 1:
        issues.append({"severity": "P2", "type": "标题层级问题", "detail": f"正文中有 {h1_count} 个 # 级标题（应只有1个）"})

    # ── "不是X而是Y" overuse ──
    buishi_count = len(re.findall(r"不是.{1,20}[，,]?.*?而是", body))
    if buishi_count > 3:
        issues.append({"severity": "P2", "type": "「不是X而是Y」过多", "detail": f"出现 {buishi_count} 次（建议≤3次）"})

    return issues


def find_duplicate_files(col_path):
    """Detect duplicate content files in a column"""
    files = list(col_path.glob("*.md"))
    files = [f for f in files if f.name not in ("_meta.yaml", "_目录.md")]
    seen_events = defaultdict(list)
    for f in files:
        try:
            content = f.read_text(encoding="utf-8")
            meta, _ = load_frontmatter(content)
            event = meta.get("event", "")
            if event:
                seen_events[event].append(f.name)
        except Exception:
            pass
    dups = {ev: fnames for ev, fnames in seen_events.items() if len(fnames) > 1}
    return dups


def local_scan_all():
    """Run local scan on all files, return structured results"""
    results = {}
    cols = sorted([d for d in OUTPUT_DIR.iterdir() if d.is_dir()])
    
    for col_dir in cols:
        col_name = col_dir.name
        col_issues = {"files": {}, "duplicates": {}, "summary": {}}
        
        files = sorted(col_dir.glob("*.md"))
        files = [f for f in files if f.name not in ("_meta.yaml", "_目录.md")]
        
        for filepath in files:
            try:
                file_issues = scan_file_local(filepath)
                if file_issues:
                    col_issues["files"][filepath.name] = file_issues
            except Exception as e:
                col_issues["files"][filepath.name] = [{"severity": "P1", "type": "读取失败", "detail": str(e)}]
        
        # Find duplicates
        dups = find_duplicate_files(col_dir)
        if dups:
            col_issues["duplicates"] = dups
        
        # Summary counts
        total_issues = sum(len(v) for v in col_issues["files"].values())
        p0 = sum(1 for issues in col_issues["files"].values() for i in issues if i["severity"] == "P0")
        p1 = sum(1 for issues in col_issues["files"].values() for i in issues if i["severity"] == "P1")
        p2 = sum(1 for issues in col_issues["files"].values() for i in issues if i["severity"] == "P2")
        col_issues["summary"] = {
            "total_files": len(files),
            "files_with_issues": len(col_issues["files"]),
            "total_issues": total_issues,
            "p0": p0, "p1": p1, "p2": p2,
            "duplicates": len(dups),
        }
        
        results[col_name] = col_issues
    
    return results


# ═══════════════════════════════════════════════════════════════
# 2. AI 深度审查（并行 API 调用）
# ═══════════════════════════════════════════════════════════════

# Agent 分组
AGENT_GROUPS = {
    "历史专家组A（三国·史记·唐纪）": ["三国", "史记", "唐纪"],
    "历史专家组B（宋纪·明纪·资治通鉴）": ["宋纪", "明纪", "资治通鉴"],
    "哲学文化组（论语·孔子传·易经课）": ["论语", "孔子传", "易经课"],
    "职场技能组（AI大模型·职场沟通）": ["AI大模型学习", "职场沟通课"],
    "生活养生组（理财·睡眠·锻炼·饮食）": ["理财课", "睡眠与精力修复课", "锻炼养生课", "饮食养生课", "饮食养生课第二版"],
}

REVIEW_PROMPT = """你是严格的内容审查专家，专注于检查 AI 生成的专栏文章质量问题。

请审查以下专栏文章，从4个维度识别问题，每个问题需注明：
- 严重度：P0（事实错误/伪造）/ P1（严重影响质量）/ P2（较小问题）
- 问题类型
- 具体位置或内容

**审查维度**：
1. **真实性**：事实错误、人名/年份/地点有误、编造引用、伪造名人评语
2. **可读性**：叙述重复、AI机器味（千篇一律的总结句）、章节间重复内容、内容雷同
3. **结构逻辑**：时间线混乱、因果倒置、章节内容与标题不符
4. **引用规范**：行内引用过密、缺少参考来源、引文与原典出入较大

专栏类型：{col_type}
{history_note}

{articles}

请按 JSON 格式输出，格式如下（只输出JSON，不加```）：
{{
  "reviews": [
    {{
      "file": "文件名",
      "score": 评分(0-100整数),
      "issues": [
        {{"severity": "P0/P1/P2", "type": "问题类型", "detail": "具体描述"}}
      ],
      "highlights": "本文亮点（1句话）"
    }}
  ]
}}"""


def pick_sample_files(col_dir, n=3):
    """Pick representative sample files from a column"""
    files = sorted(col_dir.glob("*.md"))
    files = [f for f in files if f.name not in ("_meta.yaml", "_目录.md")]
    if not files:
        return []
    if len(files) <= n:
        return files
    # Pick evenly distributed
    step = len(files) // n
    return [files[i * step] for i in range(n)]


def truncate_content(content, max_chars=2000):
    """Truncate content to a reasonable size"""
    meta, body = load_frontmatter(content)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...[内容截断]"
    return body


def review_column_group(group_name, col_names):
    """Review a group of columns using Anthropic API"""
    group_results = {}
    
    for col_name in col_names:
        col_dir = OUTPUT_DIR / col_name
        if not col_dir.exists():
            continue
        
        is_history = col_name in HISTORY_COLUMNS
        history_note = "（历史类专栏：重点检查史实准确性、人物年代、事件因果）" if is_history else "（非历史类专栏：重点检查事实可信度、案例真实性、引用准确性）"
        
        sample_files = pick_sample_files(col_dir, n=3)
        if not sample_files:
            continue
        
        articles_text = ""
        file_names = []
        for f in sample_files:
            content = f.read_text(encoding="utf-8")
            body = truncate_content(content, 1800)
            articles_text += f"\n\n【文件：{f.name}】\n{body}\n"
            file_names.append(f.name)
        
        prompt = REVIEW_PROMPT.format(
            col_type=f"「{col_name}」",
            history_note=history_note,
            articles=articles_text
        )
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            # Clean potential JSON fences
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            group_results[col_name] = {
                "status": "ok",
                "reviews": data.get("reviews", []),
                "sampled_files": file_names
            }
        except json.JSONDecodeError as e:
            group_results[col_name] = {
                "status": "parse_error",
                "error": f"JSON解析失败: {str(e)[:100]}",
                "sampled_files": file_names
            }
        except Exception as e:
            group_results[col_name] = {
                "status": "error",
                "error": str(e)[:200],
                "sampled_files": file_names
            }
        
        # Gentle rate limit
        time.sleep(1.5)
    
    return group_name, group_results


async def run_parallel_ai_review():
    """Run all agent groups in parallel using thread executor"""
    loop = asyncio.get_event_loop()
    tasks = []
    for group_name, col_names in AGENT_GROUPS.items():
        task = loop.run_in_executor(
            None, review_column_group, group_name, col_names
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return {gname: gdata for gname, gdata in results}


# ═══════════════════════════════════════════════════════════════
# 3. HTML 报告生成
# ═══════════════════════════════════════════════════════════════

def severity_badge(sev):
    colors = {"P0": "#dc2626", "P1": "#ea580c", "P2": "#ca8a04"}
    color = colors.get(sev, "#6b7280")
    return f'<span class="badge" style="background:{color}">{sev}</span>'


def build_html_report(local_results, ai_results):
    # Global stats
    total_files = sum(r["summary"]["total_files"] for r in local_results.values())
    total_issues = sum(r["summary"]["total_issues"] for r in local_results.values())
    total_dups = sum(r["summary"]["duplicates"] for r in local_results.values())
    cols_with_issues = sum(1 for r in local_results.values() if r["summary"]["total_issues"] > 0 or r["summary"]["duplicates"] > 0)

    # Build column sections
    sections_html = ""
    for col_name, local_data in sorted(local_results.items()):
        summary = local_data["summary"]
        
        # Find AI review for this column
        ai_col_data = None
        for group_data in ai_results.values():
            if col_name in group_data:
                ai_col_data = group_data[col_name]
                break
        
        # Status indicator
        if summary["p0"] > 0:
            status_cls = "status-red"
            status_text = "⚠️ 严重问题"
        elif summary["p1"] > 0 or summary["duplicates"] > 0:
            status_cls = "status-orange"
            status_text = "⚡ 有问题"
        elif summary["p2"] > 0:
            status_cls = "status-yellow"
            status_text = "💡 轻微问题"
        else:
            status_cls = "status-green"
            status_text = "✅ 通过"
        
        # Local issues table
        local_table = ""
        if local_data["files"]:
            rows = ""
            for fname, issues in sorted(local_data["files"].items()):
                for issue in issues:
                    rows += f"""<tr>
                        <td class="fname">{fname}</td>
                        <td>{severity_badge(issue['severity'])}</td>
                        <td>{issue['type']}</td>
                        <td>{issue['detail']}</td>
                    </tr>"""
            local_table = f"""
            <h4>🔍 机械扫描问题（{sum(len(v) for v in local_data['files'].values())} 条）</h4>
            <table class="issues-table">
                <thead><tr><th>文件</th><th>严重度</th><th>类型</th><th>详情</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>"""
        
        # Duplicates section
        dup_html = ""
        if local_data["duplicates"]:
            dup_rows = ""
            for event, fnames in local_data["duplicates"].items():
                dup_rows += f"<li><strong>{event}</strong>: {', '.join(fnames)}</li>"
            dup_html = f"""
            <div class="dup-box">
                <h4>🔴 重复文件（P0 严重）</h4>
                <ul>{dup_rows}</ul>
            </div>"""
        
        # AI review section
        ai_html = ""
        if ai_col_data and ai_col_data.get("status") == "ok":
            review_cards = ""
            for review in ai_col_data.get("reviews", []):
                score = review.get("score", "?")
                score_cls = "score-green" if score >= 85 else ("score-orange" if score >= 70 else "score-red")
                issues_html = ""
                for issue in review.get("issues", []):
                    issues_html += f"<li>{severity_badge(issue['severity'])} <strong>{issue['type']}</strong>: {issue['detail']}</li>"
                if not issues_html:
                    issues_html = "<li style='color:#6b7280'>无明显问题</li>"
                highlight = review.get("highlights", "")
                review_cards += f"""
                <div class="review-card">
                    <div class="review-header">
                        <span class="review-file">{review.get('file','')}</span>
                        <span class="score {score_cls}">{score}分</span>
                    </div>
                    <ul class="issue-list">{issues_html}</ul>
                    {f'<div class="highlight">✨ {highlight}</div>' if highlight else ''}
                </div>"""
            
            sampled = ai_col_data.get("sampled_files", [])
            ai_html = f"""
            <h4>🤖 AI 深度审查（抽样 {len(sampled)} 篇）</h4>
            {review_cards}"""
        elif ai_col_data and ai_col_data.get("status") == "error":
            ai_html = f"""<div class="error-box">AI 审查出错: {ai_col_data.get('error','')}</div>"""
        
        sections_html += f"""
        <div class="col-section">
            <div class="col-header" onclick="toggleSection(this)">
                <div class="col-title">
                    <span class="col-name">📚 {col_name}</span>
                    <span class="{status_cls} status-tag">{status_text}</span>
                </div>
                <div class="col-stats">
                    <span>{summary['total_files']} 篇</span>
                    <span class="stat-dup">重复 {summary['duplicates']}</span>
                    <span class="stat-p0">P0: {summary['p0']}</span>
                    <span class="stat-p1">P1: {summary['p1']}</span>
                    <span class="stat-p2">P2: {summary['p2']}</span>
                    <span class="chevron">▼</span>
                </div>
            </div>
            <div class="col-body">
                {dup_html}
                {local_table}
                {ai_html}
            </div>
        </div>"""
    
    # Agent group summary
    agent_summary = ""
    for group_name, group_data in ai_results.items():
        cols_reviewed = len([c for c, d in group_data.items() if d.get("status") == "ok"])
        agent_summary += f"""
        <div class="agent-card">
            <div class="agent-name">🧑‍💼 {group_name}</div>
            <div class="agent-stat">审查专栏: {len(group_data)} 个 | 成功: {cols_reviewed}</div>
        </div>"""
    
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HaloRead 专栏质量审查报告</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #f1f5f9; color: #1e293b; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: white; padding: 32px 24px; }}
  .header h1 {{ font-size: 1.8em; font-weight: 700; }}
  .header p {{ opacity: .7; margin-top: 6px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .stat-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); text-align: center; }}
  .stat-card .num {{ font-size: 2em; font-weight: 700; color: #334155; }}
  .stat-card .label {{ color: #64748b; font-size: .85em; margin-top: 4px; }}
  .agents-section {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .agents-section h3 {{ margin-bottom: 16px; color: #334155; }}
  .agents-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .agent-card {{ background: #f8fafc; border-radius: 8px; padding: 12px 16px; border-left: 3px solid #6366f1; }}
  .agent-name {{ font-weight: 600; font-size: .9em; color: #3730a3; }}
  .agent-stat {{ color: #64748b; font-size: .8em; margin-top: 4px; }}
  .col-section {{ background: white; border-radius: 12px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08); overflow: hidden; }}
  .col-header {{ display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; cursor: pointer; user-select: none; transition: background .15s; }}
  .col-header:hover {{ background: #f8fafc; }}
  .col-title {{ display: flex; align-items: center; gap: 12px; }}
  .col-name {{ font-weight: 600; font-size: 1.05em; }}
  .col-stats {{ display: flex; gap: 12px; align-items: center; font-size: .85em; color: #64748b; }}
  .stat-dup {{ color: #dc2626; font-weight: 600; }}
  .stat-p0 {{ color: #dc2626; }}
  .stat-p1 {{ color: #ea580c; }}
  .stat-p2 {{ color: #ca8a04; }}
  .col-body {{ padding: 0 20px 20px; display: none; }}
  .col-body.open {{ display: block; }}
  .chevron {{ font-size: .8em; transition: transform .2s; }}
  .col-header.open .chevron {{ transform: rotate(180deg); }}
  .status-tag {{ font-size: .75em; padding: 3px 10px; border-radius: 20px; font-weight: 600; }}
  .status-red {{ background: #fee2e2; color: #dc2626; }}
  .status-orange {{ background: #fff7ed; color: #ea580c; }}
  .status-yellow {{ background: #fefce8; color: #ca8a04; }}
  .status-green {{ background: #f0fdf4; color: #16a34a; }}
  .issues-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: .85em; }}
  .issues-table th {{ background: #f8fafc; padding: 8px 12px; text-align: left; font-weight: 600; color: #475569; border-bottom: 1px solid #e2e8f0; }}
  .issues-table td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }}
  .issues-table tr:last-child td {{ border-bottom: none; }}
  .fname {{ font-family: monospace; font-size: .8em; color: #6366f1; max-width: 260px; word-break: break-all; }}
  .badge {{ display: inline-block; color: white; font-size: .75em; padding: 2px 8px; border-radius: 4px; font-weight: 700; }}
  h4 {{ color: #334155; margin: 20px 0 10px; font-size: .95em; }}
  .dup-box {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px 16px; margin: 12px 0; }}
  .dup-box h4 {{ color: #dc2626; margin-top: 0; }}
  .dup-box ul {{ padding-left: 20px; font-size: .85em; color: #7f1d1d; }}
  .review-card {{ background: #f8fafc; border-radius: 8px; padding: 14px; margin-bottom: 10px; border-left: 3px solid #e2e8f0; }}
  .review-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
  .review-file {{ font-family: monospace; font-size: .82em; color: #6366f1; }}
  .score {{ font-weight: 700; font-size: 1em; padding: 2px 10px; border-radius: 6px; }}
  .score-green {{ background: #dcfce7; color: #15803d; }}
  .score-orange {{ background: #fff7ed; color: #c2410c; }}
  .score-red {{ background: #fee2e2; color: #b91c1c; }}
  .issue-list {{ padding-left: 20px; font-size: .85em; }}
  .issue-list li {{ margin-bottom: 4px; color: #475569; }}
  .highlight {{ font-size: .82em; color: #6b7280; margin-top: 8px; font-style: italic; }}
  .error-box {{ background: #fff7ed; border: 1px solid #fed7aa; border-radius: 6px; padding: 10px; color: #9a3412; font-size: .85em; }}
  .toc {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .toc h3 {{ margin-bottom: 12px; color: #334155; }}
  .toc-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }}
  .toc-item {{ padding: 6px 12px; border-radius: 6px; font-size: .85em; cursor: pointer; border: 1px solid #e2e8f0; transition: all .15s; }}
  .toc-item:hover {{ background: #f1f5f9; border-color: #cbd5e1; }}
  footer {{ text-align: center; color: #94a3b8; font-size: .8em; padding: 24px; }}
</style>
</head>
<body>
<div class="header">
  <h1>🔍 HaloRead 专栏质量审查报告</h1>
  <p>生成时间：{now} | 5 组专家 Agent 并行审查 | 机械扫描 + AI 语义深度分析</p>
</div>
<div class="container">

  <div class="stats-grid">
    <div class="stat-card"><div class="num">{len(local_results)}</div><div class="label">专栏总数</div></div>
    <div class="stat-card"><div class="num">{total_files}</div><div class="label">文章总数</div></div>
    <div class="stat-card"><div class="num" style="color:#ea580c">{total_issues}</div><div class="label">机械问题条数</div></div>
    <div class="stat-card"><div class="num" style="color:#dc2626">{total_dups}</div><div class="label">重复文件事件</div></div>
  </div>

  <div class="agents-section">
    <h3>🧑‍💼 5 组专家 Agent 分工</h3>
    <div class="agents-grid">{agent_summary}</div>
  </div>

  <div class="toc">
    <h3>📋 专栏快速导航</h3>
    <div class="toc-grid">
"""
    for col_name, data in sorted(local_results.items()):
        s = data["summary"]
        indicator = "🔴" if s["p0"] > 0 or s["duplicates"] > 0 else ("🟠" if s["p1"] > 0 else ("🟡" if s["p2"] > 0 else "🟢"))
        html += f'<div class="toc-item" onclick="scrollToCol(\'{col_name}\')">{indicator} {col_name} ({s["total_files"]}篇)</div>\n'
    
    html += f"""    </div>
  </div>

  {sections_html}

</div>
<footer>HaloRead 自动审查报告 · 机械扫描覆盖全部 {total_files} 篇 · AI 深度审查每专栏抽样 3 篇</footer>

<script>
function toggleSection(header) {{
  header.classList.toggle('open');
  const body = header.nextElementSibling;
  body.classList.toggle('open');
}}
function scrollToCol(name) {{
  const sections = document.querySelectorAll('.col-section');
  for (const s of sections) {{
    if (s.querySelector('.col-name') && s.querySelector('.col-name').textContent.includes(name)) {{
      s.scrollIntoView({{behavior: 'smooth', block: 'start'}});
      const header = s.querySelector('.col-header');
      if (!header.classList.contains('open')) {{
        header.classList.add('open');
        s.querySelector('.col-body').classList.add('open');
      }}
      break;
    }}
  }}
}}
// Auto-open sections with P0 issues
document.querySelectorAll('.status-red, .status-orange').forEach(tag => {{
  const section = tag.closest('.col-section');
  if (section) {{
    section.querySelector('.col-header').classList.add('open');
    section.querySelector('.col-body').classList.add('open');
  }}
}});
</script>
</body>
</html>"""
    
    return html


# ═══════════════════════════════════════════════════════════════
# 4. Main
# ═══════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("HaloRead 多 Agent 并行内容审查系统")
    print("=" * 60)
    
    # Phase 1: Local scan
    print("\n📊 Phase 1: 本地机械扫描全部 686 篇文章...")
    local_results = local_scan_all()
    total = sum(r["summary"]["total_files"] for r in local_results.values())
    issues_count = sum(r["summary"]["total_issues"] for r in local_results.values())
    print(f"   ✅ 扫描完成: {total} 篇, 发现 {issues_count} 条机械问题")
    
    # Phase 2: Parallel AI review
    print("\n🤖 Phase 2: 5 组 Agent 并行 AI 深度审查（每专栏抽样3篇）...")
    ai_results = await run_parallel_ai_review()
    success_cols = sum(1 for gd in ai_results.values() for d in gd.values() if d.get("status") == "ok")
    print(f"   ✅ AI 审查完成: {success_cols} 个专栏深度分析完成")
    
    # Phase 3: Generate report
    print("\n📄 Phase 3: 生成 HTML 报告...")
    html = build_html_report(local_results, ai_results)
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"   ✅ 报告已生成: {REPORT_PATH}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("审查摘要:")
    for col_name, data in sorted(local_results.items()):
        s = data["summary"]
        indicator = "🔴" if s["p0"] > 0 or s["duplicates"] > 0 else ("🟠" if s["p1"] > 0 else ("🟡" if s["p2"] > 0 else "🟢"))
        print(f"  {indicator} {col_name}: {s['total_files']}篇 | 重复:{s['duplicates']} P0:{s['p0']} P1:{s['p1']} P2:{s['p2']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
