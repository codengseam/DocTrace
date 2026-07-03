"""archetype 分桶阶段2测试：质检分桶。

测试契约（来自 docs/archetype-design/design.md §8 质检规则分桶细则）：
- run_content_quality_checks 接受 archetype 参数，默认 "narrative"（向后兼容）
- modern/knowledge 桶跳过古籍专属规则（年份/名家/时间线/现代术语禁用）
- knowledge 桶用 KNOWLEDGE_TERMS_WHITELIST 做中英混杂白名单
- check_numeric_facts 的 auto_errors 全桶都跑（数字硬错误是通用检查）
- check_ai_cliches 全桶都跑（套话黑名单是通用检查）
- check_numeric_facts 的 manual_review：narrative 保留，modern/knowledge 过滤 N年前后/N岁 误标
- _is_modern_column / _is_philosophy_or_classic 已删除（由 archetype 取代）

禁区：src/utils/quality.py 内部零改动，所有路由在 content_quality.py 调用层完成。
"""
import pytest

from src.utils.content_quality import run_content_quality_checks


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def _make_content(title: str, body: str) -> str:
    """构造带 frontmatter 的测试内容。"""
    return f"""---
title: {title}
book: {title}
chapter: 测试章
event: 测试事件
sort: 1
chapter_sort: 1
---

{body}
"""


# ---------------------------------------------------------------------------
# 契约1：签名与默认值
# ---------------------------------------------------------------------------

class TestRunContentQualityChecksSignature:
    """run_content_quality_checks 接受 archetype 参数，默认 narrative。"""

    def test_accepts_archetype_param(self):
        """传 archetype="modern" 不报错（当前代码无此参数会 TypeError）。"""
        content = _make_content("测试书", "普通内容")
        report = run_content_quality_checks(content, archetype="modern")
        assert report is not None

    def test_default_archetype_is_narrative(self):
        """不传 archetype 时默认 narrative，行为与显式传 narrative 一致。"""
        content = _make_content("测试书", "普通内容")
        default_report = run_content_quality_checks(content)
        narrative_report = run_content_quality_checks(content, archetype="narrative")
        assert default_report.score == narrative_report.score
        assert default_report.issues == narrative_report.issues


# ---------------------------------------------------------------------------
# 契约2：modern 桶跳过古籍专属规则
# ---------------------------------------------------------------------------

class TestModernBucketSkipsAncientRules:
    """modern 桶（理财/职场/养生）不跑古籍专属检查。

    当前 BUG：MODERN_BOOK_KEYWORDS 只有 8 词（职场/沟通/面试/商科/心理学/管理/营销/销售），
    漏掉'理财'，导致理财课被误报'缺年份''缺名家'。
    """

    def test_modern_skips_year_check_for_finance(self):
        """modern 桶对理财课不检查年份必填（当前代码会误报）。"""
        content = _make_content("理财课", "本章讲 ETF 的配置思路，无年份标注。")
        report = run_content_quality_checks(content, archetype="modern")
        truth_issues = report.details.get("truth", [])
        assert not any("年份" in i for i in truth_issues), (
            f"modern 桶不应检查年份，却报：{truth_issues}"
        )

    def test_modern_skips_famous_critics_check(self):
        """modern 桶不强制要求司马光等古籍名家。"""
        content = _make_content("理财课", "格雷厄姆说买股票要看内在价值。")
        report = run_content_quality_checks(content, archetype="modern")
        truth_issues = report.details.get("truth", [])
        assert not any("司马光" in i or "名家" in i for i in truth_issues), (
            f"modern 桶不应强制古籍名家，却报：{truth_issues}"
        )

    def test_modern_skips_temporal_order_check(self):
        """modern 桶跳过历史时间线检查。"""
        content = _make_content("理财课", "## 讲事情\n无时间标注的内容。\n")
        report = run_content_quality_checks(content, archetype="modern")
        sequence_issues = report.details.get("sequence", [])
        assert not any("时间" in i or "年份" in i for i in sequence_issues), (
            f"modern 桶不应检查时间线，却报：{sequence_issues}"
        )

    def test_modern_skips_modern_jargon_check(self):
        """modern 桶不跑 check_modern_jargon（'底层逻辑'等词在现代语境是正常词）。

        注意区分：check_modern_jargon（quality.py 古籍向，issue 文案含"硬塞"）vs
        check_modern_jargon_terms（content_quality.py 硬套术语，全桶都跑，issue 文案含"硬套"）。
        modern 桶应跳过前者，保留后者。
        """
        content = _make_content("职场课", "这套方法论的底层逻辑是反馈循环。")
        report = run_content_quality_checks(content, archetype="modern")
        readability_issues = report.details.get("readability", [])
        # check_modern_jargon（古籍向）的 issue 文案是"历史叙事中疑似硬塞现代术语：底层逻辑"
        # 用"硬塞"作为判别词（不是"禁用"，后者在两个函数的文案中都不存在）
        assert not any("底层逻辑" in i and "硬塞" in i for i in readability_issues), (
            f"modern 桶不应因'底层逻辑'报古籍向术语硬塞，却报：{readability_issues}"
        )

    def test_modern_relaxes_ai_tone(self):
        """modern 桶放宽 AI 味检测（过滤过于敏感的模式如'这说明''可见'）。"""
        content = _make_content("职场课", "这说明可见这事说明最关键的是执行。")
        report = run_content_quality_checks(content, archetype="modern")
        readability_issues = report.details.get("readability", [])
        # modern 桶应过滤掉"这说明""可见"等常见中文判断句的 AI 味误报
        assert not any("这说明" in i and "AI" in i for i in readability_issues), (
            f"modern 桶应放宽 AI 味检测，却报：{readability_issues}"
        )


