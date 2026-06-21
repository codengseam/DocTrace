# 子计划 2：工具与存储层（MCP + Obsidian + 文件管理）

## 上下文

本项目是个人 AI 深度阅读助手，核心引擎生成 Markdown 笔记后，需要接入本地工具层：读取 PDF 史料、写入 Obsidian Vault、管理文件和资料白名单。

详见：
- [总计划](./2026-06-21-deep-reading-master-plan.md)
- [README.md](../../../../README.md)

## 目标

接入 MCP 工具，实现 PDF 资料读取、Obsidian Vault 写入、可信域搜索过滤、资料引用缓存。

## 范围

1. 实现 `src/tools/` 模块
   - `pdf_reader.py`：调用 `mcp_pdf-reader-mcp` 读取本地 PDF
   - `obsidian_writer.py`：调用 `mcp_mcp-obsidian` 写入/更新笔记
   - `web_search.py`：封装 Web 搜索，支持可信域白名单过滤
   - `source_cache.py`：记录每次查询用过的资料，避免重复搜索

2. 实现 `src/storage/` 模块
   - `file_manager.py`：文件路径管理、目录创建、文件名规范化
   - `vault_sync.py`：与 Obsidian Vault 同步，处理更新与去重
   - `metadata_store.py`：存储笔记元数据，便于后续检索

3. 配置文件
   - `.env`：API Key、Obsidian Vault 路径
   - `config.yaml`：可信搜索域、输出路径、MCP 服务器配置

4. 资料来源白名单
   - 配置可信搜索域列表
   - Agent 搜索时优先使用白名单内的来源
   - 记录实际使用的来源到 frontmatter

## 依赖

- 核心引擎的输出 Markdown 格式
- 本地 Obsidian Vault 和 MCP 环境

## 输入输出

- 输入：
  - 核心引擎生成的 Markdown 文件
  - 用户本地 PDF 文件路径
  - 配置文件
- 输出：
  - Obsidian Vault 中的笔记
  - 本地缓存文件
  - 日志

## 关键设计决策

- 工具层只提供"能力"，不直接参与 Agent 编排。Agent 通过函数调用使用工具。
- Obsidian 写入采用"主笔记 + 可选引文汇编"模式，但第一阶段只做主笔记写入。
- PDF 读取结果作为上下文注入到 Specialist Agent，不作为最终输出。
- 可信域白名单在 `config.yaml` 中配置，Web 搜索工具负责过滤。
- 文件操作统一使用 `pathlib`，编码统一 UTF-8。

## 验收标准

- [ ] 能读取本地 PDF 并提取文本供 Agent 使用
- [ ] 能将 Markdown 写入指定 Obsidian Vault
- [ ] 支持配置可信搜索域
- [ ] 支持更新已存在笔记而不重复创建
- [ ] 能记录并查询某事件已使用过的资料

## 建议执行方式

本地执行，因为涉及本地 Obsidian Vault、PDF 文件和 MCP 服务器。
