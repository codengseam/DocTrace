# 角色
（modern 桶不使用 biographer 节点）

# 说明
modern 桶（理财/职场/养生）的 5 段结构为：入戏/破题/方法论/避坑/践行，不包含人物传记段，因此不调用 biographer（见 `src/agents/editor.py` SECTION_TEMPLATES["modern"]、design.md §9.2、§10.2）。

本文件仅用于避免 `load_prompt` 在 modern 桶加载 biographer 时 fallback 到 narrative 原路径并触发 UserWarning（见 `src/utils/prompts.py` load_prompt、design.md §9 阶段4）。实际 workflow 不会进入此分支。

# 占位符
与 narrative 版保持一致，预防性保留：
- 书籍：{book}
- 章节：{chapter}
- 事件：{event}
- 用户补充：{user_input}

# 输出格式
若被意外调用，直接返回空字符串，不输出任何段落正文。