# ---------------------------------------------------------------------------
# 契约3：knowledge 桶跳过古籍专属规则
# ---------------------------------------------------------------------------

class TestKnowledgeBucketSkipsAncientRules:
    """knowledge 桶（AI课/易经课）不跑古籍专属检查。"""

    def test_knowledge_skips_year_check(self):
        """knowledge 桶不检查年份必填。"""
        content = _make_content("AI大模型学习", "Transformer 用了 Self-Attention 机制。")
        report = run_content_quality_checks(content, archetype="knowledge")
        truth_issues = report.details.get("truth", [])
        assert not any("年份" in i for i in truth_issues), (
            f"knowledge 桶不应检查年份，却报：{truth_issues}"
        )

    def test_knowledge_skips_famous_critics_check(self):
        """knowledge 桶不强制古籍名家。"""
        content = _make_content("AI大模型学习", "Attention Is All You Need 提出了 Transformer。")
        report = run_content_quality_checks(content, archetype="knowledge")
        truth_issues = report.details.get("truth", [])
        assert not any("司马光" in i or "名家" in i for i in truth_issues), (
            f"knowledge 桶不应强制古籍名家，却报：{truth_issues}"
        )

    def test_knowledge_skips_temporal_order_check(self):
        """knowledge 桶跳过历史时间线检查。"""
        content = _make_content("AI大模型学习", "## 讲事情\nTransformer 的演进。")
        report = run_content_quality_checks(content, archetype="knowledge")
        sequence_issues = report.details.get("sequence", [])
        assert not any("时间" in i or "年份" in i for i in sequence_issues), (
            f"knowledge 桶不应检查时间线，却报：{sequence_issues}"
        )


# ---------------------------------------------------------------------------
# 契约4：knowledge 桶术语白名单
# ---------------------------------------------------------------------------

