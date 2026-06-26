from src.utils.quality import run_quality_check, check_chapter_title_soul


def test_quality_check_detects_missing_section():
    content = "## 讲事情\n\n内容"
    result = run_quality_check(content, ["讲事情", "讲人物"])
    assert len(result["structure"]) == 1
    assert "讲人物" in result["structure"][0]


def test_quality_check_detects_ai_tone():
    content = "我们可以看到，这件事很重要。"
    result = run_quality_check(content, ["讲事情"])
    assert len(result["ai_tone"]) > 0


def test_quality_check_passes_clean_content():
    content = "## 讲事情\n\n这是故事内容。"
    result = run_quality_check(content, ["讲事情"])
    assert result["structure"] == []
    assert result["ai_tone"] == []


# ===== check_chapter_title_soul 章回体灵魂标题检测 =====


def test_chapter_title_soul_good_titles_score_high():
    """好灵魂标题应得高分（≥3）。"""
    good_titles = [
        "不能不刚",
        "不是谋反，是挡路",
        "替不了的",
        "备顾问而已",
        "改革者必须死",
    ]
    for title in good_titles:
        result = check_chapter_title_soul(title)
        assert result["score"] >= 3, f"好标题 '{title}' 评分应≥3，实际 {result['score']}: {result['reasons']}"


def test_chapter_title_soul_event_label_scores_low():
    """事件标签（短且无刺）应得低分（<3）。"""
    bad_titles = ["备棺", "上疏", "退田", "削藩"]
    for title in bad_titles:
        result = check_chapter_title_soul(title)
        assert result["score"] < 3, f"事件标签 '{title}' 评分应<3，实际 {result['score']}"
        assert any("事件标签" in r or "信息密度" in r for r in result["reasons"])


def test_chapter_title_soul_number_only_scores_low():
    """数字+量词模式应得低分。"""
    bad_titles = ["九个字", "八十五天", "二十七年", "三万人"]
    for title in bad_titles:
        result = check_chapter_title_soul(title)
        assert result["score"] < 3, f"数字量词 '{title}' 评分应<3，实际 {result['score']}"
        assert any("数字" in r for r in result["reasons"])


def test_chapter_title_soul_isolated_object_scores_low():
    """孤立物件指代（那X）应得低分。"""
    bad_titles = ["那支流矢", "那封信", "那把刀", "那道旨意"]
    for title in bad_titles:
        result = check_chapter_title_soul(title)
        assert result["score"] < 3, f"孤立物件 '{title}' 评分应<3，实际 {result['score']}"
        assert any("物件" in r for r in result["reasons"])


def test_chapter_title_soul_decorative_poetic_scores_low():
    """四字景物装饰性短语应得低分。"""
    bad_titles = ["风雨欲来", "潮起潮落", "落花流水"]
    for title in bad_titles:
        result = check_chapter_title_soul(title)
        assert result["score"] < 3, f"装饰诗化 '{title}' 评分应<3，实际 {result['score']}"


def test_chapter_title_soul_xx_de_yy_not_auto_flagged():
    """XX的YY 结构不应自动判低分（很多是好标题用'的'点反差）。"""
    good_xx_de_yy = [
        "举人的命",      # 海瑞身份局限
        "干净的武器",    # 海瑞清廉是武器
        "纸糊的盛世",    # 盛世是假象
        "五年复辽的谎",  # 袁崇焕妄言
        "九千岁的崩塌",  # 魏忠贤倒台
        "被阉割的统帅",  # 郑和身份反差
        "刮腐肉的人",    # 严嵩整顿吏治
        "十八年的散沙",  # 南明不团结
    ]
    for title in good_xx_de_yy:
        result = check_chapter_title_soul(title)
        assert result["score"] >= 3, f"XX的YY好标题 '{title}' 不应被误判，实际 {result['score']}: {result['reasons']}"


def test_chapter_title_soul_empty_title():
    """空标题应得 0 分。"""
    result = check_chapter_title_soul("")
    assert result["score"] == 0
    assert any("空" in r for r in result["reasons"])


def test_chapter_title_soul_returns_score_and_reasons():
    """返回结构应包含 score 和 reasons 字段。"""
    result = check_chapter_title_soul("不能不刚")
    assert "score" in result
    assert "reasons" in result
    assert isinstance(result["reasons"], list)
    assert isinstance(result["score"], int)


def test_chapter_title_soul_mixed_good_title_not_flagged():
    """承载洞察的中长标题不应被误判为低分。"""
    good_titles = [
        "赢了面子输了里子",
        "杀功臣保的不是孙子，是孤独",
        "天子守国门",
        "铁券免不了一死",
        "压不住",
    ]
    for title in good_titles:
        result = check_chapter_title_soul(title)
        assert result["score"] >= 3, f"好标题 '{title}' 不应被误判，实际 {result['score']}: {result['reasons']}"
