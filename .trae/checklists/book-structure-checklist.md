# 书籍结构规范 Checklist

本 checklist 用于校验 `output/<book>/` 下 Markdown 文件的命名与 frontmatter 是否符合构建要求。配合 `scripts/build_site.py` 使用。

**使用方式**：对每本书逐文件检查，标注 ✅ 通过 / ❌ 未通过 / ➖ 不适用。未通过项必须修复。

---

## 一、文件命名规范

**约定**：`output/<book>/<chapter>_<event>.md`

- `<book>`：目录名，与 frontmatter 中的 `book` 字段一致。
- `<chapter>`：大模块/阶段名，与 frontmatter 中的 `chapter` 字段一致。
- `<event>`：模块内的单篇文章名，与 frontmatter 中的 `event` 字段一致。

### 1.1 正确示例

```text
output/史记/01_五帝本纪_黄帝.md
output/史记/01_五帝本纪_颛顼.md
output/史记/02_夏本纪_大禹治水.md
output/资治通鉴/周纪一_三家分晋.md
output/资治通鉴/秦纪二_荆轲刺秦.md
output/睡眠/01_睡眠基础_为什么需要睡眠.md
output/睡眠/02_失眠调理_入睡困难怎么办.md
```

### 1.2 错误示例

```text
❌ output/史记/07_鸿门宴.md              # 缺少 event 段，sort/chapter_sort 无法从文件名推断
❌ output/AI大模型学习/AI课01_提示工程.md # chapter 段语义不清
❌ output/锻炼/睡眠课01_睡前拉伸.md       # chapter 与书籍主题不一致
❌ output/史记/01_五帝本纪_黄帝.txt       # 扩展名不是 .md
```

### 1.3 检查项

- [ ] 文件扩展名为 `.md`
- [ ] 文件名格式为 `<chapter>_<event>.md`，仅含一个下划线分隔符
- [ ] `<chapter>` 不为纯数字前缀，语义上代表模块/阶段
- [ ] `<event>` 不为空，能概括单篇文章主题
- [ ] 同一 `<book>` 下不存在重复文件名

---

## 二、Frontmatter 必填字段

每篇 `.md` 文件必须包含以下 YAML frontmatter 字段：

```yaml
---
title: 单篇文章标题
book: 书籍目录名
chapter: 模块名（与文件名 <chapter> 一致）
event: 文章名（与文件名 <event> 一致）
sort: 1
chapter_sort: 1
---
```

### 2.1 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | string | 文章展示标题，允许与 `event` 不同 |
| `book` | string | 必须与所在目录 `<book>` 完全一致 |
| `chapter` | string | 必须与文件名中的 `<chapter>` 完全一致 |
| `event` | string | 必须与文件名中的 `<event>` 完全一致 |
| `sort` | integer | 文章在当前 chapter 内的排序，从 1 开始连续递增 |
| `chapter_sort` | integer | chapter 在全书中的排序，从 1 开始递增 |

### 2.2 检查项

- [ ] `title` 存在且为非空字符串
- [ ] `book` 存在且与目录名一致
- [ ] `chapter` 存在且与文件名 `<chapter>` 一致
- [ ] `event` 存在且与文件名 `<event>` 一致
- [ ] `sort` 存在且为整数
- [ ] `chapter_sort` 存在且为整数

---

## 三、Sort 语义

### 3.1 chapter_sort（大模块顺序）

- `chapter_sort` 决定**大模块/阶段**在全书中的展示顺序。
- 同一本书内，**不同大模块**的 `chapter_sort` 应唯一且递增；同一模块下的多个 chapter 可以共用同一个 `chapter_sort`。
- 例如《易经课》中：开篇=1、基础=2、上经=3、下经=4、易传=5、应用=6、占卜=7、总结=8。

### 3.2 sort（模块内顺序）

- 基础语义：`sort` 决定文章在当前 chapter 内的展示顺序，从 1 开始连续递增，无重复。
- 扩展语义：当一本书把**每个细粒度单元作为一个 chapter**（如《易经课》每卦一个 chapter）时，`sort` 可用于表示该单元在其所属大模块内的位置，此时允许单事件 chapter 的 `sort` 不为 1。
- 同一 chapter 内 `sort` 必须唯一，且整体保持递增。

### 3.3 检查项

- [ ] 同一 `book` 下，不同大模块的 `chapter_sort` 无重复且递增
- [ ] 同一 `chapter` 内 `sort` 唯一且递增
- [ ] 常规多事件 chapter 的 `sort` 从 1 开始连续递增
- [ ] 单事件 chapter 的 `sort` 通常为 1；若该书存在共用同一 `chapter_sort` 的多个 chapter，可作为模块内位置标号

