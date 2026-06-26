#!/usr/bin/env python3
"""
远端分支治理脚本（BUG-023）

用途：
  判定哪些远程分支可安全删除，dry-run 出报告或 execute 执行删除。
  解决"用户不走PR直接合入master"导致 git branch --merged 失效的问题。

判定算法（等价合入）：
  M0 merge-base ancestor 命中 → confidence=1.0（短路）
  M1 commit message 匹配（权重 0.2）
  M2 文件 blob 内容比对（权重 0.5，net-effect 最强证据）
  M3 patch-id 比对（权重 0.3，内容哈希，squash 会漏报）
  综合 confidence = 0.5*M2 + 0.3*M3 + 0.2*M1

用法：
  python scripts/branch_governance.py --mode dry-run --pattern "trae/agent-*"
  python scripts/branch_governance.py --mode execute --pattern "trae/agent-*" --yes
  python scripts/branch_governance.py --mode execute --branch trae/agent-xxx --yes
"""

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional


PROTECTED_DEFAULT = "master,main,gh-pages,release/*"
DEFAULT_PATTERN = "trae/agent-*"
DEFAULT_STALE_DAYS = 14
DEFAULT_THRESHOLD = 0.6
CONFIDENCE_NEEDS_HUMAN = 0.3

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


@dataclass
class BranchReport:
    """单个分支的治理判定报告"""
    name: str
    confidence: float
    methods: List[str] = field(default_factory=list)
    last_commit: Optional[str] = None
    unique_commits: int = 0
    verdict: str = "keep"  # delete / needs-human / keep / protected
    reason: str = ""


