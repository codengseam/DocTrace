#!/usr/bin/env python3
"""校验指定范围内的 Git 提交信息是否符合 HaloRead 中文提交规范。

用法：
    python scripts/validate_commit_messages.py [<rev-range>]

示例：
    python scripts/validate_commit_messages.py origin/master..HEAD
    python scripts/validate_commit_messages.py HEAD~3..HEAD
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import List, Tuple


# 至少包含一个中文字符（CJK Unified Ideographs）
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def run_git(args: List[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def get_commits(rev_range: str) -> List[Tuple[str, str]]:
    """返回 (hash, message) 列表。"""
    log = run_git(["log", rev_range, "--format=%H%x00%B%x00", "--no-merges"])
    if not log.strip():
        return []
    parts = log.split("\x00")
    commits = []
    # format 输出为 hash\x00body\x00hash\x00body\x00...，最后可能有一个空元素
    for i in range(0, len(parts) - 1, 2):
        commit_hash = parts[i].strip()
        message = parts[i + 1].strip()
        if commit_hash:
            commits.append((commit_hash, message))
    return commits


def validate_message(commit_hash: str, message: str) -> List[str]:
    errors: List[str] = []
    lines = message.splitlines()
    if not lines or not lines[0].strip():
        errors.append("提交信息标题不能为空")
        return errors

    subject = lines[0].strip()

    # 标题必须包含中文
    if not CHINESE_RE.search(subject):
        errors.append(f"标题必须包含中文: '{subject}'")

    # 标题长度
    if len(subject) > 50:
        errors.append(f"标题超过 50 个字符（当前 {len(subject)}）: '{subject}'")

    # 过滤掉注释行和空行后检查正文
    body_lines = [
        line
        for line in lines[1:]
        if line.strip() and not line.strip().startswith("#")
    ]
    if not body_lines:
        errors.append("缺少正文说明；请用中文说明'为什么改'和'改了什么'")
    else:
        body = "\n".join(body_lines)
        if not CHINESE_RE.search(body):
            errors.append("正文必须用中文描述修改内容")

    # 拒绝默认合并提交信息（虽然 --no-merges 已过滤，保留兜底）
    if subject.startswith("Merge branch") or subject.startswith("Merge pull request"):
        errors.append(f"请使用非默认的合并提交说明: '{subject}'")

    return errors


def main() -> int:
    rev_range = sys.argv[1] if len(sys.argv) > 1 else "origin/master..HEAD"

    try:
        commits = get_commits(rev_range)
    except subprocess.CalledProcessError as exc:
        print(f"[validate_commit_messages] 获取提交失败: {exc}", file=sys.stderr)
        return 1

    if not commits:
        print(f"[validate_commit_messages] 范围内无提交: {rev_range}")
        return 0

    total_errors = 0
    for commit_hash, message in commits:
        errors = validate_message(commit_hash, message)
        if errors:
            total_errors += len(errors)
            short_hash = run_git(["rev-parse", "--short", commit_hash]).strip()
            print(f"\n提交 {short_hash} 不符合规范:")
            for err in errors:
                print(f"  - {err}")
            # 缩进展示原始信息，便于定位
            for line in message.splitlines():
                print(f"    {line}")

    if total_errors:
        print(
            f"\n[validate_commit_messages] 共发现 {total_errors} 处违规，"
            "请修正提交信息后再 push。",
            file=sys.stderr,
        )
        return 1

    print(
        f"[validate_commit_messages] {len(commits)} 个提交信息符合规范"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
