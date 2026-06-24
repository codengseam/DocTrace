"""Web 阅读器前端测试。

本模块不启动浏览器，而是通过读取模板、CSS、JS 源文件，
断言吸底栏、沉浸式全屏、点击翻页等关键实现存在。

注意：本测试针对 src/web/ 旧路径，项目已迁移到 site/；
以 tests/test_reader_features.js 为基线。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.skip(
    reason="针对 src/web/ 旧路径，项目已迁移到 site/；以 tests/test_reader_features.js 为基线。"
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "src" / "web" / "templates" / "index.html"
CSS = ROOT / "src" / "web" / "static" / "css" / "style.css"
JS = ROOT / "src" / "web" / "static" / "js" / "app.js"


@pytest.fixture
def template_html():
    return TEMPLATE.read_text(encoding="utf-8")


@pytest.fixture
def css_text():
    return CSS.read_text(encoding="utf-8")


@pytest.fixture
def js_text():
    return JS.read_text(encoding="utf-8")


def _extract_rule(text: str, selector: str) -> str:
    """从 CSS 文本中提取指定选择器对应的规则块（支持嵌套大括号）。"""
    pattern = re.compile(
        rf"{re.escape(selector)}\s*\{{",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start:i - 1] if depth == 0 else text[start:i]


class TestBottomBar:
    """底部导航栏吸底相关断言。"""

    def test_bottom_bar_uses_fixed_position(self, css_text):
        """底栏必须使用 fixed 定位才能真正吸底。"""
        rule = _extract_rule(css_text, ".bottom-bar")
        assert "position: fixed" in rule, ".bottom-bar 缺少 position: fixed"

    def test_bottom_bar_has_safe_area_padding(self, css_text):
        """底栏必须包含 iPhone home indicator 安全区处理。"""
        rule = _extract_rule(css_text, ".bottom-bar")
        assert "env(safe-area-inset-bottom)" in rule, ".bottom-bar 缺少安全区 padding"

    def test_bottom_bar_hidden_by_transform_not_display(self, css_text):
        """隐藏底栏时应使用 transform 滑出，避免 fixed 元素重渲染闪烁。"""
        rule = _extract_rule(css_text, "body.ui-hidden .bottom-bar")
        assert "transform: translateY(100%)" in rule, "ui-hidden 时应使用 transform 隐藏底栏"

    def test_mobile_reader_has_bottom_padding_for_bottom_bar(self, css_text):
        """移动端阅读区底部应预留底栏高度，防止正文/章末导航被遮挡。"""
        # 在 @media (max-width: 768px) 内的 .reader 规则
        media_match = re.search(
            r"@media\s*\(\s*max-width:\s*768px\s*\)\s*\{",
            css_text,
            re.DOTALL,
        )
        assert media_match, "缺少 768px 媒体查询"
        start = media_match.end()
        depth = 1
        i = start
        while i < len(css_text) and depth > 0:
            if css_text[i] == "{":
                depth += 1
            elif css_text[i] == "}":
                depth -= 1
            i += 1
        media_body = css_text[start:i - 1] if depth == 0 else css_text[start:i]
        reader_rule = _extract_rule(media_body, ".reader")
        assert "padding-bottom" in reader_rule, ".reader 在移动端缺少 padding-bottom"
        assert "env(safe-area-inset-bottom)" in reader_rule, ".reader 移动端 padding 未考虑安全区"


class TestImmersiveMode:
    """沉浸式全屏阅读模式相关断言。"""

    def test_template_has_fullscreen_button(self, template_html):
        """模板中必须存在进入/退出全屏的按钮。"""
        assert 'id="fullscreenBtn"' in template_html, "模板缺少全屏按钮 #fullscreenBtn"

    def test_template_has_tap_zones(self, template_html):
        """模板中必须存在左/中/右触控层，用于番茄小说式翻页。"""
        assert 'class="reader-tap-zones"' in template_html, "模板缺少 .reader-tap-zones 触控层"
        assert 'data-zone="prev"' in template_html, "缺少上一页触控区"
        assert 'data-zone="menu"' in template_html, "缺少中央菜单触控区"
        assert 'data-zone="next"' in template_html, "缺少下一页触控区"

    def test_css_has_immersive_mode_styles(self, css_text):
        """CSS 中必须包含沉浸式模式样式。"""
        assert ".immersive-mode" in css_text, "CSS 缺少 .immersive-mode 样式"

    def test_js_has_fullscreen_api_usage(self, js_text):
        """JS 中必须调用 Fullscreen API。"""
        assert "requestFullscreen" in js_text, "JS 未使用 requestFullscreen"
        assert "exitFullscreen" in js_text or "webkitExitFullscreen" in js_text, "JS 未处理退出全屏"

    def test_js_has_tap_zone_logic(self, js_text):
        """JS 中必须包含触控区分发与翻页逻辑。"""
        assert "reader-tap-zones" in js_text or "data-zone" in js_text, "JS 未引用触控层"
        assert "goPrevPage" in js_text, "JS 缺少 goPrevPage 翻页逻辑"
        assert "goNextPage" in js_text, "JS 缺少 goNextPage 翻页逻辑"

    def test_js_excludes_interactive_elements_from_tap_zones(self, js_text):
        """触控层事件处理应排除链接、按钮、输入框等可交互元素，避免误拦截。"""
        assert "target.closest('a, button, input, textarea, select" in js_text, (
            "JS 未在触控层中排除可交互元素"
        )