---

## 四、特殊书籍处理

### 4.1 资治通鉴类：章节名含 dynasty + 纪

文件名示例：

```text
output/资治通鉴/周纪一_三家分晋.md
output/资治通鉴/周纪二_田氏代齐.md
output/资治通鉴/秦纪一_商鞅变法.md
output/资治通鉴/秦纪二_荆轲刺秦.md
output/资治通鉴/汉纪一_鸿门宴.md
```

- `chapter` 字段仍等于文件名中的 `周纪一`、`秦纪二` 等。
- `chapter_sort` 按朝代分组递增：
  - 周纪 = 1
  - 秦纪 = 2
  - 汉纪 = 3
  - 魏纪 = 4
  - 晋纪 = 5
  - 宋纪 = 6
  - 齐纪 = 7
  - 梁纪 = 8
  - 陈纪 = 9
  - 隋纪 = 10
  - 唐纪 = 11
  - 后梁纪 = 12
  - 后唐纪 = 13
  - 后晋纪 = 14
  - 后汉纪 = 15
  - 后周纪 = 16
- 同一 dynasty 内，按「一、二、三...」顺序继续递增。

### 4.2 现代课程类：原使用纯数字前缀

如 `AI大模型学习`、`睡眠`、`锻炼` 等书籍，原文件名可能是：

```text
output/睡眠/睡眠课01_为什么需要睡眠.md
output/睡眠/睡眠课02_如何快速入睡.md
```

**推荐做法**：拆分为模块，明确 `<chapter>` 语义。

```text
output/睡眠/01_睡眠基础_为什么需要睡眠.md
output/睡眠/02_失眠调理_如何快速入睡.md
```

**最低要求**（暂时无法重组模块时）：

- 将原 `睡眠课01` 作为 `<chapter>`，`为什么需要睡眠` 作为 `<event>`。
- 必须补全 `chapter_sort` 和 `sort`。
- 不允许 chapter 字段与书籍主题无关（如 `AI课01` 出现在 `睡眠` 书中）。

### 4.3 检查项

- [ ] 资治通鉴类 `chapter_sort` 按朝代顺序递增
- [ ] 现代课程类已尽量拆分为语义模块
- [ ] 无法拆分时，`chapter_sort` 和 `sort` 仍已补全
- [ ] 不存在 chapter 字段与书籍主题明显不符的情况

---

## 五、问题严重度表

| 级别 | 说明 | 典型问题 | 处理要求 |
|---|---|---|---|
| **P0** | 构建阻断 | 缺少 frontmatter、`book`/`chapter`/`event` 与路径不一致、`sort`/`chapter_sort` 缺失 | 必须修复，否则构建脚本无法正确解析 |
| **P1** | 排序混乱 | `sort` 不连续或重复、`chapter_sort` 倒序或重复、单事件 chapter 的 `sort` 不为 1 | 必须修复，影响目录展示顺序 |
| **P2** | 命名不规范 | 纯数字前缀文件名、`<chapter>` 语义不清、扩展名错误、chapter 与主题不符 | 建议修复，提升可维护性 |

---

## 六、检查记录表

| 文件路径 | book | chapter | event | sort | chapter_sort | 问题 | 严重度 | 修复状态 |
|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |

---

## 七、自检报告模板

```markdown
## 书籍结构自检报告

### 检查范围
- 书籍目录：____
- 文件数量：____

### 命名规范
- ✅/❌ 文件名格式正确
- ✅/❌ 无纯数字前缀
- ✅/❌ 扩展名正确

### Frontmatter
- ✅/❌ title 存在且非空
- ✅/❌ book 与目录名一致
- ✅/❌ chapter 与文件名一致
- ✅/❌ event 与文件名一致
- ✅/❌ sort 为整数
- ✅/❌ chapter_sort 为整数

### Sort 语义
- ✅/❌ chapter_sort 无重复、整体递增
- ✅/❌ 同 chapter 内 sort 从 1 连续递增
- ✅/❌ 单事件 chapter sort = 1

### 特殊书籍
- ✅/❌ 资治通鉴类按朝代排序
- ✅/❌ 现代课程类已分组或已补全字段

### 问题汇总
| 文件 | 问题 | 严重度 | 修复状态 |
|---|---|---|---|
|  |  |  |  |

### 总结
- P0 问题数：__
- P1 问题数：__
- P2 问题数：__
- 是否可构建：是 / 否
```
