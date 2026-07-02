#!/usr/bin/env python3
"""字数事实核对脚本（第一性原理：字数是确定性事实，不交给会数错 token 的 LLM）。

扫描 Markdown 中所有"声称字数"模式，用 Python len() 核对。
**字数不含标点**——中文标点（，。！？；：""''「」（）—…《》、）和英文标点
（,.!?;:'"()<>[]{}）、空白字符、Markdown 符号（# * - > ` |）均不计入。

覆盖三种写法：
- 模式A：`N 个字：X` / `N 个字，X` / `N 个字、"X"`
- 模式B（主流）：`「X」这 N 个字` / `"X"这 N 个字` / `「X」N 个字`（引号在引文前后，"这"字可选）
- 模式C：`N 个字：「X」` / `N 个字，"X"`

用法：
    python scripts/check_char_count.py --file output/史记/汉纪/07_鸿�宴.md
    python scripts/check_char_count.py --dir output/ --strict
    python scripts/check_char_count.py --dir output/ --verbose

退出码：
    0  无错误，或未用 --strict
    1  发现字数错误且使用了 --strict
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.quality import strip_frontmatter  # noqa: E402  (sys.path 需先就位)

# 中英文标点 + 空白 + Markdown 符号，均不计入字数
_PUNCT_CHARS = (
    # 中文标点
    "，。！？；：""''「」『』（）—…《》、·"
    # 英文标点
    ",.!?;:'\"()<>[]{}"
    # 破折号与省略号变体
    "\u2014\u2013\u2026\u00b7"
    # 全角空格与常规空白
    " \t\r\n\u3000"
    # Markdown 符号
    "#*- >`|"
)

# 单一信源：与 src/utils/quality.py 的 _strip_punct_for_char_count 保持一致
def strip_punct(s: str) -> str:
    """移除标点、空白与 Markdown 符号，返回纯字符序列。"""
    return "".join(ch for ch in s if ch not in _PUNCT_CHARS)


# 中文数字支持（BUG-026 的 (\d+) 只匹配阿拉伯数字，对"这八个字"等中文数字完全失效）
_CN_DIGITS = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "百": 100,
    "千": 1000, "万": 10000, "两": 2,
}

# 匹配中文数字或阿拉伯数字（"第"字开头的是序号"第一个字"，非字数声称，排除）
_NUM = r"(?<!第)([一二三四五六七八九十百千万两\d]+)"


def cn_to_int(s: str) -> int:
    """中文数字转 int。支持：三/十二/二十/二十三/一百二十等常见字数形式。

    若无法解析返回 -1（表示跳过核对）。
    """
    if not s:
        return -1
    if s.isdigit():
        return int(s)

    total = 0
    # 处理"百"
    if "百" in s:
        parts = s.split("百")
        left = _CN_DIGITS.get(parts[0], 1) if parts[0] else 1
        total += left * 100
        rest = parts[1] if len(parts) > 1 else ""
        if rest:
            if "十" in rest:
                sp = rest.split("十")
                tens = _CN_DIGITS.get(sp[0], 1) if sp[0] else 1
                total += tens * 10
                if len(sp) > 1 and sp[1]:
                    total += _CN_DIGITS.get(sp[1], 0)
            elif rest in _CN_DIGITS:
                total += _CN_DIGITS[rest]
        return total

    # 处理"十"
    if "十" in s:
        parts = s.split("十")
        left = _CN_DIGITS.get(parts[0], 1) if parts[0] else 1
        total += left * 10
        if len(parts) > 1 and parts[1]:
            total += _CN_DIGITS.get(parts[1], 0)
        return total

    # 单字
    return _CN_DIGITS.get(s, -1)


# 引号字符集（用于 B/C 模式匹配引文边界）
_QUOTE_OPEN = "「『\"'\u201c"
_QUOTE_CLOSE = "」』\"'\u201d"
_QUOTE_ANY = _QUOTE_OPEN + _QUOTE_CLOSE

# 三种模式的正则
# 模式A：N 个字：X（无引号，X 不含中文标点，到逗号/句号停）
#         保留 BUG-026 的 "5个字：你好世" 契约。引号引文交给模式C（引文可含逗号）。
_PATTERN_A = re.compile(
    _NUM + r"\s*个字[：:]\s*([^" + re.escape(_QUOTE_ANY) + r"\n，。！？；：]{1,30})"
)

# 模式B：「X」这 N 个字 / "X"。这 N 个字 / "X"——这 N 个字
#         （引号在前，"这"字必选，引号与"这"之间允许少量标点如句号/破折号/逗号）
#         要求"这"字必选以强指代，降低误报
_PATTERN_B = re.compile(
    r"[" + re.escape(_QUOTE_OPEN) + r"]([^" + re.escape(_QUOTE_ANY) + r"\n]{1,30})[" + re.escape(_QUOTE_CLOSE) + r"][\s。，；—…、\-]{0,5}这\s*" + _NUM + r"\s*个字"
)

# 模式C：N 个字："X" / N 个字，「X」 / N 个字，"X"（N个字+分隔符+引号引文，引文可含逗号）
#         必选分隔符（冒号/中文逗号/英文逗号），引文到闭合引号为止，允许含中文逗号
_PATTERN_C = re.compile(
    _NUM + r"\s*个字[：:，,]\s*[" + re.escape(_QUOTE_OPEN) + r"]([^" + re.escape(_QUOTE_CLOSE) + r"\n]{1,60})[" + re.escape(_QUOTE_CLOSE) + r"]"
)


def _scan(body: str) -> list[tuple[int, int, str, int, int, str]]:
    """对一段文本运行三种模式检测，返回原始匹配列表。

    每个元素：(start, end, snippet, expected, actual, pattern_type)
    expected == -1 表示数字无法解析，跳过核对。
    """
    out: list[tuple[int, int, str, int, int, str]] = []
    seen: set[tuple[int, int]] = set()

    # 多引号并列结构检测：闭引号 + 短词 + 开引号 + 引文 + 闭引号
    # 用于跳过 "X"和「Y」两字 / "X"，也讲"Y"两字 / "X""Y"两字 这类并列结构
    _qo = re.escape(_QUOTE_OPEN)
    _qc = re.escape(_QUOTE_CLOSE)
    _qa = re.escape(_QUOTE_ANY)
    _PARALLEL = re.compile(
        rf"[{_qc}][^{_qa}\n]{{0,15}}[{_qo}][^{_qa}\n]{{1,15}}[{_qc}]"
    )

    def _has_parallel(m_start: int, m_end: int) -> bool:
        """检查匹配前后是否有并列的引号引文（多引号并列结构）。

        五种启发式：
        1. m.start() 前一个字符是闭引号（如 "X"两个字）
        2. m.end() 后 8 字符内含开引号 + 引文 + 闭引号（如 「X」和「Y」两字）
        3. head 含 闭引号 + 短词 + 开引号 + 引文 + 闭引号 模式（如 "X"，也讲"Y"两字）
        4. head 末尾 5 字符内含 闭引号+短词+并列连词（如 「X」和 / "X"和）
        5. head 末尾 20 字符内含 闭引号+，+短词+也+动词（如 "X"，也讲 / "X"，也道）
        """
        # 规则 1：m.start() 前一个字符是闭引号
        if m_start > 0 and body[m_start - 1] in _QUOTE_CLOSE:
            return True
        # 规则 2：m.end() 后 8 字符内含开引号 + 引文 + 闭引号
        tail = body[m_end:m_end + 8]
        if re.search(rf"[{_qo}][^{_qa}\n]{{1,10}}[{_qc}]", tail):
            return True
        # 规则 3：head 含并列引号引文模式
        head = body[max(0, m_start - 50):m_start]
        if _PARALLEL.search(head):
            return True
        # 规则 4：head 末尾 5 字符内含 闭引号+短词+并列连词
        if re.search(rf"[{_qc}][^{_qa}\n]{{0,3}}[和与或、]", head[-5:]):
            return True
        # 规则 5：head 末尾 20 字符内含 闭引号+，+短词+也+动词
        if re.search(rf"[{_qc}]，[^{_qa}\n]{{0,3}}也[讲说道]", head[-20:]):
            return True
        return False

    def _add(m_start: int, m_end: int, snippet: str, expected_raw: str, x: str, ptype: str) -> None:
        if (m_start, m_end) in seen:
            return
        seen.add((m_start, m_end))
        expected = cn_to_int(expected_raw)
        if expected < 0:
            return  # 数字无法解析，跳过
        actual = len(strip_punct(x))
        if actual == 0:
            return  # 引文为空或纯标点/Markdown符号（如 ** 加粗），无法核对，跳过
        if actual != expected:
            out.append((m_start, m_end, snippet, expected, actual, ptype))

    for m in _PATTERN_A.finditer(body):
        x = m.group(2).strip().strip(_QUOTE_ANY)
        _add(m.start(), m.end(), m.group(0).strip(), m.group(1), x, "A")
    for m in _PATTERN_B.finditer(body):
        # 模式B 多引号并列跳过（如 "X"，也讲"Y"。这两个字）
        if _has_parallel(m.start(), m.end()):
            continue
        _add(m.start(), m.end(), m.group(0).strip(), m.group(2), m.group(1), "B")
    for m in _PATTERN_C.finditer(body):
        # 模式C 多引号并列跳过
        if _has_parallel(m.start(), m.end()):
            continue
        _add(m.start(), m.end(), m.group(0).strip(), m.group(1), m.group(2), "C")
    return out


def check_text(text: str) -> list[dict]:
    """检测一段文本，返回字数错误列表（自动跳过 frontmatter）。

    返回元素：{"line": int, "snippet": str, "expected": int, "actual": int, "pattern_type": "A"|"B"|"C"}
    """
    body = strip_frontmatter(text)
    offset = len(text) - len(body)
    matches = _scan(body)

    # 反推行号
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(i + 1)

    def _line_of(pos_in_body: int) -> int:
        pos_in_full = pos_in_body + offset
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos_in_full:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    return [
        {
            "line": _line_of(start),
            "snippet": snippet,
            "expected": expected,
            "actual": actual,
            "pattern_type": ptype,
        }
        for start, _end, snippet, expected, actual, ptype in matches
    ]


def check_file(path: Path) -> list[dict]:
    """检测单个文件，返回字数错误列表（每个元素附加 "file" 字段）。"""
    text = path.read_text(encoding="utf-8")
    errors = check_text(text)
    for e in errors:
        try:
            e["file"] = str(path.resolve().relative_to(ROOT))
        except ValueError:
            # 路径不在项目根下（如 tmp_path），用绝对路径
            e["file"] = str(path)
    return errors


def check_dir(directory: Path | str, glob: str = "**/*.md") -> list[dict]:
    """递归检测目录下所有 Markdown 文件，返回字数错误列表。"""
    dir_path = Path(directory)
    if not dir_path.exists():
        return []
    all_errors: list[dict] = []
    for md_path in sorted(dir_path.glob(glob)):
        if not md_path.is_file():
            continue
        try:
            file_errors = check_file(md_path)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: 读取 {md_path} 失败：{exc}", file=sys.stderr)
            continue
        all_errors.extend(file_errors)
    return all_errors


def _format_error(e: dict) -> str:
    return (
        f"{e.get('file', '?')}:{e['line']} | "
        f"声称={e['expected']} 实际={e['actual']} | "
        f"模式{e['pattern_type']} | 引文：{e['snippet']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="字数事实核对（第一性原理：字数是确定性事实，不交给 LLM）"
    )
    parser.add_argument("--file", help="单文件路径")
    parser.add_argument("--dir", default="", help="目录路径（默认 output/）")
    parser.add_argument("--glob", default="**/*.md", help="文件 glob 模式（默认 **/*.md）")
    parser.add_argument("--strict", action="store_true", help="发现错误时退出码 1")
    parser.add_argument("--verbose", action="store_true", help="显示详细匹配过程")
    args = parser.parse_args(argv)

    if not args.file and not args.dir:
        # 默认扫描 output/
        args.dir = str(ROOT / "output")

    all_errors: list[dict] = []
    scanned = 0
    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: 文件不存在：{path}", file=sys.stderr)
            return 1
        scanned = 1
        all_errors = check_file(path)
    else:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"Error: 目录不存在：{dir_path}", file=sys.stderr)
            return 1
        for _ in dir_path.glob(args.glob):
            if _.is_file():
                scanned += 1
        all_errors = check_dir(dir_path, args.glob)

    if args.verbose:
        print(f"扫描 {scanned} 个文件")
        print(f"匹配模式：A=N个字：X / B=「X」这N个字 / C=N个字：「X」")
        print()

    if not all_errors:
        print(f"✅ 共扫描 {scanned} 个文件，未发现字数错误。")
        return 0

    print(f"❌ 共扫描 {scanned} 个文件，发现 {len(all_errors)} 处字数错误：\n")
    for e in all_errors:
        print(_format_error(e))
    print(f"\n字数不含标点（中英文标点、空白、Markdown 符号均不计入）。")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