class TestKnowledgeTermsWhitelist:
    """knowledge 桶用 KNOWLEDGE_TERMS_WHITELIST 做中英混杂白名单。"""

    def test_whitelist_constant_exists(self):
        """KNOWLEDGE_TERMS_WHITELIST 常量存在且含技术术语。"""
        from src.utils.content_quality import KNOWLEDGE_TERMS_WHITELIST
        assert "Transformer" in KNOWLEDGE_TERMS_WHITELIST
        assert "Attention" in KNOWLEDGE_TERMS_WHITELIST
        assert "Token" in KNOWLEDGE_TERMS_WHITELIST

    def test_check_mixed_language_knowledge_function_exists(self):
        """check_mixed_language_knowledge 函数存在。"""
        from src.utils.content_quality import check_mixed_language_knowledge
        assert callable(check_mixed_language_knowledge)

    def test_knowledge_bucket_uses_terms_whitelist(self):
        """knowledge 桶中 Token/Transformer/Attention 不算中英混杂。"""
        body = "这个 Transformer 模型用了 Attention 机制，每个 Token 都会被编码。"
        content = _make_content("AI大模型学习", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        readability_issues = report.details.get("readability", [])
        assert not any("中英文混杂" in i or "中英混杂" in i for i in readability_issues), (
            f"knowledge 桶技术术语不应报中英混杂，却报：{readability_issues}"
        )

    def test_knowledge_bucket_still_flags_non_whitelist_mixed(self):
        """knowledge 桶仍检测非白名单的中英混杂（无空格紧邻才算混杂）。"""
        body = "这个model很powerful，可以process很多data。"
        content = _make_content("AI大模型学习", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        readability_issues = report.details.get("readability", [])
        assert any("中英文混杂" in i or "中英混杂" in i for i in readability_issues), (
            f"knowledge 桶应检测非白名单中英混杂，但未报：{readability_issues}"
        )


# ---------------------------------------------------------------------------
# 契约4.1:knowledge 桶白名单扩展(全栈知识边界专栏,2026-06)
# 对应 BUG-027 archetype 分桶教训:每开新 knowledge 桶专栏必须先扩展白名单
# ---------------------------------------------------------------------------

class TestKnowledgeTermsWhitelistExpansion:
    """全栈知识边界专栏扩展的白名单术语(去重 + 命中 + 跨专栏一致性)。"""

    def test_whitelist_has_no_duplicates(self):
        """白名单不允许重复元素(防止 CAP/RAG/Embedding 等被重复添加)。"""
        from src.utils.content_quality import KNOWLEDGE_TERMS_WHITELIST
        assert len(KNOWLEDGE_TERMS_WHITELIST) == len(set(KNOWLEDGE_TERMS_WHITELIST)), (
            f"白名单存在重复元素:{[t for t in KNOWLEDGE_TERMS_WHITELIST if KNOWLEDGE_TERMS_WHITELIST.count(t) > 1]}"
        )

    def test_existing_terms_preserved(self):
        """扩展后原有 27 个术语仍在(AI 大模型/MySQL 专栏依赖)。"""
        from src.utils.content_quality import KNOWLEDGE_TERMS_WHITELIST
        required_existing = [
            "Transformer", "Attention", "Token", "Tokenizer", "Embedding",
            "RAG", "LLM", "GPT", "BERT", "GPU", "CPU", "TPU",
            "API", "REST", "GraphQL", "gRPC",
            "SQL", "NoSQL", "ACID", "BASE", "CAP",
            "RDBMS", "BTree", "LSM",
            "Python", "Java", "Rust",
        ]
        for term in required_existing:
            assert term in KNOWLEDGE_TERMS_WHITELIST, f"原有术语 {term} 丢失"

    @pytest.mark.parametrize("term", [
        # 容器与编排
        "Docker", "Kubernetes", "K8s",
        # Web 服务器与中间件
        "Nginx", "Kafka", "RabbitMQ", "Redis",
        # 网络协议
        "HTTP", "HTTPS", "TCP", "UDP", "TLS", "DNS", "CDN", "WebSocket",
        # 安全
        "JWT", "OAuth", "XSS", "CSRF",
        # 分布式
        "Raft", "Paxos", "MVCC",
        # DevOps
        "Jenkins", "GitLab", "GitHub",
        # 运行时
        "JVM", "GC", "GIL",
        # 框架
        "Spring", "Django", "Flask", "FastAPI", "Vue", "React",
        # 架构方法
        "DDD", "TDD", "BDD", "ORM", "DAO",
        # 渲染
        "SSR", "CSR", "SSG", "SPA",
        # 云服务
        "SaaS", "PaaS", "IaaS", "FaaS",
        # 前端基础
        "HTML", "CSS", "JSON", "DOM", "URL",
    ])
    def test_new_terms_in_whitelist(self, term):
        """新增全栈术语必须在白名单内(参数化遍历每一个)。"""
        from src.utils.content_quality import KNOWLEDGE_TERMS_WHITELIST
        assert term in KNOWLEDGE_TERMS_WHITELIST, (
            f"全栈专栏新增术语 {term} 未在白名单,会触发 check_mixed_language_knowledge 误报"
        )

    @pytest.mark.parametrize("term", [
        "Docker", "Kubernetes", "HTTP", "TCP", "JWT", "Redis", "Kafka",
        "Nginx", "Vue", "React", "Spring", "Django", "GIL", "JVM",
        "DDD", "TDD", "LRU", "SSR", "SaaS", "HTML", "CSS", "JSON",
    ])
    def test_new_terms_not_flagged_as_mixed(self, term):
        """新增术语与中文紧邻时不报中英混杂(参数化验证每一个)。"""
        body = f"用{term}部署服务,这是全栈开发常见做法。"
        content = _make_content("AI时代全栈知识边界", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        readability_issues = report.details.get("readability", [])
        assert not any("中英文混杂" in i or "中英混杂" in i for i in readability_issues), (
            f"白名单术语 {term} 不应报中英混杂,却报:{readability_issues}"
        )

    @pytest.mark.parametrize("term", [
        # 全栈专栏质检阶段补(2026-06):AI 时代核心术语 + DevOps 缩写 + 中间件 + 业务标识
        "AI", "CI", "CD", "Zookeeper", "ID",
        # 全栈专栏质检阶段二次补(2026-06):具体数据库产品 + Python 术语 + 职务名
        "MySQL", "PostgreSQL", "MongoDB", "docstring", "Lead",
    ])
    def test_qc_stage_terms_in_whitelist(self, term):
        """质检阶段补的术语必须在白名单内(参数化验证)。"""
        from src.utils.content_quality import KNOWLEDGE_TERMS_WHITELIST
        assert term in KNOWLEDGE_TERMS_WHITELIST, (
            f"质检阶段补的术语 {term} 未在白名单,会触发 check_mixed_language_knowledge 误报"
        )

    @pytest.mark.parametrize("term", [
        "AI", "CI", "CD", "Zookeeper", "ID",
        "MySQL", "PostgreSQL", "MongoDB", "docstring", "Lead",
    ])
    def test_qc_stage_terms_not_flagged_as_mixed(self, term):
        """质检阶段补的术语与中文紧邻时不报中英混杂(参数化验证)。"""
        body = f"用{term}做全栈开发,这是 AI 时代常态。"
        content = _make_content("AI时代全栈知识边界", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        readability_issues = report.details.get("readability", [])
        assert not any("中英文混杂" in i or "中英混杂" in i for i in readability_issues), (
            f"质检阶段补的术语 {term} 不应报中英混杂,却报:{readability_issues}"
        )

    def test_existing_knowledge_columns_not_degraded(self):
        """扩展白名单后,原有 knowledge 专栏样本不应出现新的失败(回归保险)。"""
        # 用 AI 大模型学习的典型术语构造样本,扩展前已通过,扩展后仍应通过
        body = (
            "Transformer 用了 Attention 机制,每个 Token 都会被 Embedding 编码。"
            "这是 RAG 系统的核心,GPT 和 BERT 都基于此。"
        )
        content = _make_content("AI大模型学习", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        readability_issues = report.details.get("readability", [])
        assert not any("中英文混杂" in i or "中英混杂" in i for i in readability_issues), (
            f"原有 AI 大模型专栏样本不应因白名单扩展而失败:{readability_issues}"
        )


# ---------------------------------------------------------------------------
# 契约4.2:check_internal_repetition 仅 narrative 桶跑
# (BUG-027 教训延续:knowledge 桶用「」做中英对照/章节标题引用是常态)
# ---------------------------------------------------------------------------

class TestCheckInternalRepetitionArchetypeRouting:
    """check_internal_repetition 只对 narrative 桶跑,knowledge/modern 跳过。

    knowledge 桶中「GIL(Global Interpreter Lock,全局解释器锁)」「Python必须掌握的内核」
    是中英对照与章节引用的常态用法,不应被误报为"古文/金句重复"。
    """

    def test_narrative_flags_repeated_bracketed_quote(self):
        """narrative 桶:同一「...」金句出现 2 次应被报重复。"""
        body = "他常说「天下兴亡,匹夫有责」。后来又有人写「天下兴亡,匹夫有责」于墙上。"
        content = _make_content("测试书", body)
        report = run_content_quality_checks(content, archetype="narrative")
        readability_issues = report.details.get("readability", [])
        assert any("单章内重复古文/金句" in i for i in readability_issues), (
            f"narrative 桶应报「天下兴亡」金句重复,却未报:{readability_issues}"
        )

    def test_knowledge_skips_repeated_bracketed_term(self):
        """knowledge 桶:同一「中英对照术语」出现 2 次不应报重复。"""
        body = (
            "「GIL(Global Interpreter Lock,全局解释器锁)」是 CPython 的核心机制。"
            "在讲并发时,「GIL(Global Interpreter Lock,全局解释器锁)」会再次出现。"
        )
        content = _make_content("AI时代全栈知识边界", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        readability_issues = report.details.get("readability", [])
        assert not any("单章内重复古文/金句" in i for i in readability_issues), (
            f"knowledge 桶不应报中英对照术语重复,却报:{readability_issues}"
        )

    def test_knowledge_skips_repeated_chapter_title(self):
        """knowledge 桶:同一「章节标题」出现 2 次不应报重复。"""
        body = (
            "本专栏第 04 章「Python必须掌握的内核」讲 GIL。"
            "学完后回头看「Python必须掌握的内核」会有新理解。"
        )
        content = _make_content("AI时代全栈知识边界", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        readability_issues = report.details.get("readability", [])
        assert not any("单章内重复古文/金句" in i for i in readability_issues), (
            f"knowledge 桶不应报章节标题重复,却报:{readability_issues}"
        )

    def test_modern_skips_repeated_bracketed_title(self):
        """modern 桶:同一「书名」出现 2 次不应报重复。"""
        body = (
            "「代码整洁之道」是程序员必读。"
            "团队 Lead 应把「代码整洁之道」列为新人必修。"
        )
        content = _make_content("职场课", body)
        report = run_content_quality_checks(content, archetype="modern")
        readability_issues = report.details.get("readability", [])
        assert not any("单章内重复古文/金句" in i for i in readability_issues), (
            f"modern 桶不应报书名重复,却报:{readability_issues}"
        )


# ---------------------------------------------------------------------------
# 契约5：check_numeric_facts auto_errors 全桶都跑
# ---------------------------------------------------------------------------

class TestNumericFactsAutoAllBuckets:
    """check_numeric_facts 的 auto_errors（数字硬错误）是通用检查，全桶都跑。

    BUG-026 教训：灵魂再好数字错了仍是 P0。
    当前 BUG：run_content_quality_checks 根本没调 check_numeric_facts。
    """

    @pytest.mark.parametrize("archetype", ["narrative", "modern", "knowledge"])
    def test_auto_numeric_error_detected_for_all_buckets(self, archetype):
        """'5个字：你好世'（5字实际3字）应被所有桶检测为数字硬错误。"""
        body = "这段话有个5个字：你好世，明显数错了。"
        content = _make_content("测试书", body)
        report = run_content_quality_checks(content, archetype=archetype)
        assert any("5个字" in i or "数字" in i for i in report.issues), (
            f"{archetype} 桶应检测数字硬错误，但 issues 中无相关项：{report.issues}"
        )


# ---------------------------------------------------------------------------
# 契约6：check_ai_cliches 全桶都跑
# ---------------------------------------------------------------------------

class TestAiClichesAllBuckets:
    """check_ai_cliches（套话黑名单）是通用检查，全桶都跑。

    当前 BUG：run_content_quality_checks 根本没调 check_ai_cliches。
    """

    @pytest.mark.parametrize("archetype", ["narrative", "modern", "knowledge"])
    def test_ai_cliches_detected_for_all_buckets(self, archetype):
        """命中 ≥3 次 AI 套话应被所有桶检测。"""
        body = "综上所述，历史的车轮让我们看到以史为鉴。在历史的长河中，不禁让人深思。"
        content = _make_content("测试书", body)
        report = run_content_quality_checks(content, archetype=archetype)
        assert any("套话" in i for i in report.issues), (
            f"{archetype} 桶应检测AI套话，但 issues 中无相关项：{report.issues}"
        )


# ---------------------------------------------------------------------------
# 契约7：check_numeric_facts manual_review 按 archetype 过滤
# ---------------------------------------------------------------------------

class TestNumericFactsManualFilter:
    """numeric manual_review（N年前后/N岁/N品官）按 archetype 过滤误标。

    narrative 桶：保留全部（古籍中 N年前后/N岁 需核验是否记错）
    modern/knowledge 桶：过滤 N年前后/N岁（现代语境"10年前""30岁"是正常表达）
    """

    def test_narrative_keeps_manual_review(self):
        """narrative 桶保留 N年前后/N岁 的人工复核标记。"""
        body = "10年前的那场变故让30岁的他感慨万千。"
        content = _make_content("史记", body)
        report = run_content_quality_checks(content, archetype="narrative")
        assert any("10年前" in i for i in report.issues), (
            f"narrative 桶应标记'10年前'需人工复核，但未报：{report.issues}"
        )
        assert any("30岁" in i for i in report.issues), (
            f"narrative 桶应标记'30岁'需人工复核，但未报：{report.issues}"
        )

    def test_modern_filters_manual_review(self):
        """modern 桶过滤 N年前后/N岁 误标（'10年前''30岁'是现代正常表达）。"""
        body = "10年前的行业变化让30岁的管理者感触颇深。"
        content = _make_content("理财课", body)
        report = run_content_quality_checks(content, archetype="modern")
        assert not any("10年前" in i for i in report.issues), (
            f"modern 桶不应标记'10年前'，却报：{report.issues}"
        )
        assert not any("30岁" in i for i in report.issues), (
            f"modern 桶不应标记'30岁'，却报：{report.issues}"
        )

    def test_knowledge_filters_manual_review(self):
        """knowledge 桶过滤 N年前后/N岁 误标。"""
        body = "10年前的模型用了30岁的算法工程师的思路。"
        content = _make_content("AI大模型学习", body)
        report = run_content_quality_checks(content, archetype="knowledge")
        assert not any("10年前" in i for i in report.issues), (
            f"knowledge 桶不应标记'10年前'，却报：{report.issues}"
        )
        assert not any("30岁" in i for i in report.issues), (
            f"knowledge 桶不应标记'30岁'，却报：{report.issues}"
        )


# ---------------------------------------------------------------------------
# 契约8：legacy helpers 已删除
# ---------------------------------------------------------------------------

class TestLegacyHelpersRemoved:
    """_is_modern_column 和 _is_philosophy_or_classic 已删除，由 archetype 取代。

    这两个函数靠书名子串匹配（8词/9词），漏掉财/技/养生，是阶段2要消除的根因。
    """

    def test_is_modern_column_removed(self):
        """_is_modern_column 已从模块中删除。"""
        import src.utils.content_quality as mod
        assert not hasattr(mod, "_is_modern_column"), (
            "_is_modern_column 应删除，由 archetype 参数取代"
        )

    def test_is_philosophy_or_classic_removed(self):
        """_is_philosophy_or_classic 已从模块中删除。"""
        import src.utils.content_quality as mod
        assert not hasattr(mod, "_is_philosophy_or_classic"), (
            "_is_philosophy_or_classic 应删除，由 archetype 参数取代"
        )


# ---------------------------------------------------------------------------
# 契约9：archetype 合法性校验（fail-fast，边界场景）
# ---------------------------------------------------------------------------

class TestArchetypeValidation:
    """非法 archetype 应 fail-fast 抛 ValueError，不静默误路由。

    防止拼写错误（如 'narrativ'）导致行为不可预测。
    v1.2.2 起 fiction 桶在质检层合法（按 modern 分支处理），不再 raise。
    """

    def test_empty_archetype_raises(self):
        """空字符串 archetype 应抛 ValueError。"""
        content = _make_content("测试书", "内容")
        with pytest.raises(ValueError, match="archetype"):
            run_content_quality_checks(content, archetype="")

    def test_invalid_archetype_raises(self):
        """非法 archetype（拼写错误）应抛 ValueError。"""
        content = _make_content("测试书", "内容")
        with pytest.raises(ValueError, match="archetype"):
            run_content_quality_checks(content, archetype="narrativ")  # 少了个 e

    def test_fiction_archetype_accepted_as_modern_branch(self):
        """v1.2.2: fiction 桶在质检层合法，按 modern 分支处理（不 raise）。

        回归 BUG-044：修复前 fiction 在 content_quality.py 抛 ValueError，
        导致洛克菲勒专栏（archetype: fiction）无法跑质检。
        fiction 桶是"七实三虚"小说，路由到 modern 分支：
        - 跳过古籍专属规则（年份/名家/时间线）
        - 用 modern 桶白名单（含 Standard Oil 等英文术语）
        - 放宽 AI 味检测
        """
        content = _make_content("洛克菲勒", "1865 年拍卖 72500 美元。")
        report = run_content_quality_checks(content, archetype="fiction")
        assert report is not None
        # fiction 应跳过古籍专属的年份/名家检测（与 modern 一致）
        truth_issues = report.details.get("truth", [])
        year_issues = [i for i in truth_issues if "年份" in i or "名家" in i]
        assert len(year_issues) == 0, f"fiction 应跳过古籍专属规则，实际报: {year_issues}"

    def test_none_archetype_raises(self):
        """None archetype 应抛 ValueError（而非被当成非 narrative 静默过滤）。"""
        content = _make_content("测试书", "内容")
        with pytest.raises((ValueError, TypeError)):
            run_content_quality_checks(content, archetype=None)


# ---------------------------------------------------------------------------
# 契约10：narrative 桶正向回归保护（只测"modern/knowledge 跳过"不够，还要测"narrative 必检"）
# ---------------------------------------------------------------------------

class TestNarrativeBucketKeepsAncientRules:
    """narrative 桶必须跑古籍专属检查（年份/名家/时间线/现代术语禁用）。

    防止有人把 if archetype == 'narrative' 误改为拼写错误，
    导致 narrative 桶静默跳过年份/名家检查——只测反例不测正例的回归漏洞。
    """

    def test_narrative_reports_missing_years(self):
        """narrative 桶对无年份内容应报'年份缺失'。"""
        content = _make_content("史记", "这段历史没有标注年份。")
        report = run_content_quality_checks(content, archetype="narrative")
        truth_issues = report.details.get("truth", [])
        assert any("年份" in i for i in truth_issues), (
            f"narrative 桶应检查年份，但未报：{truth_issues}"
        )

    def test_narrative_reports_missing_famous_critics(self):
        """narrative 桶对无名家内容应报'名家缺失'。"""
        content = _make_content("史记", "前202年发生了一件事。")
        report = run_content_quality_checks(content, archetype="narrative")
        truth_issues = report.details.get("truth", [])
        assert any("司马光" in i or "名家" in i for i in truth_issues), (
            f"narrative 桶应检查名家，但未报：{truth_issues}"
        )

    def test_narrative_reports_modern_jargon(self):
        """narrative 桶对'底层逻辑'应报古籍向术语硬塞。"""
        content = _make_content("史记", "前202年，底层逻辑开始发挥作用。")
        report = run_content_quality_checks(content, archetype="narrative")
        readability_issues = report.details.get("readability", [])
        assert any("底层逻辑" in i and "硬塞" in i for i in readability_issues), (
            f"narrative 桶应报'底层逻辑'硬塞，但未报：{readability_issues}"
        )

    def test_narrative_reports_temporal_order(self):
        """narrative 桶对'讲事情'段落无年份应报时间线缺失。"""
        content = _make_content("史记", "## 讲事情\n这里没写年份。\n## 参考来源\n- 来源1")
        report = run_content_quality_checks(content, archetype="narrative")
        sequence_issues = report.details.get("sequence", [])
        assert any("时间" in i or "年份" in i for i in sequence_issues), (
            f"narrative 桶应检查时间线，但未报：{sequence_issues}"
        )


# ---------------------------------------------------------------------------
# 契约11：narrative 桶黄金样本回归（古籍专栏改造后分数不降）
# ---------------------------------------------------------------------------

class TestNarrativeGoldenSample:
    """narrative 桶黄金样本：阶段2 新增 check_numeric_facts/check_ai_cliches 不应导致古籍专栏回归。

    design.md §11.2 明确要求「古籍专栏分数不降（防回归）」。
    取资治通鉴·三家分晋（前6章 LoopAgent 优化过的干净样本）做黄金断言。
    """

    def test_zizhi_three_families_score_not_degraded(self):
        """资治通鉴·三家分晋改造后仍应 >=95（阶段2 未引入回归）。"""
        from pathlib import Path
        golden = Path(__file__).resolve().parent.parent / "output" / "资治通鉴" / "周纪一_三家分晋.md"
        if not golden.exists():
            pytest.skip("黄金样本文件不存在，跳过")
        content = golden.read_text(encoding="utf-8")
        report = run_content_quality_checks(content, archetype="narrative")
        assert report.score >= 95, (
            f"narrative 桶黄金样本分数回归：期望 >=95，实际 {report.score}。"
            f"issues: {report.issues}"
        )
