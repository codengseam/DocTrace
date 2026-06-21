"""来源提取工具。

为 Specialist Agent 提供统一的来源解析函数。
"""


MARKERS = ["来源：", "参考资料：", "引用：", "出处：", "参考："]


def extract_sources(content: str) -> list[str]:
    """从 LLM 输出中提取文末来源列表。

    匹配常见的来源分段标记，如「来源：」「参考资料：」「引用：」等，
    并返回以 - 或数字开头的非空行列表。
    """
    for marker in MARKERS:
        idx = content.rfind(marker)
        if idx != -1:
            tail = content[idx + len(marker):]
            lines = [
                line.strip().lstrip("-0123456789. ").strip()
                for line in tail.splitlines()
                if line.strip()
            ]
            return [line for line in lines if line]
    return []
