---
title: AI课·MCP协议
book: AI大模型学习
chapter: 模块 4｜Agent 与 RAG
event: MCP协议
created_at: 2026-06-23
source_agents: ['ai-expert']
---

# 第 22 章：MCP 协议：AI 工具的 USB 接口

> 前置知识：学完第 21 章（工具调用）即可
> 学完你能：①理解 MCP 解决什么问题 ②知道 MCP 的基本架构 ③看懂为什么 MCP 会成为标准

## 一、讲清楚：每个 AI 平台一套接口，重复造轮子

上一章讲了工具调用——给 AI 装上"手"。但你很快会发现一个新问题：每家 AI 平台的"手"接口都不一样。

你想给 ChatGPT 接一个数据库查询工具，得按 OpenAI 的 Function Calling 格式写一遍；同一个工具想给 Claude 用，得按 Anthropic 的 tool_use 格式再写一遍；想给 Coze 用，得按 Coze 的插件格式再写一遍。三套接口、三套代码、三个适配层，干的却是同一件事——查数据库。

这不是个例，是普遍现象。截至 2024 年，主流 AI 平台的工具集成方式几乎都各自为政：OpenAI 有 Function Calling、Anthropic 有 tool_use、Google 有 Function Calling、Coze 有插件市场、Dify 有工具节点……每家都自己定义"工具长什么样、怎么调、怎么返回"。开发者要给一个工具接 N 个平台，就得写 N 套适配代码。

这种重复造轮子浪费了大量精力，也阻碍了生态发展——小团队根本没精力给每个平台都适配一遍，结果就是好工具只能用在少数平台上。

MCP（Model Context Protocol，模型上下文协议）就是为解决这个问题而生的。它由 Anthropic 在 2024 年 11 月推出，目标是统一 AI 工具的接口标准——让一个工具写一次，能在所有支持 MCP 的 AI 应用里用。

本章解决三个问题：MCP 到底解决什么问题、它的架构是怎样的、为什么它有可能成为事实标准。学完之后，你能看懂 MCP 的设计思路，也能在 Claude Desktop 里实际配一个 MCP Server 跑起来。

## 二、看案例：同一个数据库插件，三套代码

来看一个真实场景。你团队有个内部数据库，存着订单、用户、库存数据。你想让 AI 助手能查这个数据库，于是开始给各家平台做适配。

**给 ChatGPT 做**：按 OpenAI 的格式写一个工具定义，包含 `name`、`description`、`parameters`（JSON Schema）。然后写一段后端代码，接收 OpenAI 转发过来的工具调用请求，执行 SQL，把结果按 OpenAI 期望的格式返回。这套代码跑在 OpenAI 的 Function Calling 框架里。

**给 Claude 做**：按 Anthropic 的格式写工具定义，字段叫 `input_schema` 而不是 `parameters`，格式略有差异。后端代码也得按 Anthropic 的接口写——接收 `tool_use` 请求，返回 `tool_result`。又是一套代码。

**给 Coze 做**：在 Coze 平台注册一个插件，按 Coze 的插件规范定义输入输出，把后端服务部署成 Coze 能调用的 HTTP 接口。第三套代码。

三套代码干的是同一件事：接收"查数据库"的请求、执行 SQL、返回结果。差别只在接口格式——就像三个不同形状的插头，插的是同一个电器。

更麻烦的是维护。数据库 schema 改了（比如加了个字段），你得在三套代码里都改一遍。任何一个平台改了接口规范，你又得跟着改。工具越多，这种适配负担越重。

**有了 MCP 之后**：你只需要写一个 MCP Server，把数据库查询能力暴露成 MCP 协议的标准接口。ChatGPT、Claude、Coze、Cursor——任何支持 MCP 的 AI 应用都能直接连这个 Server，不用你再为每家平台写适配代码。写一次，到处用。

这就是 MCP 想解决的核心问题：**把"工具接口"从"每家平台自定义"变成"全行业统一标准"**。

## 三、上手步骤

### 1. MCP 是什么：Anthropic 推出的开放协议

MCP（Model Context Protocol，模型上下文协议）是 Anthropic 在 2024 年 11 月开源的一个协议，规范文档和参考实现都放在 GitHub 上（github.com/modelcontextprotocol）。

MCP 的定位很明确：**AI 应用和外部能力之间的标准通信协议**。它不绑定任何一家模型厂商，任何 AI 应用都可以按协议实现 MCP Client，任何工具提供方都可以按协议实现 MCP Server，两边用标准协议对话，互不关心对方内部实现。

最贴切的类比是 USB 接口。USB 出现之前，电脑外设接口五花八门——键盘用 PS/2、鼠标用串口、打印机用并口、扫描仪用 SCSI……每个外设都得配专门的接口和驱动。USB 出来后，所有外设统一用一个口，插上就能用。MCP 之于 AI 工具，就是 USB 之于电脑外设——一个标准接口，插所有能力。

