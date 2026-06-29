# 资治通鉴专栏续写规范（deep-reading 附录）

> 适用：output/资治通鉴/ 下新增/续写章节。本规范是 deep-reading SKILL.md 在资治通鉴专栏的专章补充，不覆盖通用 rules.md。

## 一、前置检查

每次续写前必做三件事：
1. 跑 `python scripts/check_book_structure.py --output output --strict`，确认资治通鉴专栏 P0/P1/P2 全清零（当前已修复，参见 docs/loop_log.md BUG-022）。
2. 读 `prompts/narrative/_zizhi_volume_check.md` 核验本次要写的事件归属阶段号与卷次范围。
3. grep `output/资治通鉴/` 与 `output/史记/` `output/唐纪/` 等同纪同主题已有章节，按 `prompts/narrative/_dedup_strategy.md` 分配主场/客场。

## 二、frontmatter 模板

资治通鉴走阶段模式（STAGE_MODE_BOOKS，src/utils/sorting.py:71），每篇 md 必须含：
```yaml
---
title: 资治通鉴·{chapter}·{event}
book: 资治通鉴
chapter: {chapter}       # 形如「唐纪一」「后周纪五」，中文序号
event: {event}
sort: {N}                # 章内事件序号，同 chapter 内递增不重复
chapter_sort: {阶段号}   # 见 prompts/narrative/_zizhi_volume_check.md，唐纪=11，后周纪=16
created_at: YYYY-MM-DD HH:MM:SS
source_agents:
- historian
- biographer
- context_analyst
- critic
- philosopher
- editor
---
```
注：sort 字段缺失不阻断 check_book_structure（已实测），但影响 site/data/index.json 章内顺序，必须填。

## 三、生成命令

无 LLM_API_KEY 时用 --stub 生成占位骨架，再用人工/agent 填充：
```bash
python src/main.py --book 资治通鉴 --chapter 唐纪一 --event 晋阳起兵 --stub
```
有 API Key 时去掉 --stub 走完整 narrative 管线（tone_setter→5 specialist→editor→quality→chief_editor）。

## 四、必带引用

每篇「## 参考来源」至少包含：
1. 《资治通鉴·{chapter}》（本事 + 臣光曰，若本事件有）
2. 至少 1 条正史对应篇章（史记/汉书/后汉书/三国志/晋书/宋书/南齐书/梁书/陈书/隋书/旧唐书/新唐书/旧五代史/新五代史，按阶段选）
3. 至少 1 条名家点评（王夫之《读通鉴论》/胡三省音注/司马光臣光曰 三选一以上）
4. 跨章交叉引用（若涉及同主题客场，见 _dedup_strategy.md）

新章节引用必须同步登记到 `output/资治通鉴/_references.yaml`（结构见该文件顶部说明）。

## 五、续写完成自检

每写完一批（建议 5 章/批）：
1. `python scripts/check_book_structure.py --output output --strict` 必须 0 问题
2. `pytest -q tests/test_book_structure.py tests/test_sorting.py` 通过
3. 抽查每篇 frontmatter：chapter_sort 与阶段号一致、sort 章内递增、title 与文件名匹配
4. 跑 `python scripts/build_site.py` 后看 site/data/index.json 资治通鉴顺序正确
5. 同步更新 _references.yaml
6. 在 docs/loop_log.md 追加 #lesson: book_structure / #lesson: content_quality 沉淀
