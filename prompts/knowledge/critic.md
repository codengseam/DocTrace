# 角色
你是「critic」节点的占位 prompt（knowledge 桶专用）。

# 说明
knowledge 桶不使用 critic 节点。

依据 `docs/archetype-design/design.md` §10.5：knowledge 桶 4 段映射为
- 概念 → context_analyst
- 原理 → historian
- 实践 → biographer
- 速查/自测 → editor

无 critic 对应段。本文件仅为避免 `load_prompt`（`src/utils/prompts.py`）fallback 警告而建——knowledge 桶主流程不会调用本 prompt。

# 占位输入
- 书籍/课程：{book}
- 章节/模块：{chapter}
- 主题：{event}
- 用户补充：{user_input}

# 输出
空字符串（如被意外调用，返回空内容，由主流程兜底处理）。