需要说明的是：MCP 不仅仅支持"工具调用"（Tools），还支持"资源"（Resources，让 AI 读取文件、数据等只读内容）和"提示"（Prompts，预定义的提示词模板）。但实际使用中最主流的是 Tools，本章也聚焦在 Tools 这部分。

### 2. MCP 架构：Server、Client、协议层

MCP 的架构由三部分组成：

**MCP Server（服务端）**：提供能力的一方。一个 MCP Server 通常封装一类能力——比如"文件系统访问 Server"、"GitHub 操作 Server"、"数据库查询 Server"。Server 把自己的能力按 MCP 协议暴露出来，等 Client 来调用。Server 可以用 Python、TypeScript 等语言写，Anthropic 提供了官方 SDK。

**MCP Client（客户端）**：使用能力的一方，通常嵌在 AI 应用里。Claude Desktop、Cursor、Zed 这些支持 MCP 的应用，内部都实现了 MCP Client。Client 负责连接 Server、发现 Server 提供哪些工具、在模型需要时调用对应工具、把结果返回给模型。

**协议层**：定义 Server 和 Client 怎么对话。MCP 基于 JSON-RPC 2.0（一种用 JSON 编码的远程过程调用协议），通信内容是结构化的 JSON 消息。传输方式支持两种：stdio（标准输入输出，适合本地 Server）和 SSE/HTTP（适合远程 Server）。

整个流程大致是：

1. AI 应用启动时，MCP Client 连接配置好的 MCP Server。
2. Client 调用 Server 的 `list_tools` 方法，发现 Server 提供哪些工具。
3. 用户提问，模型判断要不要调工具、调哪个。
4. Client 通过协议调用 Server 对应的工具方法（`call_tool`），传入参数。
5. Server 执行工具逻辑，返回结果。
6. Client 把结果交给模型，模型组织回答。

对用户和模型来说，整个过程是透明的——模型只看到"有这些工具可用"，不关心工具是 MCP Server 提供的还是应用内置的。

### 3. 实操：在 Claude Desktop 里配置一个 MCP Server

Claude Desktop 是最早原生支持 MCP 的 AI 应用之一。下面演示在 Claude Desktop 里配置一个文件系统访问的 MCP Server，让 Claude 能读写本地文件。

**环境准备**：

- 安装 Claude Desktop（claude.ai/download）。
- 本机装好 Node.js（用于跑官方的 filesystem MCP Server）。

**操作步骤**：

1. 找到 Claude Desktop 的配置文件。macOS 在 `~/Library/Application Support/Claude/claude_desktop_config.json`，Windows 在 `%APPDATA%\Claude\claude_desktop_config.json`。文件不存在就新建。

