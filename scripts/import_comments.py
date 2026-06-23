#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
半自动导入脚本：从 GitHub Issues 读取待审核段评，生成 site/data/comments/<notePath>.json。

用法示例：
    export GITHUB_TOKEN=ghp_xxx
    python scripts/import_comments.py --owner codengseam --repo HaloRead

管理员工作流：
1. 在 GitHub Issues 审核评论。
2. 对通过的 issue 保持 open 并带有标签 "段评"、"待审核"。
3. 运行本脚本，自动把评论写入对应 JSON 文件。
4. 关闭或删除已导入的 issue，重新构建部署站点。
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMENTS_DIR = REPO_ROOT / "site" / "data" / "comments"


def fetch_issues(owner: str, repo: str, token: str, labels: str = "段评,待审核") -> list[dict[str, Any]]:
    """从 GitHub Issues API 获取带指定标签的 open issues。"""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = f"?state=open&labels={urllib.request.quote(labels)}&per_page=100"
    req = urllib.request.Request(url + params)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def parse_issue_title(title: str) -> tuple[str, str] | None:
    """
    解析标题 `[段评] <notePath> #<pid>`。
    返回 (notePath, paragraphId) 或 None。
    """
    m = re.search(r"\[段评\]\s*(.+?)\s*#(\S+)\s*$", title.strip())
    if not m:
        return None
    note_path = m.group(1).strip()
    pid = m.group(2).strip()
    return note_path, pid


def parse_issue_body(body: str) -> dict[str, str] | None:
    """
    解析 issue body 中的 Markdown 字段：
    **段落**：...
    **类型**：...
    **作者**：...
    **内容**：

    content
    """
    if not body:
        return None

    fields = {}
    for key in ("段落", "类型", "作者", "内容"):
        # 支持 **内容**：后换行再跟多行正文
        pattern = rf"\*\*{re.escape(key)}\*\*\s*：\s*(.*?)\n"
        m = re.search(pattern, body, re.MULTILINE)
        if m:
            fields[key] = m.group(1).strip()

    # 内容可能在 "**内容**：" 之后的多行，取剩余全部
    content_match = re.search(r"\*\*内容\*\*\s*：\s*\n+(.*)", body, re.DOTALL)
    if content_match:
        fields["内容"] = content_match.group(1).strip()

    if "内容" not in fields or not fields["内容"]:
        return None

    return fields


def type_to_key(label: str) -> str:
    """把中文类型映射为 JSON 中的 key。"""
    mapping = {"勘误": "erratum", "讨论": "discuss", "感想": "note"}
    return mapping.get(label.strip(), "discuss")


def load_json_file(note_path: str) -> dict[str, Any]:
    """加载已有的评论 JSON，不存在则返回空结构。"""
    safe_path = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_\-/]", "_", note_path)
    file_path = COMMENTS_DIR / f"{safe_path}.json"
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"notePath": note_path, "total": 0, "comments": []}


def save_json_file(note_path: str, data: dict[str, Any]) -> Path:
    """保存评论 JSON，自动创建目录。"""
    safe_path = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_\-/]", "_", note_path)
    file_path = COMMENTS_DIR / f"{safe_path}.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return file_path


def dedupe_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按内容 + 作者 + 段落去重，保留先出现的。"""
    seen = set()
    result = []
    for c in comments:
        key = (c.get("paragraphId", ""), c.get("content", ""), c.get("author", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(c)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="将 GitHub Issues 中的段评导入 JSON 文件")
    parser.add_argument("--owner", required=True, help="仓库所有者")
    parser.add_argument("--repo", required=True, help="仓库名")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub PAT，也可通过 GITHUB_TOKEN 环境变量传入")
    parser.add_argument("--labels", default="段评,待审核", help="筛选的标签，逗号分隔")
    args = parser.parse_args()

    if not args.token:
        print("错误：缺少 GitHub token，请使用 --token 或设置 GITHUB_TOKEN 环境变量", file=sys.stderr)
        return 1

    try:
        issues = fetch_issues(args.owner, args.repo, args.token, args.labels)
    except urllib.error.HTTPError as e:
        print(f"请求 GitHub Issues 失败: {e.code} {e.reason}", file=sys.stderr)
        return 1

    if not issues:
        print("没有待导入的段评 issue。")
        return 0

    # 按 notePath 分组
    groups: dict[str, list[dict[str, Any]]] = {}
    skipped = []

    for issue in issues:
        title = issue.get("title", "")
        body = issue.get("body", "")
        parsed_title = parse_issue_title(title)
        parsed_body = parse_issue_body(body)

        if not parsed_title or not parsed_body:
            skipped.append((issue.get("number"), title))
            continue

        note_path, pid = parsed_title
        comment = {
            "id": f"c{issue.get('id')}",
            "notePath": note_path,
            "paragraphId": pid,
            "content": parsed_body.get("内容", ""),
            "author": parsed_body.get("作者", "佚名"),
            "type": type_to_key(parsed_body.get("类型", "讨论")),
            "createdAt": issue.get("created_at"),
        }
        groups.setdefault(note_path, []).append(comment)

    # 写入 JSON
    written_files = []
    for note_path, comments in groups.items():
        data = load_json_file(note_path)
        existing = {c.get("id") for c in data.get("comments", [])}
        new_comments = [c for c in comments if c["id"] not in existing]
        if not new_comments:
            continue

        data["comments"].extend(new_comments)
        data["comments"] = dedupe_comments(data["comments"])
        data["total"] = len(data["comments"])
        file_path = save_json_file(note_path, data)
        written_files.append((file_path, len(new_comments)))

    # 输出结果
    print(f"共处理 {len(issues)} 个 issue。")
    if written_files:
        print("已写入文件：")
        for path, count in written_files:
            print(f"  {path}  (+{count})")
    if skipped:
        print(f"跳过 {len(skipped)} 个无法解析的 issue：")
        for number, title in skipped:
            print(f"  #{number}: {title}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