def run_git(args: List[str], cwd: Optional[str] = None) -> str:
    """执行 git 命令，返回 stdout。失败返回空字符串。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def fetch_all_remote_refs() -> None:
    """fetch 所有远端分支引用并 prune 已删除的。"""
    run_git(["fetch", "--prune", "origin", "+refs/heads/*:refs/remotes/origin/*"])


def detect_remote_prefix() -> tuple:
    """检测使用 origin/ 前缀（远端仓库）还是无前缀（纯本地仓库）。
    返回 (前缀, master引用)。
    """
    # 检查是否有 origin remote
    remotes = run_git(["remote"])
    if "origin" in remotes.splitlines():
        return "origin/", "origin/master"
    # 纯本地仓库（测试环境）
    return "", "master"


# 全局前缀（在 main 中初始化）
REF_PREFIX = "origin/"
MASTER_REF = "origin/master"


def _ref(branch: str) -> str:
    """给分支名加上前缀。"""
    return f"{REF_PREFIX}{branch}"


def list_remote_branches() -> List[str]:
    """列出所有分支（远端或本地），返回分支名。"""
    if REF_PREFIX:
        # 远端模式：查 origin/ 前缀
        out = run_git(["branch", "-r", "--format=%(refname:short)"])
        branches = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("origin/") and "->" not in line:
                branches.append(line[len("origin/"):])
        return branches
    else:
        # 本地模式：查本地分支
        out = run_git(["branch", "--format=%(refname:short)"])
        return [line.strip() for line in out.splitlines() if line.strip()]


def is_ancestor(branch: str) -> bool:
    """M0: branch 的 tip 是否是 MASTER_REF 的 ancestor。"""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", _ref(branch), MASTER_REF],
        capture_output=True,
        timeout=10,
    )
    return result.returncode == 0


def get_unique_commits(branch: str) -> List[str]:
    """获取分支相对 MASTER_REF 的独有提交（hash + subject）。"""
    merge_base = run_git(["merge-base", _ref(branch), MASTER_REF])
    if not merge_base:
        # 无共同祖先，全部视为独有
        out = run_git(["log", _ref(branch), "--format=%H %s"])
    else:
        out = run_git(["log", f"{merge_base}..{_ref(branch)}", "--format=%H %s"])
    return [line for line in out.splitlines() if line.strip()]


def get_changed_files(branch: str) -> List[str]:
    """获取分支相对 master 改动的文件列表。
    无 merge-base 时，用分支 tip 与 master tip 全量比对。
    """
    merge_base = run_git(["merge-base", _ref(branch), MASTER_REF])
    if merge_base:
        out = run_git(["diff", "--name-only", merge_base, _ref(branch)])
    else:
        # 无共同祖先（master 被重建过），全量比对 tip vs tip
        out = run_git(["diff", "--name-only", MASTER_REF, _ref(branch)])
    return [f for f in out.splitlines() if f.strip()]


def method_message_match(branch: str) -> tuple:
    """M1: commit message 匹配。返回 (命中比例, 详情)。"""
    unique = get_unique_commits(branch)
    if not unique:
        return 1.0, "no-unique-commits"
    hit = 0
    total = len(unique)
    for line in unique:
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        subject = parts[1].strip()
        # 去掉 type(scope): 前缀做模糊匹配
        key = subject.split(":", 1)[-1].strip() if ":" in subject else subject
        if len(key) < 6:
            continue
        # 在 MASTER_REF 历史搜索相同 message
        out = run_git(["log", MASTER_REF, "--grep", key, "--format=%H"])
        if out:
            hit += 1
    ratio = hit / total if total else 0.0
    return ratio, f"message({hit}/{total})"


def method_file_content(branch: str) -> tuple:
    """M2: 文件 blob 内容比对（net-effect）。返回 (命中比例, 详情)。
    无 changed files 意味着分支与 master 树内容完全一致 → 1.0。
    只比对分支**有**的文件：分支无但master有的（master新增）不算未命中。
    """
    changed = get_changed_files(branch)
    if not changed:
        # 无差异 = 分支与 master 完全等价
        return 1.0, "file-content-identical"
    hit = 0
    total = 0
    for f in changed:
        blob_branch = run_git(["rev-parse", f"{_ref(branch)}:{f}"])
        if not blob_branch:
            # 分支无此文件（master 新增的）→ 跳过，不算未命中
            continue
        total += 1
        blob_master = run_git(["rev-parse", f"{MASTER_REF}:{f}"])
        if not blob_master:
            # master 中该文件已删除 → 视为命中（净效果一致）
            hit += 1
        elif blob_branch == blob_master:
            hit += 1
    ratio = hit / total if total else 1.0
    return ratio, f"file-content({hit}/{total})"


def method_patch_id(branch: str) -> tuple:
    """M3: patch-id 比对。返回 (命中比例, 详情)。
    无 merge-base 时，用分支 tip vs master tip 的 diff 做 patch-id。
    """
    merge_base = run_git(["merge-base", _ref(branch), MASTER_REF])
    if merge_base:
        branch_commits = run_git(
            ["log", f"{merge_base}..{_ref(branch)}", "--format=%H"]
        ).splitlines()
    else:
        # 无共同祖先，取分支所有提交
        branch_commits = run_git(
            ["log", _ref(branch), "--format=%H"]
        ).splitlines()
    if not branch_commits:
        return 1.0, "no-unique-patches"
    branch_pids = set()
    for ch in branch_commits:
        if not ch.strip():
            continue
        diff = run_git(["show", ch])
        if diff:
            pid = run_git(["patch-id", "--stable"], cwd=None)
            # patch-id 从 stdin 读，这里用另一种方式
            try:
                result = subprocess.run(
                    ["git", "show", ch],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout:
                    pid_result = subprocess.run(
                        ["git", "patch-id", "--stable"],
                        input=result.stdout,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if pid_result.stdout.strip():
                        branch_pids.add(pid_result.stdout.split()[0])
            except (subprocess.TimeoutExpired, IndexError):
                continue
    # MASTER_REF 近 30 天 patch-id
    master_pids = set()
    master_commits = run_git(
        ["log", MASTER_REF, "--since=30 days ago", "--format=%H"]
    ).splitlines()
    for ch in master_commits:
        if not ch.strip():
            continue
        try:
            result = subprocess.run(
                ["git", "show", ch],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                pid_result = subprocess.run(
                    ["git", "patch-id", "--stable"],
                    input=result.stdout,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if pid_result.stdout.strip():
                    master_pids.add(pid_result.stdout.split()[0])
        except (subprocess.TimeoutExpired, IndexError):
            continue
    if not branch_pids:
        return 0.0, "patch-id(no-branch-pids)"
    hit = len(branch_pids & master_pids)
    ratio = hit / len(branch_pids) if branch_pids else 0.0
    return ratio, f"patch-id({hit}/{len(branch_pids)})"


def compute_confidence(branch: str) -> BranchReport:
    """综合判定分支的等价合入置信度。"""
    report = BranchReport(name=branch, confidence=0.0)
    # 最后提交时间与信息
    last_ts = run_git(["log", "-1", "--format=%ci", _ref(branch)])
    report.last_commit = last_ts
    unique = get_unique_commits(branch)
    report.unique_commits = len(unique)

    # M0 快速通道
    if is_ancestor(branch):
        report.confidence = 1.0
        report.methods = ["merge-base-ancestor"]
        report.verdict = "delete"
        report.reason = "分支是 master 的 ancestor（已通过 merge 进入 master）"
        return report

    # 无独有提交 → 已等价
    if not unique:
        report.confidence = 1.0
        report.methods = ["no-unique-commits"]
        report.verdict = "delete"
        report.reason = "无独有提交（内容已等价于 master）"
        return report

    # M1/M2/M3
    m1, d1 = method_message_match(branch)
    m2, d2 = method_file_content(branch)
    m3, d3 = method_patch_id(branch)
    report.methods = [d1, d2, d3]
    report.confidence = round(0.5 * m2 + 0.3 * m3 + 0.2 * m1, 3)

    if report.confidence >= DEFAULT_THRESHOLD:
        report.verdict = "delete"
        report.reason = f"等价合入高置信度 ({report.confidence})"
    elif report.confidence >= CONFIDENCE_NEEDS_HUMAN:
        report.verdict = "needs-human"
        report.reason = f"疑似合入需人工确认 ({report.confidence})"
    else:
        report.verdict = "keep"
        report.reason = f"有独有改动未合入 ({report.confidence})"
    return report


def delete_remote_branch(branch: str) -> bool:
    """删除分支（远端用 push --delete，本地用 branch -D）。"""
    if REF_PREFIX:
        result = subprocess.run(
            ["git", "push", "origin", "--delete", branch],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    else:
        # 本地模式（测试环境）
        result = subprocess.run(
            ["git", "branch", "-D", branch],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0


def format_report(
    reports: List[BranchReport],
    protected: List[str],
    mode: str,
    pattern: str,
    threshold: float,
) -> str:
    """格式化报告输出。"""
    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    delete_list = [r for r in reports if r.verdict == "delete"]
    human_list = [r for r in reports if r.verdict == "needs-human"]
    keep_list = [r for r in reports if r.verdict == "keep"]

    lines = []
    lines.append("=== 远端分支治理报告 ===")
    lines.append(f"时间: {now} (北京时间)")
    lines.append(f"模式: {mode}   扫描模式: {pattern}")
    lines.append(f"保护分支: {', '.join(protected)}")
    lines.append(f"阈值: {threshold}   候选分支: {len(reports)}")
    lines.append("")

    if delete_list:
        lines.append(f"[删除候选 - 等价合入] ({len(delete_list)})")
        for r in delete_list:
            lines.append(
                f"  {r.name}  confidence={r.confidence}  "
                f"methods={r.methods}  独有提交={r.unique_commits}"
            )
            if r.last_commit:
                lines.append(f"    最后提交: {r.last_commit}")
            lines.append(f"    原因: {r.reason}")
        lines.append("")

    if human_list:
        lines.append(f"[需人工确认] ({len(human_list)})")
        for r in human_list:
            lines.append(
                f"  {r.name}  confidence={r.confidence}  "
                f"methods={r.methods}"
            )
            lines.append(f"    原因: {r.reason}")
        lines.append("")

    if keep_list:
        lines.append(f"[保留 - 未合入或有独有改动] ({len(keep_list)})")
        for r in keep_list:
            lines.append(
                f"  {r.name}  confidence={r.confidence}  "
                f"独有提交={r.unique_commits}"
            )
            if r.last_commit:
                lines.append(f"    最后提交: {r.last_commit}")
        lines.append("")

    if protected:
        lines.append(f"[保留 - 受保护分支] ({len(protected)})")
        for p in protected:
            lines.append(f"  {p} (跳过)")
        lines.append("")

    lines.append(
        f"汇总: 删除候选 {len(delete_list)}, "
        f"需人工确认 {len(human_list)}, 保留 {len(keep_list)}"
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="远端分支治理（BUG-023）"
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "execute"],
        required=True,
        help="dry-run 只出报告，execute 执行删除",
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help=f"分支名 glob 模式，默认 {DEFAULT_PATTERN}",
    )
    parser.add_argument(
        "--protected",
        default=PROTECTED_DEFAULT,
        help=f"受保护分支（逗号分隔），默认 {PROTECTED_DEFAULT}",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"废弃分支判定天数，默认 {DEFAULT_STALE_DAYS}",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"等价合入置信度阈值，默认 {DEFAULT_THRESHOLD}",
    )
    parser.add_argument(
        "--branch",
        help="仅处理单个分支",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="execute 模式必须带此参数确认",
    )
    parser.add_argument(
        "--report-file",
        help="报告输出文件路径",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="跳过 fetch（CI 已 fetch 时使用）",
    )
    args = parser.parse_args()

    # execute 必须带 --yes
    if args.mode == "execute" and not args.yes:
        print("错误：execute 模式必须带 --yes 参数确认", file=sys.stderr)
        return 2

    protected = [p.strip() for p in args.protected.split(",") if p.strip()]

    # 初始化全局引用前缀（远端 origin/ 或本地无前缀）
    global REF_PREFIX, MASTER_REF
    REF_PREFIX, MASTER_REF = detect_remote_prefix()

    # 同步远端引用
    if not args.no_fetch and REF_PREFIX:
        print("同步远端引用...")
        fetch_all_remote_refs()

    # 列出分支
    all_branches = list_remote_branches()
    # 排除 master 自身（避免扫描主干）
    master_name = "master" if not REF_PREFIX else "master"
    all_branches = [b for b in all_branches if b != master_name and b != "main"]
    if not all_branches:
        # 即使无候选分支，也输出含保护分支段落的报告（修复 BUG：dry-run 无候选时输出缺失保护分支段落）
        print(format_report(reports=[], protected=protected, mode=args.mode,
                            pattern=args.pattern, threshold=args.threshold))
        return 0

    # 过滤候选
    if args.branch:
        candidates = [b for b in all_branches if b == args.branch]
    else:
        candidates = [
            b for b in all_branches
            if fnmatch.fnmatch(b, args.pattern) and b not in protected
        ]
        # 额外排除受保护模式（如 release/*）
        candidates = [
            b for b in candidates
            if not any(fnmatch.fnmatch(b, p) for p in protected)
        ]

    if not candidates:
        print(f"模式 {args.pattern} 下无候选分支（已排除受保护分支）")
        return 0

    # 判定
    print(f"扫描 {len(candidates)} 个候选分支...")
    reports = []
    for b in candidates:
        r = compute_confidence(b)
        reports.append(r)

    # 输出报告
    report_text = format_report(reports, protected, args.mode, args.pattern, args.threshold)
    print(report_text)

    if args.report_file:
        with open(args.report_file, "w", encoding="utf-8") as f:
            f.write(report_text + "\n")

    # execute
    if args.mode == "execute":
        delete_list = [r for r in reports if r.verdict == "delete"]
        if not delete_list:
            print("无可删除分支")
            return 0
        print(f"\n执行删除 {len(delete_list)} 个分支...")
        success = 0
        failed = []
        for r in delete_list:
            ok = delete_remote_branch(r.name)
            if ok:
                print(f"  ✅ 已删除 {r.name}")
                success += 1
            else:
                print(f"  ❌ 删除失败 {r.name}")
                failed.append(r.name)
        print(f"\n删除完成：成功 {success}，失败 {len(failed)}")
        if failed:
            print(f"失败分支: {', '.join(failed)}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