2. 编辑配置文件，加入 filesystem MCP Server：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/yourname/Documents"
      ]
    }
  }
}
```

`args` 最后那个路径是允许 Claude 访问的目录，换成你自己的路径。这个路径是安全边界——Claude 只能访问这个目录下的文件，不能越界。

3. 完全退出 Claude Desktop（不是关窗口，是退出进程），重新打开。

4. 在 Claude 对话里测试。问："我 Documents 文件夹里有哪些文件？" Claude 会调用 filesystem Server 的 `list_directory` 工具，返回真实文件列表。

5. 进一步测试。问："读一下 Documents 里的 readme.md，总结内容。" Claude 会调用 `read_file` 工具读取文件，再总结。

**预期结果**：Claude 能列出指定目录的文件、读取文件内容、写入文件（如果工具支持）。回答里会显示"调用了 filesystem 工具"。

**常见报错**：

- **Claude 启动后看不到 MCP 工具**：检查配置文件 JSON 格式是否正确、路径是否对、Node.js 是否装好。Claude Desktop 的日志在 `~/Library/Logs/Claude/` 下，能看到 MCP 加载错误。
- **工具调用报"权限不足"**：filesystem Server 只能访问配置里指定的目录。访问目录外的文件会报错。改配置加上对应目录。
- **npx 下载慢或失败**：`@modelcontextprotocol/server-filesystem` 是官方包，从 npm 下载。网络问题可以配 npm 镜像。

配好这一个 Server 后，你就理解了 MCP 的实际形态——一个独立进程，按协议暴露工具，被 AI 应用通过 Client 调用。换任何其他 MCP Server（GitHub、Slack、数据库……），配置方式都一样，只是 `command` 和 `args` 不同。

### 4. 现状（2026 年）：MCP 生态发展到哪了

截至 2026 年中，MCP 的生态已经初具规模，但还在快速演进。几个关键事实：

**支持 MCP 的 AI 应用**：Claude Desktop、Cursor、Zed、Continue、Cline 等主流 AI 编程工具和助手都已原生支持 MCP Client。OpenAI 在 2025 年宣布支持 MCP，ChatGPT 部分场景可以连 MCP Server。Coze、Dify 等平台也在跟进。整体趋势是主流 AI 应用陆续把 MCP 支持提上日程。

**现成的 MCP Server**：社区和厂商已经实现了大量 MCP Server，覆盖常见场景。官方仓库（github.com/modelcontextprotocol/servers）提供了一批参考实现，包括 filesystem、git、github、slack、google-drive、postgres、sqlite、fetch 等。第三方社区还有更多。

**协议版本**：MCP 规范仍在迭代，2025 年发布了几个新版本，加入了 streaming、远程传输增强等特性。协议本身还在演化，但核心接口（tools、resources、prompts）已经稳定。

**生态痛点**：MCP 还没完全解决"发现"问题——你想找个能查某 API 的 MCP Server，没有官方统一的注册中心，得靠 GitHub 搜索或第三方社区目录（如 mcp.so、glama.ai 这类）。Server 质量也参差不齐，生产用之前得自己测。安全也是关注点——MCP Server 能访问你的文件、数据库、API，配错权限风险不小。

整体趋势是：MCP 正在成为 AI 工具集成的事实标准，类似 HTTP 之于网页通信。但离"所有工具都用 MCP"还有距离，传统 Function Calling 接口在短期内不会消失，两者会并存一段时间。

## 四、验收标准

学完这一章，用下面三条验收自己：

1. **能说清 MCP 解决什么问题**：用大白话讲明白"工具接口碎片化"问题——每家 AI 平台一套接口，开发者要重复适配。MCP 用一个统一协议解决这件事。能举出"同一个工具给三个平台写三套代码"的例子。
2. **能讲清 MCP 的基本架构**：Server（提供能力）、Client（AI 应用里的调用方）、协议层（JSON-RPC 2.0，stdio 或 SSE 传输）。能说清 Client 怎么发现 Server 的工具、怎么调用、怎么拿结果。
3. **能在 Claude Desktop 里配置一个 MCP Server**：按上面 filesystem 的步骤配好，让 Claude 能列出指定目录的文件、读取文件内容。看到 Claude 真的调用了 MCP 工具，而不是瞎编文件名。

第三条是硬指标。配不通就回去查 JSON 格式、路径、Node.js 环境这几个常见坑。

## 五、悟本质：工具接口的标准化

MCP 的本质，可以用一句话概括：**工具接口的标准化——像 HTTP 统一了网页通信一样，MCP 想统一 AI 工具的通信**。

回顾计算机史，每一次大生态的爆发，背后都有一层接口标准化：

- **HTTP 统一了网页通信**：浏览器和服务器不用各自约定协议，任何网页任何浏览器都能互通。Web 生态因此爆发。
- **SQL 统一了数据库查询**：不管底层是 MySQL、Postgres 还是 Oracle，应用层都用 SQL 对话。数据库生态因此互通。
- **USB 统一了外设接口**：键盘、鼠标、U 盘、打印机用一个口，外设生态因此繁荣。

MCP 想做的，是 AI 领域的"HTTP/SQL/USB"——把工具接口标准化，让任何 AI 应用能连任何工具，任何工具能服务任何 AI 应用。

这个本质有几个推论：

**推论 1：MCP 的价值随生态规模网络化增长。**

一个 MCP Server 能用的人越多，越值得写；一个 AI 应用支持的 MCP Server 越多，越值得用。这是典型的网络效应——参与者越多，对每个人都越有价值。这也是为什么 MCP 一旦跨过临界点，就可能快速成为事实标准。

**推论 2：标准化的是"接口"，不是"实现"。**

MCP 不规定工具内部怎么实现——你用 Python 还是 Java、调什么 API、做什么计算，都随便。它只规定"工具怎么被发现、怎么被调用、结果怎么返回"。这和 HTTP 一样——HTTP 不规定网页内容长什么样，只规定浏览器和服务器怎么对话。这种"只管接口不管实现"的标准化，是最有生命力的——它给了实现方最大自由，同时保证了互通。

**推论 3：MCP 不取代工具调用，而是封装工具调用。**

上一章讲的工具调用（Tool Calling）是"模型怎么决定调工具、怎么传参数"——这是模型层的能力，MCP 不动它。MCP 解决的是"工具怎么被实现和暴露"——这是工具层的事。两者是互补关系：模型用 Tool Calling 决定调什么，MCP Server 提供被调的工具，Client 在中间做桥接。所以 MCP 不是 Tool Calling 的替代品，而是 Tool Calling 的"工具供应链标准化"。

**推论 4：标准化的红利是长期的，但短期会有阵痛。**

任何标准化的早期，都是新旧并存——HTTP 出来时还有大量 FTP、Gopher 站点；USB 出来时老接口设备还在用。MCP 也一样，短期内 Function Calling 和 MCP 会并存，开发者要适配两套。但长期看，标准化几乎一定会赢——因为重复造轮子的成本太高，没人愿意长期承担。早学早受益。

## 六、结语

MCP 把 AI 工具的接口标准化——一个 Server 写一次，所有支持 MCP 的 AI 应用都能用。它想做的，是 AI 时代的 USB 接口。
